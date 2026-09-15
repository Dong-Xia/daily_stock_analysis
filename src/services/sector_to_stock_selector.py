# -*- coding: utf-8 -*-
"""
热点板块 → 个股精选自动化管线

从板块轮动锁定结果中自动选取 Top 5 热点板块，
逐个调用个股精选，带限流间隔，聚合返回结果。
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# 板块间调用间隔（秒），可通过环境变量覆盖
DEFAULT_PICK_INTERVAL_SECONDS = 8
_MAX_SECTORS = 5


@dataclass
class SectorPickResult:
    """单个板块的精选结果."""
    sector_name: str = ""
    classification: str = ""
    classification_cn: str = ""
    candidates: List[Dict[str, Any]] = field(default_factory=list)
    success: bool = True
    error_message: str = ""


@dataclass
class HotSectorChainResponse:
    """热点板块链式精选的完整响应."""
    total_sectors: int = 0
    succeeded: int = 0
    failed: int = 0
    interval_seconds: int = DEFAULT_PICK_INTERVAL_SECONDS
    results: List[SectorPickResult] = field(default_factory=list)


class SectorToStockSelector:
    """热点板块 → 个股精选编排器."""

    def __init__(
        self,
        max_sectors: int = _MAX_SECTORS,
        interval_seconds: Optional[int] = None,
    ):
        self.max_sectors = max_sectors
        self.interval_seconds = interval_seconds or int(
            os.getenv("SECTOR_PICK_INTERVAL_SECONDS", str(DEFAULT_PICK_INTERVAL_SECONDS))
        )

    def execute(self) -> HotSectorChainResponse:
        """执行热点板块链式精选全流程."""
        # Step 1: 获取板块轮动数据
        sectors = self._get_top_sectors()
        if not sectors:
            logger.warning("[SectorToStock] 无热点板块可处理")
            return HotSectorChainResponse(total_sectors=0, interval_seconds=self.interval_seconds)

        logger.info(
            "[SectorToStock] 获取到 %d 个热点板块（取前 %d 个）",
            len(sectors), self.max_sectors,
        )

        # Step 2: 逐个精选（带限流）
        results: List[SectorPickResult] = []
        succeeded = 0
        failed = 0

        for i, sector in enumerate(sectors):
            sector_name = sector.get("name", "")
            classification = sector.get("classification", "")
            classification_cn = sector.get("classification_cn", "")

            logger.info(
                "[SectorToStock] (%d/%d) 开始精选板块: %s (%s)",
                i + 1, min(len(sectors), self.max_sectors),
                sector_name, classification_cn,
            )

            pick_result = self._pick_sector(sector_name, classification, classification_cn)
            results.append(pick_result)

            if pick_result.success:
                succeeded += 1
            else:
                failed += 1

            # 失败率过半则提前终止
            total_processed = succeeded + failed
            if total_processed >= 3 and failed / total_processed > 0.5:
                logger.warning(
                    "[SectorToStock] 失败率超过 50%%（%d/%d），提前终止后续调用",
                    failed, total_processed,
                )
                break

            # 板块间限流间隔
            if i < len(sectors) - 1 and i < self.max_sectors - 1:
                logger.debug("[SectorToStock] 等待 %d 秒...", self.interval_seconds)
                time.sleep(self.interval_seconds)

        return HotSectorChainResponse(
            total_sectors=len(results),
            succeeded=succeeded,
            failed=failed,
            interval_seconds=self.interval_seconds,
            results=results,
        )

    def _get_top_sectors(self) -> List[Dict[str, Any]]:
        """从板块轮动分析中获取排名前几的热点板块."""
        try:
            from src.services.sector_rotation_tracker import SectorRotationTracker

            tracker = SectorRotationTracker()
            rotation_result = tracker.analyze()

            # 优先取主线 + 强势轮动
            candidates: List[Dict[str, Any]] = []
            seen_names: set = set()

            for sector in rotation_result.top_main_lines:
                if sector.name and sector.name not in seen_names:
                    candidates.append({
                        "name": sector.name,
                        "classification": sector.classification,
                        "classification_cn": sector.classification_cn,
                        "score": sector.current_score,
                    })
                    seen_names.add(sector.name)

            for sector in rotation_result.sectors:
                if len(candidates) >= self.max_sectors:
                    break
                if sector.name and sector.name not in seen_names:
                    if sector.classification in ("strong_rotating", "rotating"):
                        candidates.append({
                            "name": sector.name,
                            "classification": sector.classification,
                            "classification_cn": sector.classification_cn,
                            "score": sector.current_score,
                        })
                        seen_names.add(sector.name)

            return candidates[:self.max_sectors]

        except ImportError as e:
            logger.error("[SectorToStock] 导入板块轮动模块失败: %s", e)
            return []
        except Exception as e:
            logger.error("[SectorToStock] 获取板块轮动数据失败: %s", e)
            return []

    def _pick_sector(
        self,
        sector_name: str,
        classification: str,
        classification_cn: str,
    ) -> SectorPickResult:
        """对单个板块执行个股精选."""
        try:
            from src.services.stock_screener_service import StockScreenerService
            from src.schemas.stock_screener_schema import ScreenerCriteria

            # 单板块预算 40s：最坏 5×(40+8)=240s，留在 hot-sector-chain 端点 300s 超时内；
            # 旧值 170s 时最坏 5×(170+8)=890s，必然被 wait_for(300) 腰斩成 504
            service = StockScreenerService(
                max_candidates=10,
                timeout_budget=40.0,
            )
            criteria = ScreenerCriteria(
                sector_name=sector_name,
                min_avg_amount_yi=1.0,
                min_turnover_rate=1.0,
                require_ma_alignment=True,
            )
            result = service.screen(criteria)

            candidates = []
            for c in result.candidates:
                candidates.append({
                    "code": c.code,
                    "name": c.name,
                    "price": c.price,
                    "change_pct": c.change_pct,
                    "composite_score": c.factors.composite_score if c.factors else 0,
                    "ma_alignment": c.ma_alignment,
                    "turnover_rate": c.turnover_rate,
                    "avg_amount_yi": c.avg_amount_yi,
                })

            logger.info(
                "[SectorToStock] 板块 '%s' 精选完成: %d 只候选",
                sector_name, len(candidates),
            )

            return SectorPickResult(
                sector_name=sector_name,
                classification=classification,
                classification_cn=classification_cn,
                candidates=candidates,
                success=True,
            )

        except ImportError as e:
            logger.error("[SectorToStock] 导入个股精选模块失败: %s", e)
            return SectorPickResult(
                sector_name=sector_name,
                classification=classification,
                classification_cn=classification_cn,
                success=False,
                error_message=f"导入模块失败: {e}",
            )
        except Exception as e:
            logger.error("[SectorToStock] 板块 '%s' 精选失败: %s", sector_name, e)
            return SectorPickResult(
                sector_name=sector_name,
                classification=classification,
                classification_cn=classification_cn,
                success=False,
                error_message=str(e),
            )
