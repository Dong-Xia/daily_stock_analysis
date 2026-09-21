# -*- coding: utf-8 -*-
"""
===================================
市场状态分类器（Market Regime Classifier）
===================================

职责：
1. 获取指数日线数据（上证/深证/创业板）
2. 从趋势、量能、宽度、波动率、情绪五个维度分析市场状态
3. 综合加权输出 7 种市场阶段（MarketRegime）及置信度、仓位建议

设计：
- 纯同步模块，不依赖 asyncio
- 不引用 src.core.pipeline 以避免循环依赖
- 各维度可独立测试，静态方法可脱离 DataManager 运行
"""

import logging
from collections import Counter
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from data_provider.base import DataFetcherManager, normalize_stock_code
from src.schemas.stock_screener_schema import (
    DimensionEvidence,
    MarketRegime,
    RegimeResult,
    get_position_factor_range,
    get_regime_label,
    get_regime_recommendation,
)

logger = logging.getLogger(__name__)

# 默认指数代码：上证综指 / 深证成指 / 创业板指
_DEFAULT_INDICES = ["000001", "399001", "399006"]

# 上证综指代码为 000001，但与平安银行(000001.SZ)代码空间冲突：
# get_daily_data("000001") 会按个股优先解析，返回平安银行而非上证指数。
# 故上证指数需走 get_index_daily_data（指数专用入口）。
# 深证成指(399001)/创业板指(399006)在 399xxx 指数区间，不与个股冲突，可继续用 get_daily_data。
_SSE_INDEX_CODE = "000001"

# 维度默认权重
_DEFAULT_DIMENSION_WEIGHTS: Dict[str, float] = {
    "trend": 0.35,
    "volume": 0.20,
    "breadth": 0.20,
    "volatility": 0.10,
    "sentiment": 0.15,
}


def _interpolate_position_factor(composite_score: float, pf_range: Tuple[float, float]) -> float:
    """在给定仓位范围内插值。"""
    lo, hi = pf_range
    factor = lo + (composite_score / 100.0) * (hi - lo)
    return round(max(0.0, min(1.0, factor)), 2)


def _clamp(value: float, lo: float = 0.0, hi: float = 100.0) -> int:
    return int(max(lo, min(hi, value)))


