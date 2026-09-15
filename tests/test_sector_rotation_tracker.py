# -*- coding: utf-8 -*-
"""Unit tests for SectorRotationTracker classification and scoring logic."""
import pytest
from unittest.mock import MagicMock
from src.services.sector_rotation_tracker import (
    SectorDurability,
    SectorRotationResult,
    SectorRotationTracker,
)


# ── _classify ─────────────────────────────────────────────


def test_classify_main_line():
    tracker = SectorRotationTracker()
    result = tracker._classify(consecutive=7, ratio=0.8, trend=2.0, score=120)
    assert result == ("main_line", "主线")


def test_classify_strong_rotating():
    tracker = SectorRotationTracker()
    result = tracker._classify(consecutive=3, ratio=0.5, trend=0.5, score=80)
    assert result == ("strong_rotating", "强势轮动")


def test_classify_rotating():
    tracker = SectorRotationTracker()
    result = tracker._classify(consecutive=2, ratio=0.35, trend=-0.5, score=60)
    assert result == ("rotating", "轮动")


def test_classify_pulse():
    tracker = SectorRotationTracker()
    result = tracker._classify(consecutive=1, ratio=0.1, trend=0.1, score=40)
    assert result == ("pulse", "脉冲")


def test_classify_fading():
    tracker = SectorRotationTracker()
    result = tracker._classify(consecutive=0, ratio=0.05, trend=-2.0, score=10)
    assert result == ("fading", "退潮")


def test_classify_emerging():
    tracker = SectorRotationTracker()
    result = tracker._classify(consecutive=0, ratio=0.15, trend=0.5, score=30)
    assert result == ("emerging", "异动")


# ── _compute_consecutive ──────────────────────────────────


def test_consecutive_basic():
    tracker = SectorRotationTracker()
    entries = [
        ("2025-01-01", 1, 100),
        ("2025-01-02", 2, 95),
        ("2025-01-03", 3, 90),
    ]
    all_dates = ["2025-01-01", "2025-01-02", "2025-01-03"]
    assert tracker._compute_consecutive(entries, all_dates) == 3


def test_consecutive_with_drop():
    """Sector dropped out of top N on intermediate trading days."""
    tracker = SectorRotationTracker()
    entries = [
        ("2025-01-01", 1, 100),
        ("2025-01-04", 2, 95),
    ]
    # 01-02 and 01-03 are trading days but sector was NOT in top N
    all_dates = ["2025-01-01", "2025-01-02", "2025-01-03", "2025-01-04"]
    assert tracker._compute_consecutive(entries, all_dates) == 1


def test_consecutive_gapped_weekend():
    """Sector missed intermediate days because they were non-trading days."""
    tracker = SectorRotationTracker()
    entries = [
        ("2025-01-01", 1, 100),
        ("2025-01-04", 2, 95),
    ]
    # 01-02 and 01-03 are NOT trading days (weekend/holiday)
    all_dates = ["2025-01-01", "2025-01-04"]
    assert tracker._compute_consecutive(entries, all_dates) == 2


def test_consecutive_not_latest_date():
    tracker = SectorRotationTracker()
    entries = [
        ("2025-01-01", 1, 100),
        ("2025-01-02", 2, 90),
    ]
    # Latest trading day is 01-05, but sector not in top N on that date
    all_dates = ["2025-01-01", "2025-01-02", "2025-01-05"]
    assert tracker._compute_consecutive(entries, all_dates) == 0


# ── _compute_score_trend ──────────────────────────────────


def test_score_trend_rising():
    tracker = SectorRotationTracker()
    scores = [50, 70, 90, 110, 130]
    assert tracker._compute_score_trend(scores) > 0


def test_score_trend_falling():
    tracker = SectorRotationTracker()
    scores = [130, 110, 90, 70, 50]
    assert tracker._compute_score_trend(scores) < 0


def test_score_trend_short():
    tracker = SectorRotationTracker()
    assert tracker._compute_score_trend([50]) == 0.0
    assert tracker._compute_score_trend([50, 60]) == 0.0


# ── _compute_momentum_5d ─────────────────────────────────


def test_momentum_5d_positive():
    tracker = SectorRotationTracker()
    scores = [100] * 5 + [120]
    assert tracker._compute_momentum_5d(scores) == 20.0


def test_momentum_5d_short():
    tracker = SectorRotationTracker()
    assert tracker._compute_momentum_5d([100, 110]) == 0.0


# ── Integration: analyze with mocked storage ──────────────


def test_analyze_empty_storage():
    mock_storage = MagicMock()
    mock_storage.get_available_dates.return_value = []
    tracker = SectorRotationTracker(storage=mock_storage)
    result = tracker.analyze()
    assert isinstance(result, SectorRotationResult)
    assert len(result.sectors) == 0
