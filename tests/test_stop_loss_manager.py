# -*- coding: utf-8 -*-
"""Unit tests for StopLossManager - ATR/MA/structure stops, trailing, time, trigger check."""
import pytest
import pandas as pd
import numpy as np
from datetime import date, timedelta
from src.services.stop_loss_manager import (
    StopLossManager, StopConfig, StopType, StopMethod, InitialStops, StopEvent,
)


def _make_df(close_values, high_values=None, low_values=None):
    n = len(close_values)
    data = {"close": close_values}
    data["high"] = high_values or [c * 1.02 for c in close_values]
    data["low"] = low_values or [c * 0.98 for c in close_values]
    return pd.DataFrame(data)


def test_compute_atr_stop():
    mgr = StopLossManager()
    close = list(range(90, 105))
    high = [c * 1.03 for c in close]
    low = [c * 0.97 for c in close]
    df = _make_df(close, high, low)
    stops = mgr.compute_initial_stops(104, df, StopMethod.ATR)
    assert stops.hard_stop > 0
    assert stops.hard_stop < 104
    assert stops.method == StopMethod.ATR


def test_compute_ma_stop():
    mgr = StopLossManager()
    close = [100] * 10 + [102] * 5 + [105] * 5
    df = _make_df(close)
    stops = mgr.compute_initial_stops(105, df, StopMethod.MA)
    assert stops.hard_stop > 0
    assert stops.hard_stop < 105


def test_percent_fallback():
    mgr = StopLossManager(default_trailing_pct=8.0)
    stops = mgr.compute_initial_stops(100, None)
    assert stops.method == StopMethod.PERCENT
    assert stops.hard_stop == pytest.approx(96.0, abs=1)


def test_trailing_stop_atr():
    mgr = StopLossManager()
    stop = mgr.compute_trailing_stop(highest_price=110, atr_value=2.0, multiplier=2.0)
    assert stop == pytest.approx(106.0, abs=0.1)


def test_trailing_stop_percent():
    mgr = StopLossManager(default_trailing_pct=10.0)
    stop = mgr.compute_trailing_stop(highest_price=100, atr_value=None)
    assert stop == pytest.approx(90.0, abs=0.1)


def test_time_stop_not_triggered():
    mgr = StopLossManager(default_time_limit_days=20)
    recent = (date.today() - timedelta(days=5)).isoformat()
    event = mgr.check_time_stop(recent)
    assert not event.triggered


def test_time_stop_triggered():
    mgr = StopLossManager(default_time_limit_days=5)
    old = (date.today() - timedelta(days=10)).isoformat()
    event = mgr.check_time_stop(old)
    assert event.triggered


def test_evaluate_hard_trigger():
    mgr = StopLossManager()
    config = StopConfig(stock_code="600519", stock_name="茅台", entry_price=100, stop_price=95)
    events = mgr.evaluate(config, current_price=94)
    hard_events = [e for e in events if e.stop_type == StopType.HARD]
    assert hard_events[0].triggered


def test_evaluate_not_triggered():
    mgr = StopLossManager()
    config = StopConfig(stock_code="600519", stock_name="茅台", entry_price=100, stop_price=95)
    events = mgr.evaluate(config, current_price=105)
    hard_events = [e for e in events if e.stop_type == StopType.HARD]
    assert not hard_events[0].triggered


def test_batch_evaluate():
    mgr = StopLossManager()
    positions = [
        StopConfig(stock_code="TEST1", entry_price=100, stop_price=95),
        StopConfig(stock_code="TEST2", entry_price=200, stop_price=190),
    ]
    prices = {"TEST1": 94, "TEST2": 195}
    triggered = mgr.batch_evaluate(positions, prices)
    assert len(triggered) == 1
    assert triggered[0].stock_code == "TEST1"


def test_format_events():
    mgr = StopLossManager()
    config = StopConfig(stock_code="TEST", stock_name="测试", entry_price=100, stop_price=95)
    events = mgr.evaluate(config, current_price=94)
    formatted = mgr.format_events(events)
    assert "止损触发" in formatted or "🚨" in formatted
