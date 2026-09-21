# -*- coding: utf-8 -*-
"""战法选股器计算问题回归测试（离线）。

背景：
1. 超跌反弹 _check_market_panic 曾用 get_daily_data("000001") 取"上证指数"，
   但 A 股各数据源均把 000001 解析为平安银行（实测 close≈11.7 元），
   指数级恐慌阈值（当日 -1.5%、连跌 3 天、乖离 -2%）被套用在单只银行股上。
2. 三倍量 _passes_all 曾仅要求 score>=3，而预筛选已保证 pass_change/pass_turnover
   恒真（起步 2 分），导致量能未达 3 倍的股票也能以"三倍量战法候选"入选。
"""
import numpy as np

from src.services.oversold_bounce_screener import OversoldBounceScreener
from src.services.triple_volume_screener import TripleVolumeCandidate, TripleVolumeScreener


class _StubManager:
    """禁止走 get_daily_data：恐慌检查必须使用指数日线而非个股K线。"""

    def get_daily_data(self, *args, **kwargs):
        raise AssertionError("_check_market_panic 不应调用 get_daily_data（000001=平安银行，非上证指数）")


def _panic_screener(monkeypatch, closes):
    screener = OversoldBounceScreener(data_manager=_StubManager())
    monkeypatch.setattr(screener, "_fetch_index_closes", lambda: np.array(closes, dtype=float))
    return screener


def test_market_panic_true_on_index_crash(monkeypatch):
    # 连跌4天、当日 -2.63%、5日乖离 -3.29% → 恐慌
    s = _panic_screener(monkeypatch, [3900, 3880, 3850, 3800, 3700])
    assert s._check_market_panic() is True


def test_market_panic_false_on_rebound(monkeypatch):
    # 末日反弹 → 连跌天数不足
    s = _panic_screener(monkeypatch, [3700, 3720, 3740, 3730, 3800])
    assert s._check_market_panic() is False


def test_market_panic_false_on_small_decline(monkeypatch):
    # 连跌4天但当日仅 -0.26%、乖离不足 → 非恐慌（指数阈值不应被个股波动误触发）
    s = _panic_screener(monkeypatch, [3830, 3825, 3820, 3815, 3805])
    assert s._check_market_panic() is False


def test_market_panic_false_when_data_insufficient(monkeypatch):
    s = _panic_screener(monkeypatch, [3900, 3880, 3850])
    assert s._check_market_panic() is False


def _candidate(**overrides) -> TripleVolumeCandidate:
    base = dict(
        pass_volume=False,
        pass_change=True,
        pass_turnover=True,
        pass_position=False,
        pass_ma_alignment=False,
        pass_solid_yang=True,
        score=3,
    )
    base.update(overrides)
    return TripleVolumeCandidate(code="600519", name="测试", **base)


def test_passes_all_rejects_without_triple_volume():
    # 涨幅+换手+阳线=3分，但量能未达3倍 → 不应入选三倍量战法
    assert TripleVolumeScreener._passes_all(_candidate()) is False


def test_passes_all_accepts_with_triple_volume():
    c = _candidate(pass_volume=True, score=4)
    assert TripleVolumeScreener._passes_all(c) is True
