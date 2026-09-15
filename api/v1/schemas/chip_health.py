# -*- coding: utf-8 -*-
"""筹码体检接口模型"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class HoldingItem(BaseModel):
    code: str = Field(..., description="6位股票代码", example="600519")
    name: Optional[str] = Field("", description="股票名称(可空,自动补全)")
    cost: Optional[float] = Field(None, description="成本价(可空,填了计算浮盈)")


class HoldingsSaveRequest(BaseModel):
    holdings: List[HoldingItem] = Field(default_factory=list, description="持仓清单(全量覆盖保存)")


class HoldingsListResponse(BaseModel):
    holdings: List[HoldingItem]
    count: int


class ChipHealthRunRequest(BaseModel):
    holdings: Optional[List[HoldingItem]] = Field(
        None, description="临时体检清单(不传则用已保存的持仓清单)")


class ChipHealthRunResponse(BaseModel):
    generated_at: str
    data_cutoff: str = Field("", description="缓存数据截止日")
    results: List[Dict[str, Any]]
    skipped: List[Dict[str, Any]] = Field(default_factory=list)
    count: int = 0


class ChipHealthStatusResponse(BaseModel):
    data_dir: str
    cache_exists: bool
    cache_mtime: Optional[str] = None
    holdings_count: int = 0
    holdings_file: str = ""
