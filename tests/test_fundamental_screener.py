# -*- coding: utf-8 -*-
"""基本面选股终端输出回归测试（离线）。

背景：format_result 旧实现把首名候选的实际增速打印成">阈值"、把评分截断后的
候选数打印成"全部条件通过"，导致用户误以为通过数恒为 50（截断上限）。
"""
from src.services.fundamental_screener import (
    FundamentalCandidate,
    FundamentalResult,
    FundamentalScreener,
)


def _result(after_net: int, candidates: list) -> FundamentalResult:
    return FundamentalResult(
        date="20260331",
        total_stocks=5000,
        after_revenue_test=300,
        after_profit_test=180,
        after_net_profit_test=after_net,
        candidates=candidates,
    )


def _candidate(revenue_yoy: float = 237.4, profit_yoy: float = 88.0) -> FundamentalCandidate:
    return FundamentalCandidate(code="600519", name="测试", revenue_yoy=revenue_yoy, profit_yoy=profit_yoy)


def test_truncation_shown_separately_from_pass_count():
    out = FundamentalScreener.format_result(_result(after_net=137, candidates=[_candidate(), _candidate()]))
    assert "全部条件通过: 137" in out
    assert "截断输出前 2 只" in out
    # 首名成绩不得伪装成阈值出现在通过数行上
    assert "营收增长>237" not in out
    assert "利润增长>88" not in out


def test_no_truncation_line_when_all_shown():
    out = FundamentalScreener.format_result(_result(after_net=2, candidates=[_candidate(), _candidate()]))
    assert "全部条件通过: 2" in out
    assert "截断" not in out
