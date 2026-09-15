# -*- coding: utf-8 -*-
"""
心法数据 Schema
"""

from typing import List, Optional
from pydantic import BaseModel, Field


class XinfaEntryCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200, description="标题")
    content: str = Field(..., min_length=1, description="正文（Markdown）")
    category: str = Field("general", description="分类: general/review/discipline/mindset/experience/plan")
    tags: Optional[List[str]] = Field(None, description="标签列表")
    stock_code: Optional[str] = Field(None, max_length=10, description="关联股票代码")
    stock_name: Optional[str] = Field(None, max_length=50, description="关联股票名称")
    sentiment: Optional[int] = Field(None, ge=1, le=5, description="情绪评分 1-5")
    is_starred: bool = Field(False, description="是否标星")


class XinfaEntryUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    content: Optional[str] = Field(None, min_length=1)
    category: Optional[str] = None
    tags: Optional[List[str]] = None
    stock_code: Optional[str] = None
    stock_name: Optional[str] = None
    sentiment: Optional[int] = Field(None, ge=1, le=5)
    is_starred: Optional[bool] = None


class XinfaEntryResponse(BaseModel):
    id: int
    title: str
    content: str
    category: str
    tags: Optional[str] = None
    stock_code: Optional[str] = None
    stock_name: Optional[str] = None
    sentiment: Optional[int] = None
    is_starred: bool = False
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    class Config:
        from_attributes = True


class XinfaEntryListResponse(BaseModel):
    total: int = Field(0, description="总数")
    items: List[XinfaEntryResponse] = Field(default_factory=list, description="条目列表")


class XinfaCategorySummary(BaseModel):
    category: str = Field(..., description="分类")
    count: int = Field(0, description="条目数")
    label: str = Field("", description="中文标签")
