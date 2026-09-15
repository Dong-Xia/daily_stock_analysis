# -*- coding: utf-8 -*-
"""Unit tests for PositionSizer - Kelly formula, risk limits, regime scaling."""
import pytest
from src.services.position_sizer import PositionSizer, SizeRequest, SizeResult


def test_basic_calculation():
    sizer = PositionSizer()
    req = SizeRequest(
        stock_code="600519", stock_name="茅台",
        entry_price=1800, stop_loss_price=1764,  # -2%
        account_equity=1000000, market_regime_factor=0.80,
        signal_confidence=70, max_positions=5,
    )
    result = sizer.calculate(req)
    assert result.recommended_shares > 0
    assert result.max_loss > 0
    assert result.recommended_pct > 0
    assert result.recommended_pct <= 25.0
    assert len(result.rationale) > 0


def test_high_confidence_bull_market():
    sizer = PositionSizer()
    req = SizeRequest(
        stock_code="AAPL", entry_price=200, stop_loss_price=190,
        account_equity=500000, market_regime_factor=1.0,
        signal_confidence=85, max_positions=5,
    )
    result = sizer.calculate(req)
    assert result.recommended_shares >= result.risk_adjusted_shares
    assert result.kelly_fraction > 0


def test_low_confidence_bear_market():
    sizer = PositionSizer()
    req = SizeRequest(
        stock_code="TEST", entry_price=50, stop_loss_price=48,
        account_equity=200000, market_regime_factor=0.20,
        signal_confidence=35, max_positions=5,
    )
    result = sizer.calculate(req)
    assert result.recommended_pct < 15.0


def test_invalid_prices():
    sizer = PositionSizer()
    req = SizeRequest(
        stock_code="XX", entry_price=0, stop_loss_price=10,
        account_equity=100000,
    )
    result = sizer.calculate(req)
    assert len(result.warnings) > 0
    assert result.recommended_shares == 0


def test_pct_limits_respected():
    sizer = PositionSizer(max_single_position_pct=15.0)
    req = SizeRequest(
        stock_code="600519", entry_price=100, stop_loss_price=95,
        account_equity=100000, market_regime_factor=0.80,
        signal_confidence=65, max_positions=5,
        max_single_position_pct=15.0,
    )
    result = sizer.calculate(req)
    assert result.recommended_pct <= 15.0


def test_sector_constraint():
    sizer = PositionSizer(max_sector_exposure_pct=30.0)
    req = SizeRequest(
        stock_code="TEST", entry_price=100, stop_loss_price=95,
        account_equity=100000, market_regime_factor=0.80,
        signal_confidence=60, sector_count=3,
        max_sector_exposure_pct=30.0,
    )
    result = sizer.calculate(req)
    assert result.equity_pct <= 12.0


def test_sector_cap_uses_post_trim_pct_not_stale():
    """单票上限裁剪后，板块上限检查必须用裁剪后的比例。

    场景: 初始 20% > max_single 10% → 裁到 5%；per_sector_max=6%。
    修复前用修剪前的 20% 判断 20>6 → 错误地再次改写仓位(6000股)；
    修复后 5% ≤ 6% → 不再触发板块裁剪。
    """
    sizer = PositionSizer()
    req = SizeRequest(
        stock_code="TEST", entry_price=10, stop_loss_price=9,
        account_equity=1_000_000, market_regime_factor=0.5,
        max_single_position_pct=10.0,
        sector_count=2, max_sector_exposure_pct=12.0,
    )
    result = sizer.calculate(req)
    assert result.risk_adjusted_shares == 5000
    assert result.risk_adjusted_cost == 50000
    assert not any("板块限制" in line for line in result.rationale)


def test_sector_cap_still_binds_after_single_trim():
    """单票裁剪后仍超板块上限时，板块裁剪必须正常生效（防止修复矫枉过正）。

    per_sector_max = 8/2 = 4% < 裁剪后的 5% → 应再裁到 4000 股。
    """
    sizer = PositionSizer()
    req = SizeRequest(
        stock_code="TEST", entry_price=10, stop_loss_price=9,
        account_equity=1_000_000, market_regime_factor=0.5,
        max_single_position_pct=10.0,
        sector_count=2, max_sector_exposure_pct=8.0,
    )
    result = sizer.calculate(req)
    assert result.risk_adjusted_shares == 4000
    assert any("板块限制" in line for line in result.rationale)


def test_format_terminal():
    sizer = PositionSizer()
    req = SizeRequest(
        stock_code="600519", stock_name="茅台",
        entry_price=1800, stop_loss_price=1764,
        account_equity=1000000,
    )
    result = sizer.calculate(req)
    formatted = PositionSizer.format_terminal(result)
    assert "茅台" in formatted
    assert "1800" in formatted
