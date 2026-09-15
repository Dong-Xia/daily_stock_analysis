# -*- coding: utf-8 -*-
"""
热点板块 API Schema
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class SectorStockItem(BaseModel):
    code: str = Field(..., description="股票代码")
    name: str = Field(..., description="股票名称")
    change_pct: float = Field(0.0, description="涨跌幅 (%)")
    price: float = Field(0.0, description="最新价")
    is_limit_up: bool = Field(False, description="是否涨停")
    consecutive_limit_up_days: int = Field(0, description="连续涨停天数")


class LimitUpLadderItem(BaseModel):
    days: int = Field(..., description="连板天数")
    stock_code: str = Field(..., description="股票代码")
    stock_name: str = Field(..., description="股票名称")


class RelatedStockItem(BaseModel):
    code: str = Field("", description="股票代码")
    name: str = Field(..., description="股票名称")


class HotSectorItem(BaseModel):
    name: str = Field(..., description="板块名称")
    change_pct: float = Field(0.0, description="板块涨跌幅 (%)")
    limit_up_count: int = Field(0, description="涨停家数")
    limit_up_stocks: List[SectorStockItem] = Field(default_factory=list, description="涨停股列表")
    ladder: List[LimitUpLadderItem] = Field(default_factory=list, description="连板梯队")
    leader: Optional[SectorStockItem] = Field(None, description="龙头股")
    leader_correlation: float = Field(0.0, description="龙头带动效应（相关系数均值）")
    score: float = Field(0.0, description="热点分数")
    catalyst: Optional[str] = Field(None, description="核心催化逻辑")
    effect_summary: Optional[str] = Field(None, description="带动效应总结")
    related_stocks: List[RelatedStockItem] = Field(default_factory=list, description="联动标的列表")
    # 游资方法论增强字段
    topic_level: str = Field("未知", description="题材级别：国家级/行业级/个股消息")
    topic_level_score: int = Field(0, description="题材级别得分")
    lifecycle: str = Field("未知", description="题材生命周期：低位试错/主升期/强势轮动/脉冲")
    sentiment_multiplier: float = Field(1.0, description="情绪乘数（0.7-1.3），基于全市场涨停家数")
    index_resonance: float = Field(0.0, description="指数共振得分（0-15），板块相对前排平均的强弱")


class HotSectorsResponse(BaseModel):
    date: str = Field(..., description="分析日期")
    sectors: List[HotSectorItem] = Field(default_factory=list, description="热点板块列表")
    total: int = Field(0, description="总数")
    cache_status: str = Field("unknown", description="缓存状态: ready/warming_up/empty")


class SectorRankingItem(BaseModel):
    name: str = Field(..., description="板块名称")
    change_pct: float = Field(0.0, description="涨跌幅 (%)")


class SectorRankingsResponse(BaseModel):
    market: str = Field("cn", description="市场")
    top: List[SectorRankingItem] = Field(default_factory=list, description="领涨板块")
    bottom: List[SectorRankingItem] = Field(default_factory=list, description="领跌板块")


class ManualSectorInput(BaseModel):
    text: str = Field(..., description="用户输入的Markdown/纯文本复盘内容", max_length=50000)
    date: Optional[str] = Field(None, description="分析日期（YYYY-MM-DD），默认今日")


class ScraperSectorRankingItem(BaseModel):
    code: str = Field("", description="板块代码")
    name: str = Field("", description="板块名称")
    change_pct: float = Field(0.0, description="涨跌幅 (%)")
    rank_type: str = Field("", description="top/bottom")
    leader: str = Field("", description="领涨股")

class ScraperLimitUpItem(BaseModel):
    code: str = Field("", description="股票代码")
    name: str = Field("", description="股票名称")
    price: float = Field(0.0, description="最新价")
    change_pct: float = Field(0.0, description="涨跌幅 (%)")
    consecutive_days: int = Field(0, description="连板天数")
    industry: str = Field("", description="所属行业")


class ScraperSectorStockItem(BaseModel):
    code: str = Field("", description="股票代码")
    name: str = Field("", description="股票名称")
    change_pct: float = Field(0.0, description="涨跌幅 (%)")
    price: float = Field(0.0, description="最新价")


class ScraperSectorDetailItem(BaseModel):
    sector_code: str = Field("", description="板块代码")
    sector_name: str = Field("", description="板块名称")
    sector_change_pct: float = Field(0.0, description="板块涨跌幅 (%)")
    limit_up_count: int = Field(0, description="涨停家数")
    limit_down_count: int = Field(0, description="跌停家数")
    limit_up_stocks: List[ScraperSectorStockItem] = Field(default_factory=list)
    limit_down_stocks: List[ScraperSectorStockItem] = Field(default_factory=list)

class ScraperLadderStockItem(BaseModel):
    code: str = Field("", description="股票代码")
    name: str = Field("", description="股票名称")
    price: float = Field(0.0, description="最新价")
    change_pct: float = Field(0.0, description="涨跌幅 (%)")

class ScraperLadderTierItem(BaseModel):
    days: int = Field(..., description="连板天数")
    stocks: List[ScraperLadderStockItem] = Field(default_factory=list, description="该梯队股票列表")

class ScraperBoardDataResponse(BaseModel):
    date: str = Field(..., description="数据日期")
    sector_rankings: List[ScraperSectorRankingItem] = Field(default_factory=list)
    limit_up_pool: List[ScraperLimitUpItem] = Field(default_factory=list)
    sector_stocks: List[ScraperSectorDetailItem] = Field(default_factory=list)
    board_ladder: List[ScraperLadderTierItem] = Field(default_factory=list, description="连板梯队")

class ManualSectorParseResponse(BaseModel):
    date: str
    sectors: List[HotSectorItem] = Field(default_factory=list)
    total: int = Field(0, description="解析出的板块数量")
    parse_info: Optional[Dict[str, Any]] = Field(None, description="解析元信息，如检测到的板块数、涨停股数等")
