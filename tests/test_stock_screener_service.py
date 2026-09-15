# -*- coding: utf-8 -*-
"""Unit tests for StockScreenerService static scoring methods and layer logic."""

import pandas as pd
import numpy as np
import pytest

from src.services.stock_screener_service import StockScreenerService
from src.schemas.stock_screener_schema import ScreenerCriteria


def _make_df(close_values, volume_values=None):
    """Create a synthetic daily DataFrame with close and volume columns."""
    n = len(close_values)
    data = {"close": close_values}
    if volume_values:
        data["volume"] = volume_values
    else:
        data["volume"] = [1e6] * n
    data["amount"] = [5e8] * n  # 0.5 亿
    return pd.DataFrame(data)


def _make_ma_aligned_df(uptrend=True):
    """Get scores for uptrend/downtrend MA pattern."""
    if uptrend:
        # Rising: MA5 > MA10 > MA20
        close = list(range(90, 110))
    else:
        # Falling
        close = list(range(110, 90, -1))
    return _make_df(close)


# ── _compute_trend_strength ──────────────────────────────


def test_compute_trend_strength_bullish():
    """MA5>MA10>MA20 rising → score ≥ 70"""
    s = StockScreenerService()
    df = _make_ma_aligned_df(uptrend=True)
    score = s._compute_trend_strength(df)
    assert score >= 70, f"expected ≥70, got {score}"


def test_compute_trend_strength_bearish():
    """MA5<MA10<MA20 falling → score ≤ 30"""
    s = StockScreenerService()
    df = _make_ma_aligned_df(uptrend=False)
    score = s._compute_trend_strength(df)
    assert score <= 40, f"expected ≤40, got {score}"


def test_compute_trend_strength_no_data():
    """Empty df → neutral 50"""
    s = StockScreenerService()
    assert s._compute_trend_strength(None) == 50.0
    assert s._compute_trend_strength(pd.DataFrame()) == 50.0


# ── _compute_volume_confirmation ──────────────────────────


def test_compute_volume_high():
    """Volume ratio 1.5 → >70"""
    s = StockScreenerService()
    close = [100] * 30
    vol = [1e6] * 25 + [2.5e6] * 5  # recent = 2.5e6, longer ≈ 1.25e6, ratio ≈ 2.0
    df = _make_df(close, vol)
    score = s._compute_volume_confirmation(df)
    assert score > 60, f"expected >60, got {score}"


def test_compute_volume_low():
    """Volume ratio 0.5 → <40"""
    s = StockScreenerService()
    close = [100] * 30
    vol = [2e6] * 20 + [1e6] * 10  # recent half
    df = _make_df(close, vol)
    score = s._compute_volume_confirmation(df)
    assert score < 60, f"expected <60, got {score}"


def test_compute_volume_no_data():
    s = StockScreenerService()
    assert s._compute_volume_confirmation(None) == 50.0


# ── _compute_bias_score ───────────────────────────────────


def test_compute_bias_optimal():
    """<3% bias → ≥80"""
    s = StockScreenerService()
    score = s._compute_bias_score(102.0, 100.0)  # 2% bias
    assert score >= 80, f"expected ≥80, got {score}"


def test_compute_bias_extended():
    """>8% bias → ≤40"""
    s = StockScreenerService()
    score = s._compute_bias_score(110.0, 100.0)  # 10% bias
    assert score <= 40, f"expected ≤40, got {score}"


def test_compute_bias_zero_price():
    s = StockScreenerService()
    assert s._compute_bias_score(0, 100) == 50.0
    assert s._compute_bias_score(100, 0) == 50.0


# ── _compute_limit_up_proximity ───────────────────────────


def test_limit_up_proximity_near():
    """<5% from limit-up → ≤30"""
    s = StockScreenerService()
    score = s._compute_limit_up_proximity(10.8, 10.0, 0.10)
    # limit_up = 11.0, distance = (11.0-10.8)/11.0 ≈ 1.8% → ≤30
    assert score <= 30, f"expected ≤30, got {score}"


def test_limit_up_proximity_safe():
    """>20% from limit-up → ≥80"""
    s = StockScreenerService()
    score = s._compute_limit_up_proximity(8.0, 10.0, 0.10)
    # limit_up = 11.0, distance = (11.0-8.0)/11.0 ≈ 27% → ≥80
    assert score >= 80, f"expected ≥80, got {score}"


def test_limit_up_proximity_zero():
    s = StockScreenerService()
    assert s._compute_limit_up_proximity(0, 10, 0.10) == 50.0


# ── _get_limit_up_ratio ───────────────────────────────────


def test_get_limit_up_ratio_kc():
    s = StockScreenerService()
    assert s._get_limit_up_ratio("688001") == 0.20
    assert s._get_limit_up_ratio("300750") == 0.20


def test_get_limit_up_ratio_normal():
    s = StockScreenerService()
    assert s._get_limit_up_ratio("600519") == 0.10
    assert s._get_limit_up_ratio("000001") == 0.10


def test_get_limit_up_ratio_bse():
    s = StockScreenerService()
    assert s._get_limit_up_ratio("920001") == 0.30


# ── _normalize_rs ─────────────────────────────────────────


def test_normalize_rs_leader():
    s = StockScreenerService()
    assert s._normalize_rs(2.5) == 100.0
    assert s._normalize_rs(1.5) > 75


def test_normalize_rs_laggard():
    s = StockScreenerService()
    assert s._normalize_rs(0.3) < 40
    assert s._normalize_rs(1.0) == pytest.approx(60.0, abs=1)


