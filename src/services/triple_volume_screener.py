# -*- coding: utf-8 -*-
"""
Triple Volume Screener - 三倍量战法选股服务

基于通达信三倍量战法公式实现的A股选股器。
两阶段筛选：实时行情预筛选 → K线数据细筛。
"""
from __future__ import annotations

import logging
import time
from concurrent.futures import ThreadPoolExecutor, wait
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from data_provider.base import DataFetcherManager, normalize_stock_code

logger = logging.getLogger(__name__)

# _detailed_screen 的 df 哨兵：区分"未预取（需单股兜底）"与"预取失败(None)"
_KLINE_UNSET = object()


@dataclass
class TripleVolumeCandidate:
    code: str = ""
    name: str = ""
    price: float = 0.0
    change_pct: float = 0.0
    turnover_rate: float = 0.0
    volume: float = 0.0
    volume_ratio: float = 0.0
    avg_vol_5: float = 0.0
    ma5: float = 0.0
    ma10: float = 0.0
    ma20: float = 0.0
    open_price: float = 0.0
    close_price: float = 0.0
    range_60d_pct: float = 0.0
    pass_volume: bool = False
    pass_change: bool = False
    pass_turnover: bool = False
    pass_position: bool = False
    pass_ma_alignment: bool = False
    pass_solid_yang: bool = False
    score: int = 0


@dataclass
class TripleVolumeResult:
    date: str = ""
    total_scanned: int = 0
    after_prescreen: int = 0
    after_detailed: int = 0
    candidates: List[TripleVolumeCandidate] = field(default_factory=list)
    elapsed_seconds: float = 0.0


