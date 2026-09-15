# -*- coding: utf-8 -*-
"""
Oversold Bounce Screener - 超跌反弹战法选股服务

基于恐慌情绪的超跌反弹选股器。
核心逻辑：大盘恐慌 + 个股超跌 = 出击时刻。
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from data_provider.base import DataFetcherManager, normalize_stock_code

logger = logging.getLogger(__name__)


@dataclass
class OversoldCandidate:
    code: str = ""
    name: str = ""
    price: float = 0.0
    today_drop_pct: float = 0.0
    n_day_drop_pct: float = 0.0
    bias_from_ma5: float = 0.0
    turnover_rate: float = 0.0
    volume: float = 0.0
    pass_drop: bool = False
    pass_bias: bool = False
    pass_volume: bool = False
    pass_position: bool = False
    pass_solid_yin: bool = False
    pass_panic: bool = False
    score: int = 0


@dataclass
class OversoldBounceResult:
    date: str = ""
    market_panic: bool = False
    total_scanned: int = 0
    after_detailed: int = 0
    candidates: List[OversoldCandidate] = field(default_factory=list)
    elapsed_seconds: float = 0.0


class OversoldBounceScreener:
    """超跌反弹战法选股器"""

    def __init__(
        self,
        data_manager: Optional[DataFetcherManager] = None,
        lookback_days: int = 5,
        min_drop_pct: float = 20.0,
        max_bias_pct: float = -8.0,
        min_turnover_rate: float = 3.0,
        kline_days: int = 60,
    ):
        self.data_manager = data_manager or DataFetcherManager()
        self.lookback_days = lookback_days
        self.min_drop_pct = min_drop_pct
        self.max_bias_pct = max_bias_pct
        self.min_turnover_rate = min_turnover_rate
        self.kline_days = kline_days

    def screen(self, max_detailed: int = 100) -> OversoldBounceResult:
        """执行超跌反弹选股

        Args:
            max_detailed: 进入细筛的最大股票数
        """
        t0 = time.time()
        today = datetime.now().strftime("%Y-%m-%d")

        # 检查大盘恐慌状态
        market_panic = self._check_market_panic()

        # 获取全A股实时行情
        all_stocks = self._fetch_all_a_stocks()
        total_scanned = len(all_stocks)
        if total_scanned == 0:
            return OversoldBounceResult(date=today, total_scanned=0, market_panic=market_panic)

        # 预筛选：今日下跌的股票
        prescreened = self._prescreen(all_stocks)
        if not prescreened:
            return OversoldBounceResult(
                date=today,
                total_scanned=total_scanned,
                market_panic=market_panic,
                elapsed_seconds=time.time() - t0,
            )

        # 限流：按跌幅排序取前N只
        if len(prescreened) > max_detailed:
            prescreened.sort(key=lambda s: self._safe_get(s, "change_pct"))
            prescreened = prescreened[:max_detailed]

        # 细筛
        candidates = []
        for stock in prescreened:
            candidate = self._detailed_screen(stock)
            if candidate and candidate.score >= 3:
                candidates.append(candidate)

        # 按评分排序
        candidates.sort(key=lambda c: c.score, reverse=True)

        elapsed = time.time() - t0
        logger.info(
            "超跌反弹选股完成: market_panic=%s, scanned=%d, candidates=%d, elapsed=%.1fs",
            market_panic, total_scanned, len(candidates), elapsed,
        )

        return OversoldBounceResult(
            date=today,
            market_panic=market_panic,
            total_scanned=total_scanned,
            after_detailed=len(candidates),
            candidates=candidates,
            elapsed_seconds=round(elapsed, 1),
        )

    def _check_market_panic(self) -> bool:
        """检查大盘是否处于恐慌状态

        恐慌条件：
        1. 上证指数连续下跌3天以上
        2. 当日大阴线（跌幅>1.5%）
        3. 指数远离5日线（乖离率<-2%）
        """
        try:
            df, _ = self.data_manager.get_daily_data("000001", days=10)
            if df is None or df.empty or len(df) < 5:
                return False

            close = df["close"].values
            ma5 = np.mean(close[-5:])

            # 检查连续下跌天数
            consecutive_down = 0
            for i in range(len(close) - 1, 0, -1):
                if close[i] < close[i - 1]:
                    consecutive_down += 1
                else:
                    break

            # 当日跌幅
            today_change = (close[-1] / close[-2] - 1) * 100 if len(close) >= 2 else 0

            # 5日线乖离率
            bias_pct = (close[-1] / ma5 - 1) * 100 if ma5 > 0 else 0

            is_panic = (
                consecutive_down >= 3
                and today_change < -1.5
                and bias_pct < -2.0
            )

            logger.info(
                "[超跌反弹] 大盘恐慌检查: 连跌%d天, 当日%.2f%%, 5日线乖离%.2f%%, 恐慌=%s",
                consecutive_down, today_change, bias_pct, is_panic,
            )
            return is_panic

        except Exception as e:
            logger.warning("[超跌反弹] 大盘恐慌检查失败: %s", e)
            return False

    def _fetch_all_a_stocks(self) -> List[Dict[str, Any]]:
        """获取全A股实时行情"""
        try:
            stocks = self.data_manager.get_all_a_stock_realtime()
            if stocks:
                logger.info("[超跌反弹] DataFetcherManager 获取 %d 只股票", len(stocks))
                return stocks
        except Exception as e:
            logger.debug("[超跌反弹] DataFetcherManager 失败, 回退直连: %s", e)

        # 直连 akshare
        import akshare as ak
        for attempt in range(1, 4):
            try:
                df = ak.stock_zh_a_spot_em()
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
                logger.debug("[超跌反弹] 东财接口失败 (attempt %d/3): %s", attempt, e)
                if attempt < 3:
                    time.sleep(min(2 ** attempt, 5))

        return []

    def _prescreen(self, stocks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """预筛选：今日下跌的股票"""
        result = []
        for s in stocks:
            change_pct = self._safe_get(s, "change_pct")
            if change_pct < 0:  # 今日下跌
                result.append(s)
        logger.info("[超跌反弹] 预筛选: %d/%d 通过 (今日下跌)", len(result), len(stocks))
        return result

    def _detailed_screen(self, stock: Dict[str, Any]) -> Optional[OversoldCandidate]:
        """细筛：跌幅、乖离率、换手率等"""
        code = stock.get("code", "")
        name = stock.get("name", "")
        if not code:
            return None

        try:
            df, _ = self.data_manager.get_daily_data(code, days=self.kline_days)
            if df is None or df.empty or len(df) < self.lookback_days:
                return None
        except Exception as e:
            logger.debug("获取 %s K线数据失败: %s", code, e)
            return None

        close = df["close"].values
        today_close = close[-1]
        if today_close <= 0:
            return None

        # N日跌幅
        past_close = close[-self.lookback_days - 1] if len(close) > self.lookback_days else close[0]
        n_day_drop = (today_close / past_close - 1) * 100 if past_close > 0 else 0

        # 5日线乖离率
        ma5 = np.mean(close[-5:])
        bias_from_ma5 = (today_close / ma5 - 1) * 100 if ma5 > 0 else 0

        # 今日跌幅
        prev_close = close[-2] if len(close) >= 2 else today_close
        today_drop = (today_close / prev_close - 1) * 100 if prev_close > 0 else 0

        # 换手率
        turnover_rate = self._safe_get(stock, "turnover_rate")

        # 检查条件
        pass_drop = n_day_drop <= -self.min_drop_pct
        pass_bias = bias_from_ma5 <= self.max_bias_pct
        pass_turnover = turnover_rate >= self.min_turnover_rate
        pass_position = True  # 超跌本身就是位置条件

        # 实体阴线（收盘价低于开盘价）
        open_p = df["open"].values[-1]
        pass_solid_yin = open_p > today_close if open_p > 0 else False

        # 恐慌盘（放量下跌）
        vol = df["volume"].values
        avg_vol_5 = np.mean(vol[-6:-1]) if len(vol) >= 6 else np.mean(vol[-5:])
        current_vol = vol[-1]
        pass_panic = current_vol > avg_vol_5 * 1.5 if avg_vol_5 > 0 else False

        score = sum([pass_drop, pass_bias, pass_turnover, pass_position, pass_solid_yin, pass_panic])

        return OversoldCandidate(
            code=code,
            name=name,
            price=round(today_close, 2),
            today_drop_pct=round(today_drop, 2),
            n_day_drop_pct=round(n_day_drop, 2),
            bias_from_ma5=round(bias_from_ma5, 2),
            turnover_rate=round(turnover_rate, 2),
            volume=float(current_vol),
            pass_drop=pass_drop,
            pass_bias=pass_bias,
            pass_volume=pass_panic,
            pass_position=pass_position,
            pass_solid_yin=pass_solid_yin,
            pass_panic=pass_panic,
            score=score,
        )

    @staticmethod
    def _safe_get(d: Dict[str, Any], key: str) -> float:
        return _safe_float(d.get(key, 0))


def _safe_float(val: Any) -> float:
    if val is None:
        return 0.0
    try:
        v = float(val)
        return 0.0 if (v != v) else v
    except (ValueError, TypeError):
        return 0.0
