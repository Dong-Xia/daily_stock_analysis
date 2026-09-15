# -*- coding: utf-8 -*-
"""
热点板块预分析定时任务

职责：
1. 每个交易日收盘后（约 18:00）自动执行热点板块分析
2. 将分析结果存入 SectorAnalysisStorage
3. 非交易日自动跳过
"""

import logging
import threading
import time
from datetime import datetime, timedelta
from typing import Optional

logger = logging.getLogger(__name__)

_SCHEDULE_HOUR = 18
_SCHEDULE_MINUTE = 0
_CHECK_INTERVAL = 60


class SectorAnalysisScheduler:
    """热点板块预分析定时调度器（后台线程）"""

    def __init__(self):
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._last_run_date: Optional[str] = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            logger.info("[SectorScheduler] 已在运行，跳过启动")
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_loop, daemon=True, name="sector-scheduler")
        self._thread.start()
        logger.info(f"[SectorScheduler] 已启动，每日 {_SCHEDULE_HOUR:02d}:{_SCHEDULE_MINUTE:02d} 执行")

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=10)

    def _is_trading_day(self, check_date: str) -> bool:
        try:
            from src.core.trading_calendar import is_market_open
            from datetime import date as dt_date
            return is_market_open("cn", dt_date.fromisoformat(check_date))
        except Exception:
            return True

    def _get_latest_trading_day(self) -> str:
        today = datetime.now()
        check_date = today.strftime("%Y-%m-%d")
        for _ in range(7):
            if self._is_trading_day(check_date):
                return check_date
            today = today - timedelta(days=1)
            check_date = today.strftime("%Y-%m-%d")
        return datetime.now().strftime("%Y-%m-%d")

    def _run_analysis(self, force: bool = False) -> bool:
        today_system = datetime.now().strftime("%Y-%m-%d")
        trading_day = self._get_latest_trading_day()

        if not force:
            if trading_day != today_system:
                logger.info(f"[SectorScheduler] 今日 {today_system} 非交易日，最近交易日 {trading_day}")
                return False

        if trading_day == self._last_run_date and not force:
            logger.debug(f"[SectorScheduler] 今日已执行过，跳过")
            return False

        logger.info(f"[SectorScheduler] 开始执行热点分析: 交易日={trading_day}")
        try:
            from src.core.sector_analyzer import SectorAnalyzer
            from src.services.sector_analysis_storage import get_sector_analysis_storage

            storage = get_sector_analysis_storage()
            analyzer = SectorAnalyzer()

            # 当日爬虫涨停池可用时直接复用连板数（与 /sectors/hot 回退路径同一语义），fail-open
            scraper_limit_up_pool = None
            try:
                from src.services.board_scraper_storage import get_board_scraper_storage
                scraper_limit_up_pool = get_board_scraper_storage().get_limit_up_pool_by_date(trading_day) or None
            except Exception as e:
                logger.debug(f"[SectorScheduler] 读取爬虫涨停池失败（忽略）: {e}")

            hot_sectors = analyzer.analyze(
                top_n=20,
                min_limit_up=1,
                date=trading_day,
                allow_realtime_fetch=True,
                scraper_limit_up_pool=scraper_limit_up_pool,
            )

            hotspot_data = analyzer.fetch_hotspot_data()
            hotspot_summary = analyzer.build_hotspot_summary(hotspot_data)

            sectors_data = []
            for hs in hot_sectors:
                sectors_data.append(hs.to_dict() if hasattr(hs, "to_dict") else hs)

            from api.v1.schemas.sectors import HotSectorItem
            valid_sectors = []
            for item in sectors_data:
                try:
                    valid_sectors.append(HotSectorItem(**item).model_dump())
                except Exception:
                    pass

            result = {
                "date": trading_day,
                "sectors": valid_sectors,
                "total": len(valid_sectors),
                "cache_status": "pre_computed",
                "hotspot_summary": hotspot_summary,
                "analyzed_at": datetime.now().isoformat(),
            }
            storage.save(trading_day, result)
            self._last_run_date = trading_day
            logger.info(f"[SectorScheduler] 热点分析完成: {len(valid_sectors)} 个板块")
            return True
        except Exception as e:
            logger.error(f"[SectorScheduler] 分析失败: {e}", exc_info=True)
            return False

    def _run_loop(self) -> None:
        while not self._stop_event.is_set():
            now = datetime.now()
            if now.hour == _SCHEDULE_HOUR and now.minute >= _SCHEDULE_MINUTE:
                self._run_analysis()
                time.sleep(3600)
            else:
                time.sleep(_CHECK_INTERVAL)


def get_latest_trading_day() -> str:
    """返回最近一个交易日（YYYY-MM-DD），用于确定分析数据属于哪个交易日"""
    today = datetime.now()
    check_date = today.strftime("%Y-%m-%d")
    for _ in range(10):
        try:
            from src.core.trading_calendar import is_market_open
            from datetime import date as dt_date
            if is_market_open("cn", dt_date.fromisoformat(check_date)):
                return check_date
        except Exception:
            pass
        today = today - timedelta(days=1)
        check_date = today.strftime("%Y-%m-%d")
    return datetime.now().strftime("%Y-%m-%d")


_scheduler_instance: Optional[SectorAnalysisScheduler] = None


def start_sector_scheduler() -> None:
    global _scheduler_instance
    if _scheduler_instance is None:
        _scheduler_instance = SectorAnalysisScheduler()
    _scheduler_instance.start()


def stop_sector_scheduler() -> None:
    if _scheduler_instance:
        _scheduler_instance.stop()


def run_sector_analysis_now() -> bool:
    global _scheduler_instance
    if _scheduler_instance is None:
        _scheduler_instance = SectorAnalysisScheduler()
    return _scheduler_instance._run_analysis(force=True)
