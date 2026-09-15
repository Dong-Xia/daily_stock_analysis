# -*- coding: utf-8 -*-
"""
板块锁定/轮动分析 — "谁能持续涨"的筛选器

消费上游 SectorAnalyzer（热点板块）的每日排行榜数据，
站在多日历史数据上，把主线（main_line）从轮动/脉冲/退潮中分离出来。

下游分类：
   主线(main_line) / 强势轮动(strong_rotating) / 轮动(rotating)
    / 脉冲(pulse) / 异动(emerging) / 退潮(fading)
"""
from __future__ import annotations

import json
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from src.services.sector_analysis_storage import get_sector_analysis_storage, SectorAnalysisStorage

logger = logging.getLogger(__name__)


@dataclass
class SectorDurability:
    """Per-sector durability metrics computed from multi-day rankings."""
    name: str = ""
    appearance_count: int = 0
    top3_count: int = 0
    top5_count: int = 0
    consecutive_days: int = 0
    current_rank: int = 99
    current_score: float = 0.0
    avg_score: float = 0.0
    score_trend: float = 0.0
    momentum_5d: float = 0.0
    rank_volatility: float = 0.0
    classification: str = "unknown"
    classification_cn: str = "未知"
    daily_scores: Dict[str, float] = field(default_factory=dict)


@dataclass
class SectorRotationResult:
    """Full sector rotation analysis result."""
    analysis_date: str = ""
    lookback_days: int = 20
    total_ranking_days: int = 0
    sectors: List[SectorDurability] = field(default_factory=list)
    top_main_lines: List[SectorDurability] = field(default_factory=list)
    rising_sectors: List[SectorDurability] = field(default_factory=list)
    fading_sectors: List[SectorDurability] = field(default_factory=list)