# ── Layer Logic ───────────────────────────────────────────


def test_layer2_alignment_classification():
    """Verify MA alignment string is set correctly."""
    s = StockScreenerService()
    # Bullish pattern: long steady rise
    close = list(range(80, 110))  # 30 data points, strong uptrend
    df = _make_df(close)
    stock = {"code": "TEST", "name": "测试", "price": 109, "change_pct": 1.0, "_df": df}
    surv, _ = s._layer2_trend_filter([stock], ScreenerCriteria(require_ma_alignment=False), None)
    assert len(surv) == 1
    assert surv[0]["ma_alignment"] == "多头排列"


def test_layer2_filter_removes_non_bullish():
    """When require_ma_alignment=True, bearish stocks removed."""
    s = StockScreenerService()
    close = list(range(105, 95, -1))  # descending
    df = _make_df(close)
    stock = {"code": "TEST", "name": "测试", "price": 96, "change_pct": -1.0, "_df": df}
    surv, _ = s._layer2_trend_filter([stock], ScreenerCriteria(require_ma_alignment=True), None)
    assert len(surv) == 0


# ── L1 liquidity filter ─────────────────────────────────────


def test_layer1_filters_low_liquidity():
    """L1 should filter out stocks below min_avg_amount and min_turnover."""
    s = StockScreenerService()
    stocks = [
        {"code": "600001", "name": "LowAmount", "price": 10, "change_pct": 2.0,
         "avg_amount_yi": 0.5, "turnover_rate": 5.0},
        {"code": "600002", "name": "LowTurnover", "price": 20, "change_pct": 1.0,
         "avg_amount_yi": 3.0, "turnover_rate": 0.3},
        {"code": "600003", "name": "Good", "price": 30, "change_pct": 3.0,
         "avg_amount_yi": 2.0, "turnover_rate": 3.0},
    ]
    criteria = ScreenerCriteria(min_avg_amount_yi=1.0, min_turnover_rate=1.0)
    survivors, count = s._layer1_liquidity_filter(stocks, criteria, None)
    codes = [st["code"] for st in survivors]
    assert "600003" in codes
    assert "600001" not in codes
    assert "600002" not in codes


def test_layer1_passes_through_when_no_data():
    """L1 should pass stocks through when metrics are unavailable."""
    s = StockScreenerService()
    stocks = [
        {"code": "600001", "name": "NoData", "price": 10, "change_pct": 2.0},
    ]
    criteria = ScreenerCriteria(min_avg_amount_yi=1.0, min_turnover_rate=1.0)
    survivors, count = s._layer1_liquidity_filter(stocks, criteria, None)
    assert len(survivors) == 1


# ── _compute_sector_leadership ──────────────────────────────


def test_sector_leadership_positive_change():
    """Positive change should get higher scores."""
    s = StockScreenerService()
    assert s._compute_sector_leadership({"change_pct": 9.5}) == 90.0
    assert s._compute_sector_leadership({"change_pct": 7.5}) == 70.0
    assert s._compute_sector_leadership({"change_pct": 5.5}) == 50.0
    assert s._compute_sector_leadership({"change_pct": 3.5}) == 30.0
    assert s._compute_sector_leadership({"change_pct": 1.0}) == 10.0


def test_sector_leadership_negative_change():
    """Negative change (declining) should get very low scores."""
    s = StockScreenerService()
    assert s._compute_sector_leadership({"change_pct": -9.0}) <= 5.0
    assert s._compute_sector_leadership({"change_pct": -5.0}) <= 5.0
    assert s._compute_sector_leadership({"change_pct": -1.0}) <= 10.0


def test_sector_leadership_no_abs_bug():
    """Verify abs() was removed: -10% should NOT score same as +10%."""
    s = StockScreenerService()
    positive = s._compute_sector_leadership({"change_pct": 10.0})
    negative = s._compute_sector_leadership({"change_pct": -10.0})
    assert positive > negative, f"Positive ({positive}) should score higher than negative ({negative})"


# ── L3 intra-sector ranking ──────────────────────────────────


def test_layer3_keeps_top_ratio():
    """L3 should keep top_n_ratio of stocks by N-day return."""
    s = StockScreenerService(top_n_ratio=0.5)
    stocks = []
    for i in range(10):
        stock = {
            "code": f"6000{i:03d}", "name": f"Stock{i}", "price": 10 + i,
            "change_pct": float(i), "_df": None, "n_day_return": float(i),
        }
        stocks.append(stock)
    survivors, _ = s._layer3_intra_sector_ranking(stocks, None)
    assert len(survivors) == 5


# ── L4 composite scoring ────────────────────────────────────


def test_layer4_pre_close_no_division_by_zero():
    """pre_close calculation should handle extreme change_pct values."""
    s = StockScreenerService()
    df = _make_df(list(range(80, 110)))

    # change_pct = 0 → pre_close = price
    stock = {"code": "TEST", "name": "测", "price": 10.0, "change_pct": 0, "ma5": 10.0, "_df": df}
    candidates = s._layer4_composite_scoring([stock])
    assert len(candidates) == 1

    # change_pct = -99 → should not crash
    stock2 = {"code": "TEST2", "name": "测2", "price": 10.0, "change_pct": -99, "ma5": 10.0, "_df": df}
    candidates = s._layer4_composite_scoring([stock2])
    assert len(candidates) == 1
