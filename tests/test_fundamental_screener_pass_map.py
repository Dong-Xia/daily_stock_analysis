# -*- coding: utf-8 -*-
"""FundamentalScreener 单元测试:screen() 重构行为不变 + get_pass_map 交集口径。"""
import sys
from unittest.mock import MagicMock

import pandas as pd
import pytest

# 无 akshare 运行环境下用 stub 保证可导入
try:
    import akshare  # noqa: F401
except ModuleNotFoundError:
    akshare = MagicMock()
    sys.modules["akshare"] = akshare

from src.services.fundamental_screener import FundamentalScreener


def _row(code, rev_yoy, profit_yoy, net_profit_yi, name=None, industry="白酒"):
    """构造 stock_yjbb_em 单行:net_profit_yi 单位为亿。"""
    return {
        "股票代码": code,
        "股票简称": name or f"股票{code}",
        "营业总收入-同比增长": rev_yoy,
        "净利润-同比增长": profit_yoy,
        "净利润-净利润": net_profit_yi * 1e8,
        "最新公告日期": "2026-08-30",
        "所处行业": industry,
    }


def _patch_yjbb(monkeypatch, rows):
    """替换 akshare.stock_yjbb_em,返回调用计数器。"""
    calls = {"n": 0}

    def fake(date):
        calls["n"] += 1
        return pd.DataFrame(rows)

    monkeypatch.setattr(akshare, "stock_yjbb_em", fake)
    return calls


def test_screen_behavior_unchanged(monkeypatch):
    """重构后 screen() 的漏斗计数/评分排序/截断/criteria 均不变。"""
    rows = [
        _row("600519", 30.0, 80.0, 1.0),   # 三条全过, 评分 2+3+1=6
        _row("000001", 60.0, 120.0, 6.0),  # 三条全过, 评分 3+5+2=10
        _row("000002", 10.0, 80.0, 1.0),   # 营收不达标
        _row("000003", 30.0, 40.0, 1.0),   # 利润不达标
        _row("000004", 30.0, 80.0, 0.3),   # 净利润不达标
    ]
    _patch_yjbb(monkeypatch, rows)

    result = FundamentalScreener(max_candidates=1).screen("20260630")

    assert result.date == "20260630"
    assert result.errors == []
    assert result.total_stocks == 5
    assert result.after_revenue_test == 4
    assert result.after_profit_test == 4
    assert result.after_net_profit_test == 2
    assert [c.code for c in result.candidates] == ["000001"]  # 评分最高, 截断为 1
    assert result.candidates[0].composite_score == 10.0
    assert "营收同比增长 ≥20%" in result.criteria


def test_screen_returns_error_on_fetch_failure(monkeypatch):
    """akshare 异常时返回 errors 结果而非抛出(screen 既有降级语义)。"""
    def fake(date):
        raise RuntimeError("boom")

    monkeypatch.setattr(akshare, "stock_yjbb_em", fake)

    result = FundamentalScreener().screen("20260630")

    assert result.candidates == []
    assert len(result.errors) == 1
    assert "boom" in result.errors[0]


@pytest.fixture(autouse=True)
def _clear_pass_map_cache():
    FundamentalScreener._PASS_MAP_CACHE.clear()
    yield
    FundamentalScreener._PASS_MAP_CACHE.clear()


def test_pass_map_three_criteria(monkeypatch):
    """通过名单只含三条硬性标准全过的股票,字段完整。"""
    rows = [
        _row("600519", 30.0, 80.0, 1.0),
        _row("000002", 10.0, 80.0, 1.0),   # 营收不达标
        _row("000003", 30.0, 40.0, 1.0),   # 利润不达标
        _row("000004", 30.0, 80.0, 0.3),   # 净利润不达标
    ]
    _patch_yjbb(monkeypatch, rows)

    m = FundamentalScreener().get_pass_map("20260630")

    assert set(m.keys()) == {"600519"}
    fund = m["600519"]
    assert fund["name"] == "股票600519"
    assert fund["revenue_yoy"] == 30.0
    assert fund["profit_yoy"] == 80.0
    assert fund["net_profit"] == 1e8
    assert fund["industry"] == "白酒"
    assert fund["composite_score"] == 6.0


def test_pass_map_not_capped(monkeypatch):
    """通过名单不受 max_candidates 展示截断影响。"""
    rows = [_row(f"{600000 + i}", 30.0, 80.0, 1.0) for i in range(60)]
    _patch_yjbb(monkeypatch, rows)

    m = FundamentalScreener(max_candidates=50).get_pass_map("20260630")

    assert len(m) == 60


def test_pass_map_cached_per_quarter(monkeypatch):
    """TTL 内同季度第二次调用命中缓存,不重新拉取。"""
    calls = _patch_yjbb(monkeypatch, [_row("600519", 30.0, 80.0, 1.0)])

    s = FundamentalScreener()
    m1 = s.get_pass_map("20260630")
    m2 = s.get_pass_map("20260630")

    assert m1 is m2
    assert calls["n"] == 1


def test_pass_map_cache_expires_after_ttl(monkeypatch):
    """TTL 过期后同季度重新拉取。"""
    import src.services.fundamental_screener as fs

    calls = _patch_yjbb(monkeypatch, [_row("600519", 30.0, 80.0, 1.0)])
    monkeypatch.setattr(fs, "_PASS_MAP_CACHE_TTL_SECONDS", 0)

    s = FundamentalScreener()
    s.get_pass_map("20260630")
    s.get_pass_map("20260630")

    assert calls["n"] == 2


def test_pass_map_raises_on_fetch_failure(monkeypatch):
    """拉取失败异常向上抛(由端点转 502)。"""
    def fake(date):
        raise RuntimeError("boom")

    monkeypatch.setattr(akshare, "stock_yjbb_em", fake)

    with pytest.raises(RuntimeError):
        FundamentalScreener().get_pass_map("20260630")
