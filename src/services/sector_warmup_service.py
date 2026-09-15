# -*- coding: utf-8 -*-
import logging
import random
import threading
import time
from datetime import datetime
from typing import List

logger = logging.getLogger(__name__)

DEFAULT_WARMUP_DELAY_SECONDS = 30
MIN_REQUEST_INTERVAL = 5.0
MAX_REQUEST_INTERVAL = 10.0
FAILURE_BACKOFF_SECONDS = 20.0
MAX_SECTORS_TO_WARMUP = 10


def run_sector_cache_warmup(delay_seconds: int = DEFAULT_WARMUP_DELAY_SECONDS) -> None:
    def _warmup_worker() -> None:
        time.sleep(delay_seconds)
        logger.info("[SectorWarmup] 开始板块缓存预热")

        try:
            from data_provider.base import DataFetcherManager
            from src.services.sector_cache_service import get_sector_cache

            dm = DataFetcherManager()
            cache = get_sector_cache()

            top, _ = dm.get_sector_rankings(20)
            all_sectors: List[str] = []
            seen = set()
            for s in top:
                name = s.get("name", "")
                if name and name not in seen:
                    seen.add(name)
                    all_sectors.append(name)

            if not all_sectors:
                logger.warning("[SectorWarmup] 未获取到板块列表，跳过预热")
                return

            sectors_to_warmup = all_sectors[:MAX_SECTORS_TO_WARMUP]
            cache.set_meta("is_warming_up", "true")
            cache.set_meta("warmup_total_sectors", str(len(sectors_to_warmup)))
            cache.set_meta("warmup_completed_sectors", "0")

            completed = 0
            consecutive_failures = 0

            for sector_name in sectors_to_warmup:
                found = False
                for board_type in ("industry", "concept"):
                    try:
                        members = dm.get_board_members(sector_name, board_type=board_type)
                        if members:
                            cache.set_board_members(sector_name, board_type, members)
                            found = True
                            consecutive_failures = 0
                            break
                    except Exception as e:
                        logger.debug(f"[SectorWarmup] {sector_name}/{board_type} 失败: {e}")
                        continue

                if not found:
                    consecutive_failures += 1
                    logger.debug(f"[SectorWarmup] {sector_name} 未获取到成分股")

                completed += 1
                cache.set_meta("warmup_completed_sectors", str(completed))

                if consecutive_failures >= 3:
                    logger.warning(
                        f"[SectorWarmup] 连续 {consecutive_failures} 次失败，"
                        f"休眠 {FAILURE_BACKOFF_SECONDS}s 让数据源冷却"
                    )
                    time.sleep(FAILURE_BACKOFF_SECONDS)
                    consecutive_failures = 0
                else:
                    sleep_sec = random.uniform(MIN_REQUEST_INTERVAL, MAX_REQUEST_INTERVAL)
                    time.sleep(sleep_sec)

            cache.set_meta("last_warmup_time", datetime.now().isoformat())
            cache.set_meta("is_warming_up", "false")
            logger.info(f"[SectorWarmup] 预热完成 {completed}/{len(sectors_to_warmup)} 个板块")
        except Exception as e:
            logger.error(f"[SectorWarmup] 预热失败: {e}")
            try:
                from src.services.sector_cache_service import get_sector_cache
                get_sector_cache().set_meta("is_warming_up", "false")
            except Exception:
                pass

    thread = threading.Thread(target=_warmup_worker, daemon=True, name="sector-warmup")
    thread.start()
    logger.info(f"[SectorWarmup] 后台预热线程已启动，{delay_seconds}s 后开始")