class SectorRotationTracker:
    """板块锁定引擎：基于多日排行榜把主线从噪音中分离出来。"""

    CLASSIFICATION_RULES = {
        "main_line": {"cn": "主线", "min_consecutive": 5, "min_appearance_ratio": 0.6},
        "strong_rotating": {"cn": "强势轮动", "min_consecutive": 3, "min_appearance_ratio": 0.4},
        "rotating": {"cn": "轮动", "min_appearance_ratio": 0.3},
        "pulse": {"cn": "脉冲", "max_consecutive": 2},
        "emerging": {"cn": "异动", "conditions": "recent_appearance_only"},
        "fading": {"cn": "退潮", "conditions": "trend_negative"},
    }

    def __init__(
        self,
        storage: Optional[SectorAnalysisStorage] = None,
        lookback_days: int = 20,
        top_n: int = 30,
    ):
        self.storage = storage or get_sector_analysis_storage()
        self.lookback_days = lookback_days
        self.top_n = top_n

    def analyze(self, target_date: Optional[str] = None) -> SectorRotationResult:
        available_dates = self.storage.get_available_dates(self.lookback_days + 10)
        if not available_dates:
            return SectorRotationResult(lookback_days=self.lookback_days)

        if target_date:
            dates = [d for d in available_dates if d <= target_date][:self.lookback_days]
        else:
            dates = available_dates[:self.lookback_days]

        if not dates:
            return SectorRotationResult(lookback_days=self.lookback_days, analysis_date=target_date or "")

        analysis_date = target_date or dates[0]
        dates.sort()
        sector_history: Dict[str, List[Tuple[str, int, float]]] = defaultdict(list)

        for date_str in dates:
            data = self.storage.get(date_str)
            if not data:
                continue
            sectors = data.get("sectors", [])
            for i, s in enumerate(sectors[:self.top_n]):
                name = s.get("name", "")
                if not name:
                    continue
                rank = i + 1
                score = float(s.get("score", 0) or 0)
                sector_history[name].append((date_str, rank, score))

        if not sector_history:
            return SectorRotationResult(
                analysis_date=analysis_date, lookback_days=self.lookback_days,
                total_ranking_days=len(dates),
            )

        sectors = []
        for name, entries in sector_history.items():
            entries.sort(key=lambda e: e[0])
            scores = [e[2] for e in entries]
            ranks = [e[1] for e in entries]

            appearance_count = len(entries)
            top3_count = sum(1 for r in ranks if r <= 3)
            top5_count = sum(1 for r in ranks if r <= 5)
            consecutive_days = self._compute_consecutive(entries, dates)
            current_rank = ranks[-1] if ranks else 99
            current_score = scores[-1] if scores else 0
            avg_score = float(np.mean(scores)) if scores else 0.0
            score_trend = self._compute_score_trend(scores)
            momentum_5d = self._compute_momentum_5d(scores)
            rank_volatility = float(np.std(ranks)) if len(ranks) >= 3 else 0.0

            appearance_ratio = appearance_count / max(len(dates), 1)
            classification, cn_label = self._classify(
                consecutive_days, appearance_ratio, score_trend, current_score,
            )

            daily_scores = {e[0]: e[2] for e in entries}

            sectors.append(SectorDurability(
                name=name,
                appearance_count=appearance_count,
                top3_count=top3_count,
                top5_count=top5_count,
                consecutive_days=consecutive_days,
                current_rank=current_rank,
                current_score=current_score,
                avg_score=avg_score,
                score_trend=round(score_trend, 3),
                momentum_5d=round(momentum_5d, 2),
                rank_volatility=round(rank_volatility, 2),
                classification=classification,
                classification_cn=cn_label,
                daily_scores=daily_scores,
            ))

        sectors.sort(key=lambda s: (
            s.consecutive_days * 3 + s.top3_count * 2 + s.appearance_count
        ), reverse=True)

        main_lines = [s for s in sectors if s.classification == "main_line"]
        rising = [s for s in sectors if s.classification in ("strong_rotating", "emerging") and s.score_trend > 0]
        fading = [s for s in sectors if s.classification == "fading" or (s.score_trend < -0.5 and s.consecutive_days == 0)]

        return SectorRotationResult(
            analysis_date=analysis_date,
            lookback_days=self.lookback_days,
            total_ranking_days=len(dates),
            sectors=sectors,
            top_main_lines=main_lines,
            rising_sectors=rising,
            fading_sectors=fading,
        )

    @staticmethod
    def _compute_consecutive(entries: List[Tuple], all_dates: List[str]) -> int:
        """Count consecutive trading days this sector appears in top N from the latest date backwards.

        Uses the full trading calendar (all_dates) to detect gaps where the sector
        dropped out of the top N on intermediate trading days.
        """
        if not entries or not all_dates:
            return 0
        entry_dates = {e[0] for e in entries}
        # Sector must be in rankings on the latest available date
        if all_dates[-1] not in entry_dates:
            return 0
        consecutive = 0
        for i in range(len(all_dates) - 1, -1, -1):
            if all_dates[i] in entry_dates:
                consecutive += 1
            else:
                break
        return consecutive

    @staticmethod
    def _compute_score_trend(scores: List[float]) -> float:
        if len(scores) < 3:
            return 0.0
        try:
            x = np.arange(len(scores))
            slope = np.polyfit(x, scores, 1)[0]
            return float(slope) / (max(abs(slope), 0.01)) * min(abs(slope), 5) / 5 * 10
        except Exception:
            return 0.0

    @staticmethod
    def _compute_momentum_5d(scores: List[float]) -> float:
        if len(scores) < 5:
            return 0.0
        return scores[-1] - scores[-min(5, len(scores))]

    @staticmethod
    def _classify(
        consecutive: int, ratio: float, trend: float, score: float,
    ) -> Tuple[str, str]:
        if consecutive >= 5 and ratio >= 0.6:
            return "main_line", "主线"
        if consecutive >= 3 and ratio >= 0.4:
            return "strong_rotating", "强势轮动"
        if ratio >= 0.3:
            if trend > 1.0:
                return "strong_rotating", "强势轮动"
            return "rotating", "轮动"
        if consecutive <= 2 and ratio < 0.3:
            if trend < -1.0:
                return "fading", "退潮"
            if consecutive == 0 and ratio < 0.2 and score > 0:
                return "emerging", "异动"
            return "pulse", "脉冲"
        if consecutive == 0 and ratio < 0.2 and score > 0:
            return "emerging", "异动"
        if trend < -1.5:
            return "fading", "退潮"
        return "unknown", "未分类"
