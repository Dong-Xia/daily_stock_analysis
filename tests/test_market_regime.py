# -*- coding: utf-8 -*-
"""Tests for MarketRegimeClassifier — pure static methods + integration.

These tests do NOT call external APIs.  All instance-method tests use
synthetic pandas DataFrames with Mock data_manager.
"""

import logging
from typing import Any, Dict
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest

from src.core.market_regime import MarketRegimeClassifier
from src.schemas.stock_screener_schema import MarketRegime

logger = logging.getLogger(__name__)


# ====================================================================
#  _classify_trend_regime  —  pure static logic
# ====================================================================


class TestClassifyTrendRegime:
    """Tests for MarketRegimeClassifier._classify_trend_regime()."""

    def test_classify_trend_regime_bullish(self):
        """MA5>MA10>MA20>MA60, all positive → trending_up, high score."""
        signal, score, confidence = MarketRegimeClassifier._classify_trend_regime(
            ma5_pct=5.0, ma10_pct=3.0, ma20_pct=1.0, ma60_pct=0.0,
        )
        assert signal == "trending_up"
        assert 70 <= score <= 100
        assert confidence == 80

    def test_classify_trend_regime_bearish(self):
        """MA5<MA10<MA20<MA60, all negative → trending_down, low score."""
        signal, score, confidence = MarketRegimeClassifier._classify_trend_regime(
            ma5_pct=-5.0, ma10_pct=-3.0, ma20_pct=-1.0, ma60_pct=0.0,
        )
        assert signal == "trending_down"
        assert 0 <= score <= 30
        assert confidence == 80

    def test_classify_trend_regime_range(self):
        """Mixed MA values (no clear alignment) → sideways, mid score."""
        signal, score, _ = MarketRegimeClassifier._classify_trend_regime(
            ma5_pct=0.5, ma10_pct=-0.5, ma20_pct=1.0, ma60_pct=0.0,
        )
        assert signal == "sideways"
        assert 20 <= score <= 80

    def test_classify_trend_regime_bottom_reversal(self):
        """MA5>MA10 but MA10<MA20<0 → bottom_reversal signal."""
        signal, score, confidence = MarketRegimeClassifier._classify_trend_regime(
            ma5_pct=-1.0, ma10_pct=-2.5, ma20_pct=-2.0, ma60_pct=0.0,
        )
        assert signal == "bottom_reversal"
        assert 0 <= score <= 100
        assert 40 <= confidence <= 60

    def test_classify_trend_regime_top_reversal(self):
        """MA5<MA10 but MA10>MA20>0 → top_reversal signal."""
        signal, score, confidence = MarketRegimeClassifier._classify_trend_regime(
            ma5_pct=2.5, ma10_pct=4.0, ma20_pct=3.0, ma60_pct=0.0,
        )
        assert signal == "top_reversal"
        assert 0 <= score <= 100
        assert 40 <= confidence <= 60

    def test_classify_trend_regime_edge_cases(self):
        """Edge values such as zero or near-zero percentages."""
        # All equal → sideways
        signal, score, _ = MarketRegimeClassifier._classify_trend_regime(
            ma5_pct=0.0, ma10_pct=0.0, ma20_pct=0.0, ma60_pct=0.0,
        )
        assert signal == "sideways"

        # Very small positive → sideways (not a clean bullish alignment)
        signal, score, _ = MarketRegimeClassifier._classify_trend_regime(
            ma5_pct=0.1, ma10_pct=0.05, ma20_pct=-0.1, ma60_pct=0.0,
        )
        assert signal in ("sideways",)

    def test_classify_trend_regime_bullish_edge(self):
        """Just barely bullish → trending_up still, score at lower bound."""
        signal, score, _ = MarketRegimeClassifier._classify_trend_regime(
            ma5_pct=0.01, ma10_pct=0.005, ma20_pct=0.001, ma60_pct=0.0,
        )
        assert signal == "trending_up"
        # score should be close to 70 when magnitude is tiny
        assert 65 <= score <= 75

    def test_classify_trend_regime_bearish_edge(self):
        """Just barely bearish → trending_down still, score near upper bound."""
        signal, score, _ = MarketRegimeClassifier._classify_trend_regime(
            ma5_pct=-0.01, ma10_pct=-0.005, ma20_pct=-0.001, ma60_pct=0.0,
        )
        assert signal == "trending_down"
        # score should be close to 30 when magnitude is tiny
        assert 25 <= score <= 35


# ====================================================================
#  _calc_ma_slope  —  pure static logic
# ====================================================================


