# -*- coding: utf-8 -*-
"""
===================================
Stock Screener - Pydantic Schema
===================================

Defines data models for the market regime classifier and stock screener module.
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class MarketRegime(str, Enum):
    """市场状态枚举 — 7 种阶段"""

    BULL_TREND = "bull_trend"
    BULL_CONSOLIDATION = "bull_consolidation"
    RANGE_BOUND = "range_bound"
    BEAR_CONSOLIDATION = "bear_consolidation"
    BEAR_TREND = "bear_trend"
    BOTTOM_REVERSAL = "bottom_reversal"
    EXTREME_SENTIMENT = "extreme_sentiment"


# ── Regime labels (CN) ──────────────────────────────────────

_REGIME_LABELS_CN: Dict[MarketRegime, str] = {
    MarketRegime.BULL_TREND: "主升趋势",
    MarketRegime.BULL_CONSOLIDATION: "震荡上行",
    MarketRegime.RANGE_BOUND: "横盘震荡",
    MarketRegime.BEAR_CONSOLIDATION: "震荡下行",
    MarketRegime.BEAR_TREND: "主跌趋势",
    MarketRegime.BOTTOM_REVERSAL: "底部反转",
    MarketRegime.EXTREME_SENTIMENT: "情绪极端",
}

_REGIME_RECOMMENDATIONS: Dict[MarketRegime, str] = {
    MarketRegime.BULL_TREND: "进攻策略：指数共振+成交放量，可提高仓位至80%",
    MarketRegime.BULL_CONSOLIDATION: "均衡偏进攻：趋势向好但量能不足，仓位≤60%",
    MarketRegime.RANGE_BOUND: "均衡策略：方向不明，控制仓位≤40%，精选个股",
    MarketRegime.BEAR_CONSOLIDATION: "防御为主：弱势反弹，仓位≤20%或观望",
    MarketRegime.BEAR_TREND: "空仓防守：空头排列，建议≤10%或空仓",
    MarketRegime.BOTTOM_REVERSAL: "试探性建仓：信号初现，仓位≤50%，确认后加仓",
    MarketRegime.EXTREME_SENTIMENT: "减仓警惕：情绪极端，无论方向建议减仓至≤40%",
}

# ── Position factor range per regime ─────────────────────────

_DEFAULT_POSITION_FACTORS: Dict[MarketRegime, tuple[float, float]] = {
    MarketRegime.BULL_TREND: (0.85, 1.00),
    MarketRegime.BULL_CONSOLIDATION: (0.60, 0.80),
    MarketRegime.RANGE_BOUND: (0.30, 0.50),
    MarketRegime.BEAR_CONSOLIDATION: (0.20, 0.40),
    MarketRegime.BEAR_TREND: (0.00, 0.20),
    MarketRegime.BOTTOM_REVERSAL: (0.50, 0.70),
    MarketRegime.EXTREME_SENTIMENT: (0.20, 0.60),
}


def get_regime_label(regime: MarketRegime) -> str:
    return _REGIME_LABELS_CN.get(regime, "未知")


def get_regime_recommendation(regime: MarketRegime) -> str:
    return _REGIME_RECOMMENDATIONS.get(regime, "")


def get_position_factor_range(regime: MarketRegime) -> tuple[float, float]:
    return _DEFAULT_POSITION_FACTORS.get(regime, (0.30, 0.50))


# ── Pydantic Models ──────────────────────────────────────────


class DimensionEvidence(BaseModel):
    """单维度分析证据"""

    model_config = ConfigDict(extra="forbid")

    dimension: str = Field(description="维度名称, e.g. trend/volume/breadth/volatility/sentiment")
    score: float = Field(default=0.0, ge=0.0, le=100.0, description="维度得分 0-100")
    signal: str = Field(default="", description="信号标签 e.g. bullish/bearish/neutral/extreme")
    detail: str = Field(default="", description="说明文字")


class RegimeResult(BaseModel):
    """市场状态分类结果"""

    model_config = ConfigDict(extra="allow")

    regime: MarketRegime = Field(description="市场阶段枚举")
    regime_label: str = Field(default="", description="中文标签")
    confidence: int = Field(default=50, ge=0, le=100, description="综合置信度 0-100")
    position_factor: float = Field(default=0.5, ge=0.0, le=1.0, description="推荐最高仓位比例")
    recommendation: str = Field(default="", description="操作建议")
    evidence: List[DimensionEvidence] = Field(default_factory=list, description="各维度证据列表")


class FactorBreakdown(BaseModel):
    """个股多因子评分明细"""

    model_config = ConfigDict(extra="forbid")

    trend_strength: Optional[float] = Field(default=None, description="趋势强度得分 0-100")
    rs_score: Optional[float] = Field(default=None, description="相对强度得分 0-100")
    volume_confirmation: Optional[float] = Field(default=None, description="量能确认得分 0-100")
    bias_from_ma5: Optional[float] = Field(default=None, description="乖离率得分 0-100")
    limit_up_proximity: Optional[float] = Field(default=None, description="涨停距离得分 0-100")
    sector_leadership: Optional[float] = Field(default=None, description="板块龙头得分 0-100")
    composite_score: float = Field(default=0.0, description="综合加权得分")


class ScreenerCriteria(BaseModel):
    """选股筛选条件"""

    model_config = ConfigDict(extra="forbid")

    sector_name: Optional[str] = Field(default=None, description="目标板块名称")
    min_avg_amount_yi: float = Field(default=1.0, ge=0.1, description="日均成交额最低门槛(亿)")
    min_turnover_rate: float = Field(default=1.0, ge=0.1, description="最低换手率(%)")
    rs_lookback_days: int = Field(default=20, ge=5, le=120, description="RS计算回看天数")
    top_n_ratio: float = Field(default=0.3, ge=0.05, le=1.0, description="板块内Top保留比例")
    max_candidates: int = Field(default=10, ge=1, le=50, description="最大输出候选数")
    require_ma_alignment: bool = Field(default=True, description="是否要求均线多头排列")
    backtest_date: Optional[str] = Field(default=None, description="回测日期 YYYY-MM-DD")


class ScreenerCandidate(BaseModel):
    """选股候选股票"""

    model_config = ConfigDict(extra="forbid")

    code: str = Field(description="股票代码")
    name: str = Field(default="", description="股票名称")
    price: float = Field(default=0.0, description="当前价格")
    change_pct: float = Field(default=0.0, description="涨跌幅%")
    factors: FactorBreakdown = Field(default_factory=FactorBreakdown, description="多因子评分明细")
    ma_alignment: str = Field(default="", description="均线排列: bullish/bearish/neutral")
    turnover_rate: float = Field(default=0.0, description="换手率%")
    avg_amount_yi: float = Field(default=0.0, description="日均成交额(亿)")
    sector_name: str = Field(default="", description="所属板块")
    is_leader: bool = Field(default=False, description="是否为板块龙头")


class ScreenerResult(BaseModel):
    """选股完整结果"""

    model_config = ConfigDict(extra="forbid")

    regime: Optional[RegimeResult] = Field(default=None, description="当前市场状态")
    candidates: List[ScreenerCandidate] = Field(default_factory=list, description="候选股票列表")
    total_considered: int = Field(default=0, description="原始候选数")
    after_liquidity: int = Field(default=0, description="流动性筛选后")
    after_trend: int = Field(default=0, description="趋势筛选后")
    after_ranking: int = Field(default=0, description="排名筛选后")
    sector_name: str = Field(default="", description="筛选板块")
    timestamp: str = Field(default="", description="时间戳 ISO-8601")
    mode: str = Field(default="realtime", description="模式: realtime/backtest")
