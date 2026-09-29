# -*- coding: utf-8 -*-
"""Unit tests for SectorToStockSelector top-sector candidate extraction."""
import pytest

from src.services.sector_rotation_tracker import (
    SectorDurability,
    SectorRotationResult,
)
from src.services.sector_to_stock_selector import SectorToStockSelector


def _sector(name, classification, classification_cn, score=50.0):
    return SectorDurability(
        name=name,
        classification=classification,
        classification_cn=classification_cn,
        current_score=score,
    )


def _patch_tracker(monkeypatch, result):
    class FakeTracker:
        def __init__(self, *args, **kwargs):
            pass

        def analyze(self, target_date=None):
            return result

    monkeypatch.setattr(
        "src.services.sector_rotation_tracker.SectorRotationTracker", FakeTracker
    )


def test_get_top_sectors_prefers_classified(monkeypatch):
    """主线 + 强势轮动/轮动应入选，脉冲/异动应排除。"""
    result = SectorRotationResult(
        sectors=[
            _sector("脉冲板块", "pulse", "脉冲"),
            _sector("强势板块", "strong_rotating", "强势轮动"),
            _sector("异动板块", "emerging", "异动"),
        ],
        top_main_lines=[_sector("主线板块", "main_line", "主线")],
    )
    _patch_tracker(monkeypatch, result)

    candidates = SectorToStockSelector(max_sectors=3)._get_top_sectors()

    names = [c["name"] for c in candidates]
    assert names == ["主线板块", "强势板块"]


def test_get_top_sectors_fallback_when_none_classified(monkeypatch):
    """全部为异动/脉冲（历史命名碎片化）时，应回退到耐久度排序前几名而非空列表。"""
    result = SectorRotationResult(
        sectors=[
            _sector("异动A", "emerging", "异动", score=70.0),
            _sector("脉冲B", "pulse", "脉冲", score=60.0),
            _sector("异动C", "emerging", "异动", score=50.0),
        ],
        top_main_lines=[],
    )
    _patch_tracker(monkeypatch, result)

    candidates = SectorToStockSelector(max_sectors=2)._get_top_sectors()

    names = [c["name"] for c in candidates]
    assert names == ["异动A", "脉冲B"]


def test_get_top_sectors_empty_when_no_data(monkeypatch):
    """轮动结果完全为空时，仍应返回空列表。"""
    _patch_tracker(monkeypatch, SectorRotationResult(sectors=[], top_main_lines=[]))

    assert SectorToStockSelector()._get_top_sectors() == []