class TestCalcMaSlope:
    """Tests for MarketRegimeClassifier._calc_ma_slope()."""

    def test_calc_ma_slope_rising(self):
        """Rising series → positive slope."""
        series = pd.Series([100.0, 101.0, 102.0, 103.0, 104.0])
        slope = MarketRegimeClassifier._calc_ma_slope(series, window=3)
        assert slope > 0

    def test_calc_ma_slope_falling(self):
        """Falling series → negative slope."""
        series = pd.Series([104.0, 103.0, 102.0, 101.0, 100.0])
        slope = MarketRegimeClassifier._calc_ma_slope(series, window=3)
        assert slope < 0

    def test_calc_ma_slope_flat(self):
        """Flat series → slope near zero."""
        series = pd.Series([100.0, 100.0, 100.0, 100.0, 100.0])
        slope = MarketRegimeClassifier._calc_ma_slope(series, window=3)
        assert abs(slope) < 1e-6

    def test_calc_ma_slope_insufficient_data(self):
        """Fewer points than window → 0.0."""
        series = pd.Series([100.0, 101.0])
        slope = MarketRegimeClassifier._calc_ma_slope(series, window=3)
        assert slope == 0.0

    def test_calc_ma_slope_with_nan(self):
        """Series with NaN values still computes (drops NaN first)."""
        series = pd.Series([np.nan, 100.0, 102.0, 104.0, 106.0])
        slope = MarketRegimeClassifier._calc_ma_slope(series, window=3)
        assert slope > 0

    def test_calc_ma_slope_normalized_by_last(self):
        """Slope is normalized by the last value in the series."""
        series_small = pd.Series([1.0, 2.0, 3.0])
        series_large = pd.Series([1000.0, 2000.0, 3000.0])
        slope_small = MarketRegimeClassifier._calc_ma_slope(series_small, window=3)
        slope_large = MarketRegimeClassifier._calc_ma_slope(series_large, window=3)
        # After normalization, slopes should be similar
        assert abs(slope_small - slope_large) < 0.01


# ====================================================================
#  _composite_to_regime  —  pure static logic
# ====================================================================


class TestCompositeToRegime:
    """Tests for MarketRegimeClassifier._composite_to_regime()."""

    WEIGHTS: Dict[str, float] = {
        "trend": 0.35,
        "volume": 0.20,
        "breadth": 0.20,
        "volatility": 0.10,
        "sentiment": 0.15,
    }

    def test_composite_to_regime_bull(self):
        """Weighted score ≥ 85 → BULL_TREND with high confidence."""
        scores = {"trend": 95, "volume": 90, "breadth": 85, "volatility": 80, "sentiment": 85}
        regime, confidence, pf = MarketRegimeClassifier._composite_to_regime(scores, self.WEIGHTS)
        assert regime == MarketRegime.BULL_TREND
        assert confidence >= 80
        assert pf >= 0.80

    def test_composite_to_regime_bull_consolidation(self):
        """Weighted score 70-84 → BULL_CONSOLIDATION."""
        scores = {"trend": 80, "volume": 70, "breadth": 65, "volatility": 75, "sentiment": 70}
        regime, confidence, _ = MarketRegimeClassifier._composite_to_regime(scores, self.WEIGHTS)
        assert regime == MarketRegime.BULL_CONSOLIDATION
        assert 70 <= confidence <= 84

    def test_composite_to_regime_range(self):
        """Weighted score 40-69 → RANGE_BOUND."""
        scores = {"trend": 55, "volume": 50, "breadth": 45, "volatility": 60, "sentiment": 50}
        regime, confidence, _ = MarketRegimeClassifier._composite_to_regime(scores, self.WEIGHTS)
        assert regime == MarketRegime.RANGE_BOUND
        assert 40 <= confidence <= 69

    def test_composite_to_regime_bear_consolidation(self):
        """Weighted score 25-39 → BEAR_CONSOLIDATION."""
        scores = {"trend": 30, "volume": 35, "breadth": 40, "volatility": 45, "sentiment": 35}
        regime, confidence, _ = MarketRegimeClassifier._composite_to_regime(scores, self.WEIGHTS)
        assert regime == MarketRegime.BEAR_CONSOLIDATION
        assert 25 <= confidence <= 39

    def test_composite_to_regime_bear(self):
        """Weighted score < 25 → BEAR_TREND."""
        scores = {"trend": 10, "volume": 15, "breadth": 20, "volatility": 30, "sentiment": 25}
        regime, confidence, _ = MarketRegimeClassifier._composite_to_regime(scores, self.WEIGHTS)
        assert regime == MarketRegime.BEAR_TREND
        assert confidence <= 30
        assert confidence >= 0

    def test_composite_to_regime_extreme(self):
        """sentiment > 90 AND volatility > 85 → EXTREME_SENTIMENT."""
        scores = {"trend": 50, "volume": 50, "breadth": 50, "volatility": 90, "sentiment": 95}
        regime, confidence, _ = MarketRegimeClassifier._composite_to_regime(scores, self.WEIGHTS)
        assert regime == MarketRegime.EXTREME_SENTIMENT

    def test_composite_to_regime_bottom_reversal_via_signal(self):
        """trend signal=bottom_reversal → BOTTOM_REVERSAL even with mid scores."""
        scores = {"trend": 55, "volume": 50, "breadth": 50, "volatility": 50, "sentiment": 50}
        regime, _, pf = MarketRegimeClassifier._composite_to_regime(
            scores, self.WEIGHTS, signals={"trend": "bottom_reversal"},
        )
        assert regime == MarketRegime.BOTTOM_REVERSAL
        assert 0.50 <= pf <= 0.70  # BOTTOM_REVERSAL position range

    def test_composite_to_regime_position_factor_interpolation(self):
        """Position factor is interpolated within regime range."""
        scores_bull = {"trend": 95, "volume": 95, "breadth": 90, "volatility": 80, "sentiment": 85}
        _, _, pf_bull = MarketRegimeClassifier._composite_to_regime(scores_bull, self.WEIGHTS)
        assert 0.85 <= pf_bull <= 1.00

        scores_bear = {"trend": 5, "volume": 10, "breadth": 10, "volatility": 20, "sentiment": 15}
        _, _, pf_bear = MarketRegimeClassifier._composite_to_regime(scores_bear, self.WEIGHTS)
        assert 0.00 <= pf_bear <= 0.20

    def test_composite_to_regime_unknown_dimension(self):
        """Unknown dimensions in scores are handled (ignored) gracefully."""
        scores = {"trend": 90, "volume": 85, "breadth": 80, "volatility": 75, "sentiment": 80, "unknown": 100}
        regime, confidence, pf = MarketRegimeClassifier._composite_to_regime(scores, self.WEIGHTS)
        assert regime == MarketRegime.BULL_TREND
        assert confidence >= 70