class TripleVolumeScreener:
    """三倍量战法选股器"""

    def __init__(
        self,
        data_manager: Optional[DataFetcherManager] = None,
        min_volume_ratio: float = 3.0,
        min_change_pct: float = 5.0,
        min_turnover_rate: float = 3.0,
        max_range_60d_pct: float = 50.0,
        kline_days: int = 60,
    ):
        self.data_manager = data_manager or DataFetcherManager()
        self.min_volume_ratio = min_volume_ratio
        self.min_change_pct = min_change_pct
        self.min_turnover_rate = min_turnover_rate
        self.max_range_60d_pct = max_range_60d_pct
        self.kline_days = kline_days
        self._turnover_available: bool = True  # 由 _fetch_all_a_stocks 设置

    def screen(
        self,
        stock_codes: Optional[List[str]] = None,
        max_detailed: int = 100,
    ) -> TripleVolumeResult:
        """执行三倍量战法选股

        Args:
            stock_codes: 限定选股范围，None 表示全市场
            max_detailed: 进入细筛的最大股票数（按涨幅降序取前N只），避免全市场细筛过慢
        """
        t0 = time.time()
        today = datetime.now().strftime("%Y-%m-%d")

        all_stocks = self._fetch_all_a_stocks()
        total_scanned = len(all_stocks)
        if total_scanned == 0:
            return TripleVolumeResult(date=today, total_scanned=0)

        if stock_codes:
            codes_normalized = {normalize_stock_code(c) for c in stock_codes}
            all_stocks = [s for s in all_stocks if normalize_stock_code(s.get("code", "")) in codes_normalized]
            total_scanned = len(all_stocks)
            if total_scanned == 0:
                return TripleVolumeResult(date=today, total_scanned=0)

        prescreened = self._prescreen(all_stocks)
        after_prescreen = len(prescreened)
        if not prescreened:
            return TripleVolumeResult(
                date=today,
                total_scanned=total_scanned,
                after_prescreen=0,
                elapsed_seconds=time.time() - t0,
            )

        if len(prescreened) > max_detailed:
            prescreened.sort(key=lambda s: self._safe_get(s, "change_pct"), reverse=True)
            skipped = len(prescreened) - max_detailed
            prescreened = prescreened[:max_detailed]
            logger.info("细筛限流: 跳过 %d 只低涨幅股 (保留前%d)", skipped, max_detailed)

        # 批量并行预取K线（仿 StockScreenerService 线程池范式），替代逐股串行拉取
        df_map = self._prefetch_daily_klines(prescreened)
        candidates = []
        for stock in prescreened:
            code = stock.get("code", "")
            if code in df_map:
                candidate = self._detailed_screen(stock, df=df_map[code])
            else:
                candidate = self._detailed_screen(stock)  # 预取未覆盖（超时截断）→ 单股兜底
            if candidate and self._passes_all(candidate):
                candidates.append(candidate)

        candidates.sort(key=lambda c: c.score, reverse=True)

        elapsed = time.time() - t0
        logger.info(
            "三倍量战法选股完成: scanned=%d, prescreened=%d, candidates=%d, elapsed=%.1fs",
            total_scanned, after_prescreen, len(candidates), elapsed,
        )

        return TripleVolumeResult(
            date=today,
            total_scanned=total_scanned,
            after_prescreen=after_prescreen,
            after_detailed=len(candidates),
            candidates=candidates,
            elapsed_seconds=round(elapsed, 1),
        )

    def _fetch_all_a_stocks(self) -> List[Dict[str, Any]]:
        """获取全A股实时行情（多数据源 fallback 链）"""
        # 路径1: DataFetcherManager（优先走缓存批量数据，含 fallback 链）
        try:
            stocks = self.data_manager.get_all_a_stock_realtime()
            if stocks:
                self._turnover_available = True
                logger.info("[三倍量] DataFetcherManager 获取 %d 只股票", len(stocks))
                return stocks
        except Exception as e:
            logger.debug("[三倍量] DataFetcherManager 全市场获取失败, 回退直连: %s", e)

        # 路径2: 直连 ak.stock_zh_a_spot_em()（东方财富，带重试）
        import akshare as ak

        for attempt in range(1, 4):
            try:
                api_start = time.time()
                df = ak.stock_zh_a_spot_em()
                api_elapsed = time.time() - api_start
                self._turnover_available = True
                logger.info("ak.stock_zh_a_spot_em 获取 %d 只股票, 耗时 %.2fs", len(df), api_elapsed)
                stocks = []
                for _, row in df.iterrows():
                    stocks.append({
                        "code": str(row.get("代码", "")),
                        "name": str(row.get("名称", "")),
                        "price": _safe_float(row.get("最新价")),
                        "change_pct": _safe_float(row.get("涨跌幅")),
                        "turnover_rate": _safe_float(row.get("换手率")),
                        "volume": _safe_float(row.get("成交量")),
                    })
                return stocks
            except Exception as e:
                logger.debug("[三倍量] 东财接口失败 (attempt %d/3): %s", attempt, e)
                if attempt < 3:
                    time.sleep(min(2 ** attempt, 5))

        # 路径2.5: Tushare pro_api（快速、稳定，含涨跌幅+换手率）
        try:
            from src.config import get_config
            config = get_config()
            if config.tushare_token:
                import tushare as ts
                ts.set_token(config.tushare_token)
                pro = ts.pro_api()

                today = datetime.now()
                for offset in range(5):
                    date_str = (today - pd.Timedelta(days=offset)).strftime("%Y%m%d")
                    try:
                        df_daily = pro.daily(trade_date=date_str)
                        if df_daily is not None and not df_daily.empty:
                            break
                    except Exception:
                        continue
                else:
                    raise RuntimeError("Tushare daily() 近5日无数据")

                df_basic = None
                for offset in range(5):
                    date_str = (today - pd.Timedelta(days=offset)).strftime("%Y%m%d")
                    try:
                        df_basic = pro.daily_basic(trade_date=date_str)
                        if df_basic is not None and not df_basic.empty:
                            break
                    except Exception:
                        continue

                if df_basic is not None and not df_basic.empty:
                    df_daily = df_daily.merge(
                        df_basic[["ts_code", "turnover_rate"]],
                        on="ts_code", how="left",
                    )
                    df_daily["turnover_rate"] = df_daily["turnover_rate"].fillna(0)
                    self._turnover_available = True
                else:
                    df_daily["turnover_rate"] = 0.0
                    self._turnover_available = False
                stocks = []
                for _, row in df_daily.iterrows():
                    code = str(row["ts_code"]).split(".")[0]
                    stocks.append({
                        "code": code,
                        "name": code,
                        "price": _safe_float(row.get("close")),
                        "change_pct": _safe_float(row.get("pct_chg")),
                        "turnover_rate": _safe_float(row.get("turnover_rate")),
                        "volume": _safe_float(row.get("vol")),
                    })
                logger.info("[三倍量] Tushare 获取 %d 只股票", len(stocks))
                return stocks
        except Exception as e:
            logger.debug("[三倍量] Tushare 数据源失败: %s", e)

        # 路径3: ak.stock_zh_a_spot()（新浪，兜底；缺少换手率字段）
        try:
            api_start = time.time()
            df = ak.stock_zh_a_spot()
            api_elapsed = time.time() - api_start
            self._turnover_available = False
            logger.warning(
                "[三倍量] 东财接口不可用，使用新浪数据源获取 %d 只股票（耗时 %.1fs）。注意：新浪不含换手率字段，"
                "预筛和细筛将跳过换手率检查。",
                len(df), api_elapsed,
            )
            stocks = []
            for _, row in df.iterrows():
                stocks.append({
                    "code": str(row.get("代码", "")),
                    "name": str(row.get("名称", "")),
                    "price": _safe_float(row.get("最新价")),
                    "change_pct": _safe_float(row.get("涨跌幅")),
                    "turnover_rate": 0.0,
                    "volume": _safe_float(row.get("成交量")),
                })
            return stocks
        except Exception as e:
            logger.warning("[三倍量] 所有数据源均失败: %s", e)
            return []

    def _prescreen(self, stocks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """实时行情预筛选：涨跌幅 + 换手率（新浪兜底时跳过换手率检查）"""
        result = []
        for s in stocks:
            change_pct = self._safe_get(s, "change_pct")
            if change_pct < self.min_change_pct:
                continue
            if self._turnover_available:
                turnover = self._safe_get(s, "turnover_rate")
                if turnover < self.min_turnover_rate:
                    continue
            result.append(s)

        if self._turnover_available:
            logger.info("预筛选: %d/%d 通过 (涨幅>=%.0f%%, 换手>=%.0f%%)",
                        len(result), len(stocks), self.min_change_pct, self.min_turnover_rate)
        else:
            logger.info("预筛选: %d/%d 通过 (涨幅>=%.0f%%, 换手率数据不可用-跳过检查)",
                        len(result), len(stocks), self.min_change_pct)
        return result

    def _fetch_one_kline(self, code: str):
        """单股拉取 kline_days 日K线，失败返回 None。"""
        try:
            df, _source = self.data_manager.get_daily_data(code, days=self.kline_days)
            return df
        except Exception as e:
            logger.debug("获取 %s K线数据失败: %s", code, e)
            return None

    def _prefetch_daily_klines(
        self, stocks: List[Dict[str, Any]], timeout: float = 140.0
    ) -> Dict[str, Any]:
        """并行预取K线，返回 {code: DataFrame|None}。

        ThreadPoolExecutor + deadline 轮询范式与 StockScreenerService._parallel_fetch_daily_data
        一致；超时未完成的代码不入 map，由 _detailed_screen 走单股兜底。
        """
        df_map: Dict[str, Any] = {}
        codes = [c for c in dict.fromkeys(s.get("code", "") for s in stocks) if c]
        if not codes:
            return df_map
        deadline = time.monotonic() + timeout
        with ThreadPoolExecutor(max_workers=min(5, len(codes))) as executor:
            futures = {executor.submit(self._fetch_one_kline, code): code for code in codes}
            pending = set(futures)
            while pending:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    logger.warning("K线预取超时，%d 只未完成", len(pending))
                    break
                done, pending = wait(pending, timeout=min(5.0, remaining))
                for future in done:
                    code = futures[future]
                    try:
                        df_map[code] = future.result(timeout=1)
                    except Exception:
                        df_map[code] = None
            for future in pending:
                future.cancel()
        return df_map

    def _detailed_screen(
        self, stock: Dict[str, Any], df: Any = _KLINE_UNSET
    ) -> Optional[TripleVolumeCandidate]:
        """K线数据细筛：成交量、均线、位置、阳线检查

        Args:
            df: 批量预取的K线；显式传入（含 None=取数失败）时不再单股重拉，
                未传（哨兵，如预取超时未覆盖该股）时走单股兜底拉取
        """
        code = stock.get("code", "")
        name = stock.get("name", "")
        if not code:
            return None

        if df is _KLINE_UNSET:
            df = self._fetch_one_kline(code)
        if df is None or df.empty or len(df) < 20:
            return None

        latest = df.iloc[-1]
        close = latest.get("close", 0)
        open_p = latest.get("open", 0)
        volume = latest.get("volume", 0)
        volume_ratio = latest.get("volume_ratio", 1.0)
        ma5 = latest.get("ma5", 0)
        ma10 = latest.get("ma10", 0)
        ma20 = latest.get("ma20", 0)

        if close <= 0:
            return None

        avg_vol_5 = float(df["volume"].tail(6).head(5).mean()) if len(df) >= 6 else 0
        pass_volume = (avg_vol_5 > 0 and volume >= avg_vol_5 * self.min_volume_ratio)
        pass_change = self._safe_get(stock, "change_pct") >= self.min_change_pct
        pass_turnover = (self._safe_get(stock, "turnover_rate") >= self.min_turnover_rate) if self._turnover_available else True

        hhv_60 = float(df["high"].tail(self.kline_days).max())
        llv_60 = float(df["low"].tail(self.kline_days).min())
        range_60d = ((hhv_60 - llv_60) / llv_60 * 100) if llv_60 > 0 else 0
        pass_position = range_60d <= self.max_range_60d_pct
        pass_ma = (ma5 > ma10 > ma20) if (ma5 and ma10 and ma20) else False
        pass_yang = open_p < close if open_p > 0 else False

        score = sum([pass_volume, pass_change, pass_turnover, pass_position, pass_ma, pass_yang])

        return TripleVolumeCandidate(
            code=code,
            name=name,
            price=self._safe_get(stock, "price"),
            change_pct=self._safe_get(stock, "change_pct"),
            turnover_rate=self._safe_get(stock, "turnover_rate"),
            volume=volume,
            volume_ratio=round(float(volume_ratio), 2),
            avg_vol_5=round(float(avg_vol_5), 0),
            ma5=round(float(ma5), 2),
            ma10=round(float(ma10), 2),
            ma20=round(float(ma20), 2),
            open_price=round(float(open_p), 2),
            close_price=round(float(close), 2),
            range_60d_pct=round(range_60d, 1),
            pass_volume=pass_volume,
            pass_change=pass_change,
            pass_turnover=pass_turnover,
            pass_position=pass_position,
            pass_ma_alignment=pass_ma,
            pass_solid_yang=pass_yang,
            score=score,
        )

    @staticmethod
    def _safe_get(d: Dict[str, Any], key: str) -> float:
        return _safe_float(d.get(key, 0))

    @staticmethod
    def _passes_all(c: TripleVolumeCandidate) -> bool:
        return c.score >= 3


def _safe_float(val: Any) -> float:
    if val is None:
        return 0.0
    try:
        v = float(val)
        return 0.0 if (v != v) else v
    except (ValueError, TypeError):
        return 0.0