class MarketRegimeClassifier:
    """程序化市场阶段分类器。

    使用指数的 MA/成交量/宽度/波动率/情绪数据，将市场划分为 7 个阶段，
    输出综合置信度与仓位建议因子。
    """

    def __init__(
        self,
        data_manager: Optional[DataFetcherManager] = None,
        ma_short: int = 5,
        ma_mid: int = 10,
        ma_long: int = 20,
        ma_trend: int = 60,
        volume_short: int = 5,
        volume_long: int = 20,
        dimension_weights: Optional[Dict[str, float]] = None,
    ):
        self.data_manager = data_manager or DataFetcherManager()
        self.ma_short = ma_short
        self.ma_mid = ma_mid
        self.ma_long = ma_long
        self.ma_trend = ma_trend
        self.volume_short = volume_short
        self.volume_long = volume_long
        self.dimension_weights = dimension_weights or dict(_DEFAULT_DIMENSION_WEIGHTS)
        self._logger = logger

    # ================================================================
    # 主入口
    # ================================================================

    def classify(
        self,
        indices: Optional[List[str]] = None,
        date: Optional[str] = None,
    ) -> RegimeResult:
        """执行市场状态分类。

        Args:
            indices: 指数代码列表，默认上证/深证/创业板。
            date: 分析日期 YYYY-MM-DD，默认今天。

        Returns:
            RegimeResult: 包含市场阶段、置信度、仓位建议和各维度证据。
        """
        indices = indices or list(_DEFAULT_INDICES)

        # 1. 获取指数数据
        dfs = self._fetch_index_data(indices, date)
        if not dfs:
            self._logger.warning("[市场状态] 未获取到指数数据，返回默认 RANGE_BOUND")
            return RegimeResult(
                regime=MarketRegime.RANGE_BOUND,
                regime_label=get_regime_label(MarketRegime.RANGE_BOUND),
                confidence=30,
                position_factor=0.30,
                recommendation=get_regime_recommendation(MarketRegime.RANGE_BOUND),
                evidence=[
                    DimensionEvidence(
                        dimension="trend",
                        score=50,
                        signal="neutral",
                        detail="无数据: 默认中立",
                    )
                ],
            )

        # 2. 逐个维度计算
        evidence_list: List[DimensionEvidence] = []
        scores: Dict[str, float] = {}
        signals: Dict[str, str] = {}

        # 趋势
        trend_ev = self._compute_trend(dfs)
        evidence_list.append(trend_ev)
        scores["trend"] = trend_ev.score
        signals["trend"] = trend_ev.signal

        # 量能
        volume_ev = self._compute_volume(dfs)
        evidence_list.append(volume_ev)
        scores["volume"] = volume_ev.score

        # 宽度
        breadth_ev = self._compute_breadth(dfs)
        evidence_list.append(breadth_ev)
        scores["breadth"] = breadth_ev.score

        # 波动率
        volatility_ev = self._compute_volatility(dfs)
        evidence_list.append(volatility_ev)
        scores["volatility"] = volatility_ev.score

        # 情绪
        sentiment_ev = self._compute_sentiment(dfs)
        evidence_list.append(sentiment_ev)
        scores["sentiment"] = sentiment_ev.score
        signals["sentiment"] = sentiment_ev.signal

        # 3. 综合输出
        regime, confidence, position_factor = self._composite_to_regime(
            scores, self.dimension_weights, signals
        )

        return RegimeResult(
            regime=regime,
            regime_label=get_regime_label(regime),
            confidence=confidence,
            position_factor=position_factor,
            recommendation=get_regime_recommendation(regime),
            evidence=evidence_list,
        )

    # ================================================================
    # 数据获取
    # ================================================================

    def _fetch_index_data(
        self, indices: List[str], date: Optional[str]
    ) -> Dict[str, pd.DataFrame]:
        """批量获取指数日线数据。"""
        dfs: Dict[str, pd.DataFrame] = {}
        for code in indices:
            try:
                if normalize_stock_code(code) == _SSE_INDEX_CODE:
                    # 上证综指与平安银行代码冲突，走指数专用入口
                    df = self.data_manager.get_index_daily_data(code, end_date=date, days=120)
                else:
                    df, _ = self.data_manager.get_daily_data(code, end_date=date, days=120)
                if df is not None and not df.empty and len(df) >= 20:
                    dfs[code] = df
                else:
                    self._logger.warning("[市场状态] %s 数据不足", code)
            except Exception as e:
                self._logger.warning("[市场状态] %s 获取失败: %s", code, e)
        return dfs

    # ================================================================
    # 维度计算
    # ================================================================

    def _compute_trend(self, dfs: Dict[str, pd.DataFrame]) -> DimensionEvidence:
        """计算趋势维度：MA 排列和斜率。

        对每个指数计算 MA5/MA10/MA20/MA60，转换为相对 MA60 的百分比，
        调用 _classify_trend_regime 获得信号和得分，跨指数聚合。
        """
        scores: List[int] = []
        signals: List[str] = []
        details: List[str] = []

        for code, df in dfs.items():
            if df.empty or len(df) < self.ma_trend:
                continue

            close = df["close"].values
            ma5 = np.mean(close[-self.ma_short :]) if len(close) >= self.ma_short else close[-1]
            ma10 = np.mean(close[-self.ma_mid :]) if len(close) >= self.ma_mid else close[-1]
            ma20 = np.mean(close[-self.ma_long :]) if len(close) >= self.ma_long else close[-1]
            ma60 = np.mean(close[-self.ma_trend :]) if len(close) >= self.ma_trend else close[-1]

            ma5_pct = (ma5 / ma60 - 1) * 100 if ma60 != 0 else 0.0
            ma10_pct = (ma10 / ma60 - 1) * 100 if ma60 != 0 else 0.0
            ma20_pct = (ma20 / ma60 - 1) * 100 if ma60 != 0 else 0.0

            signal, score, _ = self._classify_trend_regime(ma5_pct, ma10_pct, ma20_pct, 0.0)
            scores.append(score)
            signals.append(signal)

            # MA5 斜率
            ma5_series = df["close"].rolling(self.ma_short).mean().dropna()
            slope_info = ""
            if len(ma5_series) >= 5:
                slope = self._calc_ma_slope(ma5_series, window=5)
                slope_info = f", slope={slope:.4f}"

            details.append(f"{code}: {signal}(score={score}{slope_info})")

        if not scores:
            return DimensionEvidence(
                dimension="trend",
                score=50,
                signal="neutral",
                detail="趋势分析: 无有效数据",
            )

        avg_score = _clamp(np.mean(scores))
        signal_counts = Counter(signals)
        main_signal = signal_counts.most_common(1)[0][0]

        return DimensionEvidence(
            dimension="trend",
            score=avg_score,
            signal=main_signal,
            detail="趋势分析: " + "; ".join(details),
        )

    def _compute_volume(self, dfs: Dict[str, pd.DataFrame]) -> DimensionEvidence:
        """计算量能维度：短期均量 vs 长期均量。

        5日均量 / 20日均量，比值 > 1.2 放量，< 0.8 缩量。
        """
        ratios: List[float] = []
        details: List[str] = []

        for code, df in dfs.items():
            if df.empty or len(df) < self.volume_long + 5:
                continue
            volume = df["volume"].values
            vol_short = np.mean(volume[-self.volume_short :])
            vol_long_slice = volume[-self.volume_long : -self.volume_short]
            if len(vol_long_slice) < 2:
                vol_long = np.mean(volume[-self.volume_long :])
            else:
                vol_long = np.mean(vol_long_slice)

            ratio = vol_short / vol_long if vol_long > 0 else 1.0
            ratios.append(ratio)
            details.append(f"{code}: vol_ratio={ratio:.2f}")

        if not ratios:
            return DimensionEvidence(
                dimension="volume", score=50, signal="neutral", detail="量能分析: 无有效数据"
            )

        avg_ratio = float(np.mean(ratios))
        if avg_ratio > 1.2:
            score = _clamp(80 + (avg_ratio - 1.2) / 0.8 * 20)
            signal = "high"
        elif avg_ratio > 1.0:
            score = _clamp(50 + (avg_ratio - 1.0) / 0.2 * 30)
            signal = "normal_high"
        elif avg_ratio > 0.8:
            score = _clamp(30 + (avg_ratio - 0.8) / 0.2 * 20)
            signal = "normal_low"
        else:
            score = _clamp(30 - (0.8 - avg_ratio) / 0.8 * 30)
            signal = "low"

        return DimensionEvidence(
            dimension="volume",
            score=_clamp(score),
            signal=signal,
            detail="量能分析: " + "; ".join(details),
        )

    def _compute_breadth(self, dfs: Dict[str, pd.DataFrame]) -> DimensionEvidence:
        """计算宽度维度：涨跌家数比。

        优先从 data_manager 的 fetcher 获取 get_market_stats()，
        不可用则用指数涨跌比例作为代理。
        """
        stats = self._try_get_market_stats()
        if stats is not None:
            return self._score_breadth_from_stats(stats)

        # 代理：指数上涨比例
        return self._score_breadth_from_indices(dfs)

    def _try_get_market_stats(self) -> Optional[Dict[str, Any]]:
        """尝试从可用 fetcher 获取市场统计。"""
        try:
            fetchers = self.data_manager._get_fetchers_snapshot()
            for fetcher in fetchers:
                try:
                    stats = fetcher.get_market_stats()
                    if stats and stats.get("up_count") is not None and stats.get("down_count") is not None:
                        return stats
                except Exception:
                    continue
        except Exception:
            pass
        return None

    def _score_breadth_from_stats(self, stats: Dict[str, Any]) -> DimensionEvidence:
        """根据市场涨跌统计计算宽度得分。"""
        up = int(stats.get("up_count", 0))
        down = int(stats.get("down_count", 0))
        total = up + down
        if total <= 0:
            return DimensionEvidence(
                dimension="breadth", score=50, signal="neutral", detail="宽度分析: 无涨跌数据"
            )

        up_ratio = up / total
        if up_ratio > 0.6:
            score = _clamp(50 + (up_ratio - 0.6) / 0.4 * 50)
            signal = "broad"
        elif up_ratio < 0.4:
            score = _clamp(50 - (0.4 - up_ratio) / 0.4 * 50)
            signal = "narrow"
        else:
            score = _clamp(50 + (up_ratio - 0.5) * 100)
            signal = "neutral"

        return DimensionEvidence(
            dimension="breadth",
            score=score,
            signal=signal,
            detail=f"涨跌比: {up}/{down} = {up_ratio:.1%}",
        )

    def _score_breadth_from_indices(self, dfs: Dict[str, pd.DataFrame]) -> DimensionEvidence:
        """用指数涨跌比例作为宽度代理评分。"""
        if not dfs:
            return DimensionEvidence(
                dimension="breadth", score=50, signal="neutral", detail="宽度分析: 无数据，默认中立"
            )

        up_count = sum(
            1 for _, df in dfs.items()
            if not df.empty and float(df["pct_chg"].iloc[-1]) > 0
        )
        ratio = up_count / len(dfs)
        score = _clamp(ratio * 100)
        return DimensionEvidence(
            dimension="breadth",
            score=score,
            signal="proxy",
            detail=f"指数上涨比例: {up_count}/{len(dfs)} = {ratio:.0%} (代理)",
        )

    def _compute_volatility(self, dfs: Dict[str, pd.DataFrame]) -> DimensionEvidence:
        """计算波动率维度：ATR 比值。

        ATR = max(high-low, |high-prev_close|, |low-prev_close|)，
        比较 5 日平均 ATR 和 20 日平均 ATR。
        ATR 扩张（>1.3x）→ 低分，ATR 收缩 → 高分。
        """
        atr_ratios: List[float] = []
        details: List[str] = []

        for code, df in dfs.items():
            if df.empty or len(df) < 25:
                continue
            high = df["high"].values
            low = df["low"].values
            close = df["close"].values

            prev_close = np.roll(close, 1)
            prev_close[0] = close[0]

            atr = np.maximum(
                high - low,
                np.maximum(np.abs(high - prev_close), np.abs(low - prev_close)),
            )
            atr_5 = np.mean(atr[-5:])
            atr_20 = np.mean(atr[-20:])

            atr_ratio = atr_5 / atr_20 if atr_20 > 0 else 1.0
            atr_ratios.append(atr_ratio)
            details.append(f"{code}: atr_ratio={atr_ratio:.2f}")

        if not atr_ratios:
            return DimensionEvidence(
                dimension="volatility", score=50, signal="neutral", detail="波动率分析: 无有效数据"
            )

        avg_ratio = float(np.mean(atr_ratios))
        if avg_ratio > 1.3:
            score = _clamp(50 - (avg_ratio - 1.3) / 0.7 * 50, 0, 100)
            signal = "high_vol"
        elif avg_ratio > 1.0:
            score = _clamp(50 - (avg_ratio - 1.0) / 0.3 * 20, 0, 100)
            signal = "elevated"
        elif avg_ratio > 0.7:
            score = _clamp(60 + (1.0 - avg_ratio) / 0.3 * 30, 0, 100)
            signal = "normal"
        else:
            score = _clamp(90 + (0.7 - avg_ratio) / 0.7 * 10, 0, 100)
            signal = "calm"

        return DimensionEvidence(
            dimension="volatility",
            score=_clamp(score),
            signal=signal,
            detail="波动率分析: " + "; ".join(details),
        )

    def _compute_sentiment(self, dfs: Dict[str, pd.DataFrame]) -> DimensionEvidence:
        """计算情绪维度：价格极端波动代理。

        用最近 10 个交易日中涨跌幅 > 2% 的天数占比作为情绪极端指标。
        占比高 → 情绪化市场 → 低分。
        """
        extreme_ratios: List[float] = []
        details: List[str] = []

        for code, df in dfs.items():
            if df.empty or len(df) < 10:
                continue
            pct_chg = df["pct_chg"].values[-10:]
            extreme_count = float(np.sum(np.abs(pct_chg) > 2.0))
            extreme_ratio = extreme_count / len(pct_chg)
            extreme_ratios.append(extreme_ratio)
            details.append(f"{code}: extreme_pct={extreme_ratio:.0%}")

        if not extreme_ratios:
            return DimensionEvidence(
                dimension="sentiment", score=50, signal="neutral", detail="情绪分析: 无有效数据"
            )

        avg_extreme = float(np.mean(extreme_ratios))
        if avg_extreme > 0.5:
            score = _clamp(40 - (avg_extreme - 0.5) / 0.5 * 40, 0, 100)
            signal = "extreme"
        elif avg_extreme > 0.3:
            score = _clamp(40 - (avg_extreme - 0.3) / 0.2 * 20, 0, 100)
            signal = "elevated"
        else:
            score = _clamp(60 + (0.3 - avg_extreme) / 0.3 * 40, 0, 100)
            signal = "calm"

        return DimensionEvidence(
            dimension="sentiment",
            score=_clamp(score),
            signal=signal,
            detail="情绪分析: " + "; ".join(details),
        )

    # ================================================================
    # 静态方法：纯逻辑，可脱离 DataManager 测试
    # ================================================================

    @staticmethod
    def _classify_trend_regime(
        ma5_pct: float, ma10_pct: float, ma20_pct: float, ma60_pct: float
    ) -> Tuple[str, int, int]:
        """分类趋势信号（纯静态逻辑）。

        根据 MA 相对 MA60 的百分比偏移判断趋势阶段。

        Args:
            ma5_pct:  (MA5 / MA60 - 1) * 100
            ma10_pct: (MA10 / MA60 - 1) * 100
            ma20_pct: (MA20 / MA60 - 1) * 100
            ma60_pct: (MA60 / MA60 - 1) * 100 → 约等于 0

        Returns:
            (signal_label, score_0to100, confidence_0to100)
        """
        # Bullish alignment: MA5 > MA10 > MA20 > MA60, all positive
        if ma5_pct > ma10_pct > ma20_pct > 0:
            magnitude = min(ma5_pct, 15.0) / 15.0
            score = int(70 + magnitude * 25)
            return "trending_up", _clamp(score, 0, 100), 80

        # Bearish alignment: MA5 < MA10 < MA20 < MA60, all negative
        if ma5_pct < ma10_pct < ma20_pct < 0:
            magnitude = min(abs(ma5_pct), 15.0) / 15.0
            score = int(30 - magnitude * 25)
            return "trending_down", _clamp(score, 0, 100), 80

        # Bottom reversal: MA5 crossing up through MA10 in downtrend
        if ma5_pct > ma10_pct and ma10_pct < ma20_pct and ma20_pct < 0:
            return "bottom_reversal", 55, 50

        # Top reversal: MA5 crossing down through MA10 in uptrend
        if ma5_pct < ma10_pct and ma10_pct > ma20_pct and ma20_pct > 0:
            return "top_reversal", 30, 50

        # Sideways: everything else
        avg_pct = (ma5_pct + ma10_pct + ma20_pct) / 3.0
        score = int(50 + avg_pct * 2)
        score = max(20, min(80, score))
        return "sideways", score, 50

    @staticmethod
    def _composite_to_regime(
        scores: Dict[str, float],
        weights: Dict[str, float],
        signals: Optional[Dict[str, str]] = None,
    ) -> Tuple[MarketRegime, int, float]:
        """综合各维度得分给出市场阶段判定。

        Args:
            scores: 维度→得分 (0-100)
            weights: 维度→权重
            signals: 可选的维度→额外信号（用于特殊案例识别）

        Returns:
            (regime, confidence_0to100, position_factor_0to1)
        """
        signals = signals or {}

        # 加权平均
        total_weight = sum(weights.get(d, 0.1) for d in scores if d in weights)
        if total_weight <= 0:
            weighted_score = 50.0
        else:
            weighted_score = sum(scores[d] * weights.get(d, 0.1) for d in scores) / total_weight

        weighted_score = max(0.0, min(100.0, weighted_score))

        # ---- 特殊案例 ----
        # 情绪极端 + 高波动 → EXTREME_SENTIMENT
        if scores.get("sentiment", 0) > 90 and scores.get("volatility", 0) > 85:
            regime = MarketRegime.EXTREME_SENTIMENT
        # 趋势底部反转信号 → BOTTOM_REVERSAL
        elif signals.get("trend") == "bottom_reversal":
            regime = MarketRegime.BOTTOM_REVERSAL
        else:
            # 常规映射
            if weighted_score >= 85:
                regime = MarketRegime.BULL_TREND
            elif weighted_score >= 70:
                regime = MarketRegime.BULL_CONSOLIDATION
            elif weighted_score >= 40:
                regime = MarketRegime.RANGE_BOUND
            elif weighted_score >= 25:
                regime = MarketRegime.BEAR_CONSOLIDATION
            else:
                regime = MarketRegime.BEAR_TREND

        # 仓位因子：在阶段范围内插值
        pf_min, pf_max = get_position_factor_range(regime)
        position_factor = _interpolate_position_factor(weighted_score, (pf_min, pf_max))

        confidence = int(round(weighted_score))
        confidence = max(0, min(100, confidence))

        return regime, confidence, position_factor

    @staticmethod
    def _calc_ma_slope(series: pd.Series, window: int = 3) -> float:
        """计算 MA 序列的线性回归斜率（经尾值归一化）。

        Args:
            series: MA 序列（pandas Series）
            window: 参与计算的最近点数

        Returns:
            float: 归一化斜率
        """
        valid = series.dropna()
        if len(valid) < window:
            return 0.0
        y = valid.iloc[-window:].values
        x = np.arange(window)
        slope = np.polyfit(x, y, 1)[0]
        if abs(y[-1]) > 1e-10:
            slope = slope / abs(y[-1])
        return float(slope)
