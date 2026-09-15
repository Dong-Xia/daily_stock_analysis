# -*- coding: utf-8 -*-
"""
持仓筹码体检接口

基于本地 3 年日线数据库的筹码引擎，对持仓清单输出减仓判定（🔴/🟠/🟡/⚪/🟢）。
规则依据 stockData/筹码策略回测报告.md；引擎见 src/services/chip_health_service.py。
"""

import logging

from fastapi import APIRouter, HTTPException

from api.v1.schemas.chip_health import (
    ChipHealthRunRequest,
    ChipHealthRunResponse,
    ChipHealthStatusResponse,
    HoldingsListResponse,
    HoldingsSaveRequest,
)
from src.services import chip_health_service
from src.services.chip_health_service import ChipHealthError

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get(
    "/status",
    response_model=ChipHealthStatusResponse,
    summary="筹码体检环境状态",
    description="返回数据目录、指标缓存是否存在及更新时间、已保存持仓数。",
)
def get_status():
    return chip_health_service.status()


@router.get(
    "/holdings",
    response_model=HoldingsListResponse,
    summary="读取已保存的持仓清单",
)
def get_holdings():
    rows = chip_health_service.load_saved_holdings()
    return {"holdings": rows, "count": len(rows)}


@router.put(
    "/holdings",
    response_model=HoldingsListResponse,
    summary="保存持仓清单(全量覆盖)",
)
def put_holdings(req: HoldingsSaveRequest):
    try:
        n = chip_health_service.save_holdings([h.model_dump() for h in req.holdings])
    except Exception as e:
        logger.exception("保存持仓清单失败")
        raise HTTPException(status_code=500, detail=f"保存失败: {e}") from e
    return {"holdings": req.holdings, "count": n}


@router.post(
    "/run",
    response_model=ChipHealthRunResponse,
    summary="执行持仓筹码体检",
    description="对持仓清单跑筹码引擎(子进程, 约10-60秒)。传 holdings 则临时体检, 不传用已保存清单。",
)
def run_check(req: ChipHealthRunRequest):
    holdings = [h.model_dump() for h in req.holdings] if req.holdings is not None else None
    try:
        out = chip_health_service.run_check(holdings)
    except ChipHealthError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        logger.exception("筹码体检执行失败")
        raise HTTPException(status_code=500, detail=f"体检失败: {e}") from e
    out["count"] = len(out.get("results", []))
    return out
