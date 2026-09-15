# -*- coding: utf-8 -*-
"""资金水位缓存回归测试：缓存键必须含有效交易日，跨日自动刷新。

背景：旧实现 key 仅含语言、无 TTL，长驻服务永远返回首次请求的盘前快照。
"""
from datetime import date

import pytest

import src.core.trading_calendar as tc
import src.services.history_service as hs


@pytest.fixture(autouse=True)
def _clean_state(monkeypatch):
    hs._MONEY_STATUS_CACHE.clear()
    monkeypatch.setattr(hs, "_MONEY_STATUS_FETCHER", object())  # 跳过真实 DataFetcherManager 构造
    yield
    hs._MONEY_STATUS_CACHE.clear()


def _stub(monkeypatch, assess):
    monkeypatch.setattr(hs, "assess_market_money_status", assess)
    monkeypatch.setattr(hs, "format_money_status_block",
                        lambda status, language="zh": f"block[{status}][{language}]")


def test_cache_hit_same_day_refetch_after_rollover(monkeypatch):
    calls = {"n": 0}

    def fake_assess(_fetcher):
        calls["n"] += 1
        return f"day{calls['n']}"

    _stub(monkeypatch, fake_assess)
    cur = {"d": date(2026, 9, 10)}
    monkeypatch.setattr(tc, "get_effective_trading_date", lambda market, current_time=None: cur["d"])

    assert hs._get_money_status_block("zh") == "block[day1][zh]"
    assert hs._get_money_status_block("zh") == "block[day1][zh]"
    assert calls["n"] == 1  # 同日命中缓存，不重复取数

    cur["d"] = date(2026, 9, 11)  # 跨交易日
    assert hs._get_money_status_block("zh") == "block[day2][zh]"
    assert calls["n"] == 2
    assert set(hs._MONEY_STATUS_CACHE) == {"money_status_zh_2026-09-11"}  # 旧键已清理

    assert hs._get_money_status_block("en") == "block[day3][en]"
    assert set(hs._MONEY_STATUS_CACHE) == {
        "money_status_zh_2026-09-11", "money_status_en_2026-09-11",
    }  # 语言维度互不误伤


def test_failure_cached_fail_open_per_day(monkeypatch):
    calls = {"n": 0}

    def boom(_fetcher):
        calls["n"] += 1
        raise RuntimeError("source down")

    _stub(monkeypatch, boom)
    cur = {"d": date(2026, 9, 10)}
    monkeypatch.setattr(tc, "get_effective_trading_date", lambda market, current_time=None: cur["d"])

    assert hs._get_money_status_block("zh") == ""
    assert hs._get_money_status_block("zh") == ""
    assert calls["n"] == 1  # 当日失败不重试打爆数据源

    cur["d"] = date(2026, 9, 11)
    assert hs._get_money_status_block("zh") == ""
    assert calls["n"] == 2  # 次日自然重试
