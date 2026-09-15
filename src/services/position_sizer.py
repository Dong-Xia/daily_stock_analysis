# -*- coding: utf-8 -*-
"""
Position Sizer - 动态仓位计算引擎

Risk-based position sizing using Kelly formula, regime scaling, and concentration limits.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class SizeRequest:
    """Input parameters for position sizing."""
    stock_code: str = ""
    stock_name: str = ""
    entry_price: float = 0.0
    stop_loss_price: float = 0.0
    account_equity: float = 0.0
    market_regime_factor: float = 0.5
    signal_confidence: int = 50
    max_positions: int = 5
    sector_count: int = 0
    risk_per_trade_pct: float = 2.0
    min_rr_ratio: float = 2.0
    target_rr_ratio: float = 2.0
    max_single_position_pct: float = 25.0
    max_sector_exposure_pct: float = 40.0


@dataclass
class SizeResult:
    """Output of position sizing calculation."""
    stock_code: str = ""
    stock_name: str = ""
    entry_price: float = 0.0
    stop_loss_price: float = 0.0
    risk_per_share: float = 0.0
    risk_adjusted_shares: int = 0
    risk_adjusted_cost: float = 0.0
    max_loss: float = 0.0
    equity_pct: float = 0.0
    kelly_fraction: float = 0.0
    kelly_shares: int = 0
    kelly_cost: float = 0.0
    half_kelly_shares: int = 0
    half_kelly_cost: float = 0.0
    recommended_shares: int = 0
    recommended_cost: float = 0.0
    recommended_pct: float = 0.0
    rationale: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


class PositionSizer:
    """Dynamic position sizing engine.

    Combines Kelly formula, regime-based scaling, and concentration
    limits to produce risk-adjusted position recommendations.
    """

    def __init__(
        self,
        risk_per_trade_pct: float = 2.0,
        min_rr_ratio: float = 1.5,
        target_rr_ratio: float = 2.0,
        max_single_position_pct: float = 25.0,
        max_sector_exposure_pct: float = 40.0,
        kelly_fraction: float = 0.5,
    ):
        self.risk_per_trade_pct = risk_per_trade_pct
        self.min_rr_ratio = min_rr_ratio
        self.target_rr_ratio = target_rr_ratio
        self.max_single_position_pct = max_single_position_pct
        self.max_sector_exposure_pct = max_sector_exposure_pct
        self.kelly_fraction = kelly_fraction

    def calculate(self, req: SizeRequest) -> SizeResult:
        """Compute position size from input parameters."""
        rationale: List[str] = []
        warnings: List[str] = []

        if req.entry_price <= 0 or req.stop_loss_price <= 0:
            return SizeResult(
                stock_code=req.stock_code,
                stock_name=req.stock_name,
                warnings=["买入价或止损价无效"],
                rationale=["无法计算: 价格参数为0"],
            )

        if req.account_equity <= 0:
            return SizeResult(
                stock_code=req.stock_code,
                stock_name=req.stock_name,
                warnings=["账户资金无效"],
                rationale=["无法计算: 账户资金为0"],
            )

        risk_per_share = abs(req.entry_price - req.stop_loss_price)
        if risk_per_share <= 0:
            warnings.append("止损价与买入价相同，无法计算风险")
            risk_per_share = req.entry_price * 0.01

        base_equity_per_position = req.account_equity / req.max_positions
        rationale.append(f"均分仓位: {req.account_equity:.0f}/{req.max_positions} = {base_equity_per_position:.0f}/只")

        regime_position_pct = req.market_regime_factor * req.max_single_position_pct / 100
        regime_equity = req.account_equity * regime_position_pct
        rationale.append(f"市场阶段调整: {req.market_regime_factor*100:.0f}% × {req.max_single_position_pct:.0f}% = {regime_equity:.0f}")

        max_risk_amount = req.account_equity * req.risk_per_trade_pct / 100
        risk_adjusted_shares = int(max_risk_amount / risk_per_share)
        risk_adjusted_cost = risk_adjusted_shares * req.entry_price
        risk_adjusted_pct = risk_adjusted_cost / req.account_equity * 100
        rationale.append(f"风控限制: 单笔最大亏损 {req.risk_per_trade_pct}% = {max_risk_amount:.0f}")
        rationale.append(f"  → {risk_adjusted_shares}股 × {req.entry_price:.2f} = {risk_adjusted_cost:.0f} ({risk_adjusted_pct:.1f}%)")

        if req.stop_loss_price > req.entry_price:
            warnings.append("止损价高于买入价(多头仓位)")
        if risk_adjusted_pct > req.max_single_position_pct:
            risk_adjusted_shares = int(regime_equity / req.entry_price)
            risk_adjusted_cost = risk_adjusted_shares * req.entry_price
            warnings.append(f"风控仓位超过上限({risk_adjusted_pct:.1f}%>{req.max_single_position_pct}%)，已裁剪")
            # 裁剪后同步比例，否则下面的板块上限检查会拿修剪前的旧值做判断，导致双重砍仓
            risk_adjusted_pct = risk_adjusted_cost / req.account_equity * 100

        sector_remaining = req.max_sector_exposure_pct
        if req.sector_count > 0:
            per_sector_max = req.max_sector_exposure_pct / max(req.sector_count, 1)
            if risk_adjusted_pct > per_sector_max:
                risk_adjusted_shares = int(req.account_equity * per_sector_max / 100 / req.entry_price)
                risk_adjusted_cost = risk_adjusted_shares * req.entry_price
                rationale.append(f"板块限制: 每板块≤{per_sector_max:.1f}% → {risk_adjusted_shares}股")

        max_loss = risk_adjusted_shares * risk_per_share
        equity_pct = risk_adjusted_cost / req.account_equity * 100 if req.account_equity > 0 else 0

        win_prob = req.signal_confidence / 100
        loss_prob = 1.0 - win_prob
        if win_prob > 0 and loss_prob > 0:
            raw_kelly = (win_prob * self.target_rr_ratio - loss_prob) / self.target_rr_ratio
            kelly = max(0.0, min(raw_kelly, 0.25))
        else:
            kelly = 0.0
        kelly_equity = req.account_equity * kelly
        kelly_shares = int(kelly_equity / req.entry_price) if req.entry_price > 0 else 0
        kelly_cost = kelly_shares * req.entry_price
        kelly_pct = kelly_equity / req.account_equity * 100 if req.account_equity > 0 else 0
        rationale.append(f"Kelly公式: f*={kelly:.3f} (p={win_prob:.0%}, R={self.target_rr_ratio})")
        rationale.append(f"  → 全Kelly={kelly_shares}股({kelly_pct:.1f}%)")

        half_kelly_shares = int(kelly_equity * self.kelly_fraction / req.entry_price) if req.entry_price > 0 else 0
        half_kelly_cost = half_kelly_shares * req.entry_price

        if req.signal_confidence >= 70 and req.market_regime_factor >= 0.70:
            recommended_shares = kelly_shares
            recommended_cost = kelly_cost
            rationale.append("高置信+进攻市场 → 使用全Kelly")
        elif req.signal_confidence >= 60:
            recommended_shares = half_kelly_shares
            recommended_cost = half_kelly_cost
            rationale.append(f"中等置信 → 使用{self.kelly_fraction*100:.0f}%Kelly")
        else:
            recommended_shares = int(risk_adjusted_shares * 0.5)
            recommended_cost = recommended_shares * req.entry_price
            rationale.append("低置信 → 半仓风控")

        max_allowed_cost = req.account_equity * regime_position_pct
        if recommended_cost > max_allowed_cost:
            recommended_shares = int(max_allowed_cost / req.entry_price)
            recommended_cost = recommended_shares * req.entry_price
            warnings.append(f"推荐仓位超过市场阶段上限，已裁剪至{regime_position_pct*100:.0f}%")

        recommended_pct = recommended_cost / req.account_equity * 100 if req.account_equity > 0 else 0

        if recommended_pct < 1.0:
            warnings.append(f"推荐仓位过低({recommended_pct:.1f}%)，可能不适合入场")

        return SizeResult(
            stock_code=req.stock_code,
            stock_name=req.stock_name,
            entry_price=req.entry_price,
            stop_loss_price=req.stop_loss_price,
            risk_per_share=round(risk_per_share, 2),
            risk_adjusted_shares=risk_adjusted_shares,
            risk_adjusted_cost=round(risk_adjusted_cost, 2),
            max_loss=round(max_loss, 2),
            equity_pct=round(equity_pct, 1),
            kelly_fraction=round(kelly, 4),
            kelly_shares=kelly_shares,
            kelly_cost=round(kelly_cost, 2),
            half_kelly_shares=half_kelly_shares,
            half_kelly_cost=round(half_kelly_cost, 2),
            recommended_shares=recommended_shares,
            recommended_cost=round(recommended_cost, 2),
            recommended_pct=round(recommended_pct, 1),
            rationale=rationale,
            warnings=warnings,
        )

    @staticmethod
    def format_terminal(result: SizeResult) -> str:
        """Format result as terminal-friendly string."""
        lines = [
            f"📊 {result.stock_name}({result.stock_code}) 仓位计算",
            "=" * 50,
            f"  买入价: {result.entry_price:.2f}  止损价: {result.stop_loss_price:.2f}",
            f"  每股风险: {result.risk_per_share:.2f}",
            f"  推荐仓位: {result.recommended_shares}股 ({result.recommended_pct:.1f}%)",
            f"  投入金额: {result.recommended_cost:.0f}",
            f"  最大亏损: {result.max_loss:.0f}",
            f"  Kelly系数: {result.kelly_fraction:.4f}  (全={result.kelly_shares}股, 半={result.half_kelly_shares}股)",
            "",
        ]
        if result.rationale:
            lines.append("  计算过程:")
            for r in result.rationale:
                lines.append(f"    {r}")
        if result.warnings:
            lines.append("")
            for w in result.warnings:
                lines.append(f"  ⚠️ {w}")
        return "\n".join(lines)
