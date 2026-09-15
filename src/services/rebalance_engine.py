# -*- coding: utf-8 -*-
"""
Rebalance Engine - 持仓排名与调仓信号生成

  "去弱留强": rank by relative strength → bottom 20% reduce, top 50% hold/add
  "龙头切换": if sector leader rotated → exit follower, buy new leader
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class SignalType(str, Enum):
    BUY = "buy"
    ADD = "add"
    HOLD = "hold"
    REDUCE = "reduce"
    EXIT = "exit"
    ROTATE = "rotate"


@dataclass
class PositionRank:
    """Ranked position with performance metrics."""
    stock_code: str = ""
    stock_name: str = ""
    sector: str = ""
    cost_price: float = 0.0
    current_price: float = 0.0
    pnl_pct: float = 0.0
    rs_ratio: float = 1.0
    trend_score: float = 50.0
    rank: int = 0
    total_positions: int = 0
    percentile: float = 50.0
    recommendation: str = ""


@dataclass
class RebalanceSignal:
    """A specific action recommendation."""
    signal_type: SignalType = SignalType.HOLD
    stock_code: str = ""
    stock_name: str = ""
    current_price: float = 0.0
    pnl_pct: float = 0.0
    rank: int = 0
    percentile: float = 50.0
    reason: str = ""
    urgency: str = "normal"
    target_shares: int = 0
    target_pct: float = 0.0


@dataclass
class RebalanceResult:
    """Full rebalance analysis output."""
    timestamp: str = ""
    total_positions: int = 0
    rankings: List[PositionRank] = field(default_factory=list)
    signals: List[RebalanceSignal] = field(default_factory=list)
    summary: str = ""


class RebalanceEngine:
    """Position ranking and rebalance signal generator."""

    def __init__(
        self,
        hold_threshold_pct: float = 0.5,
        weak_threshold_pct: float = 0.2,
        leader_rs_threshold: float = 1.3,
        max_sector_positions: int = 3,
    ):
        self.hold_threshold_pct = hold_threshold_pct
        self.weak_threshold_pct = weak_threshold_pct
        self.leader_rs_threshold = leader_rs_threshold
        self.max_sector_positions = max_sector_positions

    def rank_positions(
        self,
        positions: List[Dict],
        sector_returns: Optional[Dict[str, float]] = None,
    ) -> List[PositionRank]:
        """Rank positions by Relative Strength (RS) vs sector."""
        sector_returns = sector_returns or {}
        ranked: List[PositionRank] = []

        for pos in positions:
            code = pos.get("code", "")
            name = pos.get("name", code)
            sector = pos.get("sector", "")
            cost = float(pos.get("cost_price", pos.get("current_price", 0)))
            price = float(pos.get("current_price", 0))
            stock_return = float(pos.get("return_pct", 0))
            trend = float(pos.get("trend_score", 50))

            if cost > 0:
                pnl = (price - cost) / cost * 100
            else:
                pnl = 0.0

            sector_ret = sector_returns.get(sector, stock_return) if sector else stock_return
            if abs(sector_ret) > 0.01:
                rs = stock_return / sector_ret
            else:
                rs = 1.0

            ranked.append(PositionRank(
                stock_code=code, stock_name=name, sector=sector,
                cost_price=cost, current_price=price, pnl_pct=round(pnl, 1),
                rs_ratio=round(rs, 3), trend_score=round(trend, 1),
            ))

        ranked.sort(key=lambda r: r.rs_ratio, reverse=True)
        total = max(len(ranked), 1)
        for i, r in enumerate(ranked):
            r.rank = i + 1
            r.total_positions = total
            r.percentile = round(100 - (i / total * 100), 0)

        return ranked

    def generate_signals(
        self, rankings: List[PositionRank], account_cash_pct: float = 0.0,
    ) -> List[RebalanceSignal]:
        """Generate trade signals from ranked positions."""
        signals: List[RebalanceSignal] = []
        total = max(len(rankings), 1)

        for r in rankings:
            percentile = r.percentile
            is_weak = percentile <= self.weak_threshold_pct * 100
            is_strong = percentile >= (1 - self.hold_threshold_pct) * 100

            if is_weak:
                if r.pnl_pct < -8:
                    signals.append(RebalanceSignal(
                        signal_type=SignalType.EXIT, stock_code=r.stock_code,
                        stock_name=r.stock_name, current_price=r.current_price,
                        pnl_pct=r.pnl_pct, rank=r.rank, percentile=r.percentile,
                        reason=f"弱股(排名{r.rank}/{total}) + 亏损{r.pnl_pct:.0f}% → 止损退出",
                        urgency="high",
                    ))
                else:
                    signals.append(RebalanceSignal(
                        signal_type=SignalType.REDUCE, stock_code=r.stock_code,
                        stock_name=r.stock_name, current_price=r.current_price,
                        pnl_pct=r.pnl_pct, rank=r.rank, percentile=r.percentile,
                        reason=f"弱势(排名{r.rank}/{total}) → 减仓50%",
                        urgency="medium", target_pct=50.0,
                    ))

            elif not is_strong:
                signals.append(RebalanceSignal(
                    signal_type=SignalType.HOLD, stock_code=r.stock_code,
                    stock_name=r.stock_name, current_price=r.current_price,
                    pnl_pct=r.pnl_pct, rank=r.rank, percentile=r.percentile,
                    reason=f"中间(排名{r.rank}/{total}) → 持有观察",
                    urgency="low",
                ))

            elif is_strong and r.rs_ratio > self.leader_rs_threshold:
                if r.pnl_pct > 5:
                    signals.append(RebalanceSignal(
                        signal_type=SignalType.ADD, stock_code=r.stock_code,
                        stock_name=r.stock_name, current_price=r.current_price,
                        pnl_pct=r.pnl_pct, rank=r.rank, percentile=r.percentile,
                        reason=f"领涨(RS={r.rs_ratio:.1f}) → 可加仓",
                        urgency="medium",
                    ))
                else:
                    signals.append(RebalanceSignal(
                        signal_type=SignalType.HOLD, stock_code=r.stock_code,
                        stock_name=r.stock_name, current_price=r.current_price,
                        pnl_pct=r.pnl_pct, rank=r.rank, percentile=r.percentile,
                        reason=f"强势(排名{r.rank}/{total}) → 持有",
                        urgency="low",
                    ))

            else:
                signals.append(RebalanceSignal(
                    signal_type=SignalType.HOLD, stock_code=r.stock_code,
                    stock_name=r.stock_name, current_price=r.current_price,
                    pnl_pct=r.pnl_pct, rank=r.rank, percentile=r.percentile,
                    reason=f"排名{r.rank}/{total} → 暂持",
                    urgency="low",
                ))

        exits = [s for s in signals if s.signal_type == SignalType.EXIT]
        if exits and account_cash_pct > 20:
            candidates = [r for r in rankings if r.percentile >= 80 and r.rs_ratio > 1.0]
            if candidates:
                target = candidates[0]
                signals.append(RebalanceSignal(
                    signal_type=SignalType.ROTATE, stock_code=target.stock_code,
                    stock_name=target.stock_name, current_price=target.current_price,
                    pnl_pct=target.pnl_pct, rank=target.rank, percentile=target.percentile,
                    reason=f"轮换至最强(RS={target.rs_ratio:.1f})",
                    urgency="medium",
                ))

        return signals

    def analyze(
        self, positions: List[Dict], sector_returns: Optional[Dict[str, float]] = None,
        account_cash_pct: float = 0.0,
    ) -> RebalanceResult:
        rankings = self.rank_positions(positions, sector_returns)
        signals = self.generate_signals(rankings, account_cash_pct)

        buy_signals = [s for s in signals if s.signal_type in (SignalType.BUY, SignalType.ADD, SignalType.ROTATE)]
        sell_signals = [s for s in signals if s.signal_type in (SignalType.REDUCE, SignalType.EXIT)]
        hold_count = len([s for s in signals if s.signal_type == SignalType.HOLD])

        summary = f"{len(rankings)}只持仓: 🔴卖{sell_signals}只 | 🟡持{hold_count}只 | 🟢加{buy_signals}只"

        return RebalanceResult(
            timestamp=datetime.now().isoformat(),
            total_positions=len(rankings),
            rankings=rankings,
            signals=signals,
            summary=summary,
        )

    @staticmethod
    def format_result(result: RebalanceResult) -> str:
        lines = [
            "📊 持仓调仓分析",
            f"{'='*60}",
            "",
            f"  排名:",
            f"  {'排名':<4} {'代码':<12} {'名称':<10} {'盈亏':>7} {'RS':>7} {'分类':>8}",
            f"  {'-'*50}",
        ]
        for r in result.rankings:
            pnl_marker = "🟢" if r.pnl_pct > 0 else "🔴"
            lines.append(
                f"  {r.rank:<4} {r.stock_code:<12} {r.stock_name:<10} "
                f"{pnl_marker}{r.pnl_pct:>+5.1f}% {r.rs_ratio:>6.2f}x {r.percentile:>7.0f}%"
            )

        lines.append("")
        lines.append(f"  信号 ({len(result.signals)}):")
        for s in result.signals:
            icon = {"buy":"🟢","add":"🟢","hold":"🟡","reduce":"🟠","exit":"🔴","rotate":"🔁"}.get(s.signal_type.value, "⚪")
            lines.append(f"  {icon} [{s.signal_type.value.upper():<6}] {s.stock_name} | {s.reason}")
        lines.append("")
        lines.append(f"  总结: {result.summary}")
        return "\n".join(lines)