# ====================================================================
#  Instance methods  —  synthetic data with mocked data_manager
# ====================================================================


def _make_synthetic_df(length: int = 100, start_price: float = 3000.0) -> pd.DataFrame:
    """Create a synthetic index daily DataFrame with required columns."""
    dates = pd.date_range(end="2026-05-06", periods=length, freq="B")
    prices = start_price * (1 + np.cumsum(np.random.default_rng(42).normal(0, 0.005, length)))
    closes = prices
    highs = closes * (1 + np.abs(np.random.default_rng(42).normal(0, 0.003, length)))
    lows = closes * (1 - np.abs(np.random.default_rng(42).normal(0, 0.003, length)))
    opens = (highs + lows) / 2
    volumes = np.random.default_rng(42).lognormal(15, 0.5, length)
    amounts = volumes * closes
    pct_chg = np.zeros(length)
    pct_chg[1:] = (closes[1:] / closes[:-1] - 1) * 100

    return pd.DataFrame({
        "date": dates,
        "open": opens,
        "high": highs,
        "low": lows,
        "close": closes,
        "volume": volumes,
        "amount": amounts,
        "pct_chg": pct_chg,
    })


class TestMarketRegimeIntegration:
    """Integration tests with synthetic data and mocked data_manager."""

    @pytest.fixture
    def mock_manager(self):
        manager = MagicMock()
        return manager

    def _make_dfs(self, bullish: bool = True) -> Dict[str, pd.DataFrame]:
        """Create synthetic DataFrames for 3 indices."""
        rng = np.random.default_rng(42)
        dfs = {}
        base_prices = {"000001": 3100.0, "399001": 10500.0, "399006": 2100.0}
        for code, start_price in base_prices.items():
            length = 120
            daily_ret = 0.0008 if bullish else -0.0008
            prices = start_price * (1 + np.cumsum(rng.normal(daily_ret, 0.008, length)))
            closes = prices
            highs = closes * (1 + np.abs(rng.normal(0, 0.002, length)))
            lows = closes * (1 - np.abs(rng.normal(0, 0.002, length)))
            volumes = rng.lognormal(15, 0.4, length)
            pct_chg = np.zeros(length)
            pct_chg[1:] = (closes[1:] / closes[:-1] - 1) * 100

            dfs[code] = pd.DataFrame({
                "date": pd.date_range(end="2026-05-06", periods=length, freq="B"),
                "open": (highs + lows) / 2,
                "high": highs,
                "low": lows,
                "close": closes,
                "volume": volumes,
                "amount": volumes * closes,
                "pct_chg": pct_chg,
            })
        return dfs

    def test_classify_returns_regime_result(self, mock_manager):
        """classify() returns a RegimeResult with the correct type."""
        dfs = self._make_dfs(bullish=True)

        def side_effect(code, **kwargs):
            if code in dfs:
                return dfs[code], "mock_source"
            raise ValueError(f"Unknown code: {code}")

        mock_manager.get_daily_data.side_effect = side_effect

        classifier = MarketRegimeClassifier(data_manager=mock_manager)
        result = classifier.classify(indices=["000001", "399001", "399006"], date="2026-05-06")

        assert result.regime in MarketRegime.__members__.values()
        assert 0 <= result.confidence <= 100
        assert 0.0 <= result.position_factor <= 1.0
        assert len(result.evidence) > 0
        assert result.regime_label
        assert result.recommendation

    def test_classify_bullish_market(self, mock_manager):
        """In a bullish scenario, regime should be bullish."""
        dfs = self._make_dfs(bullish=True)
        mock_manager.get_daily_data.side_effect = (
            lambda code, **kwargs: (dfs.get(code, pd.DataFrame()), "mock")
        )

        classifier = MarketRegimeClassifier(data_manager=mock_manager)
        result = classifier.classify(date="2026-05-06")

        assert result.regime in (
            MarketRegime.BULL_TREND,
            MarketRegime.BULL_CONSOLIDATION,
            MarketRegime.RANGE_BOUND,
        )

    def test_classify_bearish_market(self, mock_manager):
        """In a bearish scenario, regime should be bearish."""
        dfs = self._make_dfs(bullish=False)
        mock_manager.get_daily_data.side_effect = (
            lambda code, **kwargs: (dfs.get(code, pd.DataFrame()), "mock")
        )

        classifier = MarketRegimeClassifier(data_manager=mock_manager)
        result = classifier.classify(date="2026-05-06")

        assert result.regime in (
            MarketRegime.BEAR_TREND,
            MarketRegime.BEAR_CONSOLIDATION,
            MarketRegime.RANGE_BOUND,
        )

    def test_classify_empty_data_returns_default(self):
        """When no data is available, default RANGE_BOUND is returned."""
        mock_manager = MagicMock()
        mock_manager.get_daily_data.side_effect = ValueError("No data")

        classifier = MarketRegimeClassifier(data_manager=mock_manager)
        result = classifier.classify(indices=["000001"], date="2026-05-06")

        assert result.regime == MarketRegime.RANGE_BOUND
        assert result.confidence == 30

    def test_classify_with_market_stats_breadth(self, mock_manager):
        """When market stats are available, breadth uses adv/decl ratio."""
        dfs = self._make_dfs(bullish=True)
        mock_manager.get_daily_data.side_effect = (
            lambda code, **kwargs: (dfs.get(code, pd.DataFrame()), "mock")
        )

        # Mock fetcher that returns market stats
        mock_fetcher = MagicMock()
        mock_fetcher.get_market_stats.return_value = {
            "up_count": 3500,
            "down_count": 1200,
            "flat_count": 200,
            "limit_up_count": 80,
            "limit_down_count": 5,
            "total_amount": 1.2e11,
        }
        mock_manager._get_fetchers_snapshot.return_value = [mock_fetcher]

        classifier = MarketRegimeClassifier(data_manager=mock_manager)
        result = classifier.classify(date="2026-05-06")

        breadth_ev = [ev for ev in result.evidence if ev.dimension == "breadth"]
        assert len(breadth_ev) == 1
        assert "涨跌比" in breadth_ev[0].detail
        assert breadth_ev[0].signal == "broad"

    def test_classify_default_indices(self, mock_manager):
        """Default indices (上证/深证/创业板) are used when none provided."""
        dfs = self._make_dfs(bullish=True)
        calls = {}

        def side_effect(code, **kwargs):
            calls[code] = calls.get(code, 0) + 1
            if code in dfs:
                return dfs[code], "mock"
            raise ValueError(f"Unknown code: {code}")

        mock_manager.get_daily_data.side_effect = side_effect

        classifier = MarketRegimeClassifier(data_manager=mock_manager)
        classifier.classify(date="2026-05-06")

        # Default codes should have been fetched
        for default_code in ("000001", "399001", "399006"):
            assert default_code in calls, f"Expected {default_code} to be fetched"
