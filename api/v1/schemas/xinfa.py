# -*- coding: utf-8 -*-
"""
心法模块 API Schema
"""

from typing import List, Optional
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# 请求
# ---------------------------------------------------------------------------

class XinfaCreateRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=200, description="标题")
    content: str = Field(..., min_length=1, description="正文（Markdown）")
    category: str = Field("general", description="分类: general/review/discipline/mindset/experience/plan")
    tags: Optional[List[str]] = Field(None, description="标签列表")
    stock_code: Optional[str] = Field(None, max_length=10, description="关联股票代码")
    stock_name: Optional[str] = Field(None, max_length=50, description="关联股票名称")
    sentiment: Optional[int] = Field(None, ge=1, le=5, description="情绪评分 1-5")
    is_starred: bool = Field(False, description="是否标星")


class XinfaUpdateRequest(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    content: Optional[str] = Field(None, min_length=1)
    category: Optional[str] = None
    tags: Optional[List[str]] = None
    stock_code: Optional[str] = None
    stock_name: Optional[str] = None
    sentiment: Optional[int] = Field(None, ge=1, le=5)
    is_starred: Optional[bool] = None


class XinfaListParams(BaseModel):
    category: Optional[str] = Field(None, description="分类筛选")
    keyword: Optional[str] = Field(None, description="关键词搜索（标题/内容）")
    stock_code: Optional[str] = Field(None, max_length=10, description="关联股票代码筛选")
    is_starred: Optional[bool] = Field(None, description="仅标星")
    page: int = Field(1, ge=1, description="页码")
    page_size: int = Field(20, ge=1, le=100, description="每页条数")


# ---------------------------------------------------------------------------
# 响应
# ---------------------------------------------------------------------------

class XinfaEntryItem(BaseModel):
    id: int = Field(..., description="条目ID")
    title: str = Field(..., description="标题")
    content: str = Field(..., description="正文")
    category: str = Field("general", description="分类")
    tags: Optional[List[str]] = Field(None, description="标签列表")
    stock_code: Optional[str] = Field(None, description="关联股票代码")
    stock_name: Optional[str] = Field(None, description="关联股票名称")
    sentiment: Optional[int] = Field(None, description="情绪评分")
    is_starred: bool = Field(False, description="是否标星")
    created_at: Optional[str] = Field(None, description="创建时间")
    updated_at: Optional[str] = Field(None, description="更新时间")


class XinfaListResponse(BaseModel):
    total: int = Field(0, description="总数")
    items: List[XinfaEntryItem] = Field(default_factory=list, description="条目列表")
    page: int = Field(1, description="当前页码")
    page_size: int = Field(20, description="每页条数")


class XinfaCategorySummaryItem(BaseModel):
    category: str = Field(..., description="分类代码")
    count: int = Field(0, description="条目数")
    label: str = Field("", description="中文分类名")


class XinfaCategorySummaryResponse(BaseModel):
    categories: List[XinfaCategorySummaryItem] = Field(default_factory=list)


class XinfaDeleteResponse(BaseModel):
    success: bool = Field(..., description="是否成功")
