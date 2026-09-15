# -*- coding: utf-8 -*-
"""
心法模块 API 端点
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from api.v1.schemas.common import ErrorResponse
from api.v1.schemas.xinfa import (
    XinfaCreateRequest,
    XinfaUpdateRequest,
    XinfaListResponse,
    XinfaEntryItem,
    XinfaCategorySummaryResponse,
    XinfaCategorySummaryItem,
    XinfaDeleteResponse,
)
from src.services.xinfa_service import XinfaService

logger = logging.getLogger(__name__)
router = APIRouter()


def _entry_to_item(entry: dict) -> XinfaEntryItem:
    return XinfaEntryItem(
        id=entry["id"],
        title=entry["title"],
        content=entry["content"],
        category=entry.get("category", "general"),
        tags=entry.get("tags"),
        stock_code=entry.get("stock_code"),
        stock_name=entry.get("stock_name"),
        sentiment=entry.get("sentiment"),
        is_starred=entry.get("is_starred", False),
        created_at=entry.get("created_at"),
        updated_at=entry.get("updated_at"),
    )


@router.post(
    "",
    response_model=XinfaEntryItem,
    responses={
        201: {"description": "创建成功"},
        400: {"description": "参数错误", "model": ErrorResponse},
        500: {"description": "服务器错误", "model": ErrorResponse},
    },
    summary="创建心法条目",
    description="新增一条炒股心得记录。",
)
def create_xinfa(data: XinfaCreateRequest) -> XinfaEntryItem:
    try:
        svc = XinfaService()
        entry = svc.create_entry(data)
        if entry is None:
            raise HTTPException(status_code=500, detail={"error": "create_failed", "message": "创建心法条目失败"})
        return _entry_to_item(entry)
    except HTTPException:
        raise
    except Exception as e:
        logger.error("创建心法条目异常: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail={"error": "internal_error", "message": str(e)})


@router.get(
    "",
    response_model=XinfaListResponse,
    responses={
        200: {"description": "条目列表"},
        500: {"description": "服务器错误", "model": ErrorResponse},
    },
    summary="获取心法列表",
    description="分页查询心法条目，支持分类、关键词搜索、股票代码筛选。",
)
def list_xinfa(
    category: Optional[str] = Query(None, description="分类筛选"),
    keyword: Optional[str] = Query(None, description="关键词搜索"),
    stock_code: Optional[str] = Query(None, max_length=10, description="关联股票代码"),
    is_starred: Optional[bool] = Query(None, description="仅标星"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页条数"),
) -> XinfaListResponse:
    try:
        svc = XinfaService()
        result = svc.list_entries(
            category=category,
            keyword=keyword,
            stock_code=stock_code,
            is_starred=is_starred,
            page=page,
            page_size=page_size,
        )
        return XinfaListResponse(
            total=result["total"],
            items=[_entry_to_item(item) for item in result["items"]],
            page=result["page"],
            page_size=result["page_size"],
        )
    except Exception as e:
        logger.error("查询心法列表异常: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail={"error": "internal_error", "message": str(e)})


@router.get(
    "/categories",
    response_model=XinfaCategorySummaryResponse,
    responses={
        200: {"description": "分类统计"},
        500: {"description": "服务器错误", "model": ErrorResponse},
    },
    summary="获取心法分类统计",
    description="返回各分类的条目数量。",
)
def get_categories() -> XinfaCategorySummaryResponse:
    try:
        svc = XinfaService()
        cats = svc.get_category_summary()
        return XinfaCategorySummaryResponse(
            categories=[XinfaCategorySummaryItem(**c) for c in cats]
        )
    except Exception as e:
        logger.error("获取心法分类统计异常: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail={"error": "internal_error", "message": str(e)})


@router.get(
    "/starred",
    response_model=XinfaListResponse,
    responses={
        200: {"description": "标星条目列表"},
        500: {"description": "服务器错误", "model": ErrorResponse},
    },
    summary="获取标星心法",
    description="返回所有标星的心法条目。",
)
def list_starred(
    limit: int = Query(50, ge=1, le=200, description="返回条数上限"),
) -> XinfaListResponse:
    try:
        svc = XinfaService()
        items = svc.get_starred_entries(limit)
        return XinfaListResponse(
            total=len(items),
            items=[_entry_to_item(item) for item in items],
            page=1,
            page_size=limit,
        )
    except Exception as e:
        logger.error("获取标星心法异常: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail={"error": "internal_error", "message": str(e)})


@router.get(
    "/{entry_id}",
    response_model=XinfaEntryItem,
    responses={
        200: {"description": "条目详情"},
        404: {"description": "条目不存在", "model": ErrorResponse},
        500: {"description": "服务器错误", "model": ErrorResponse},
    },
    summary="获取心法详情",
    description="根据 ID 获取单条心法条目。",
)
def get_xinfa(entry_id: int) -> XinfaEntryItem:
    try:
        svc = XinfaService()
        entry = svc.get_entry(entry_id)
        if entry is None:
            raise HTTPException(status_code=404, detail={"error": "not_found", "message": f"心法条目 {entry_id} 不存在"})
        return _entry_to_item(entry)
    except HTTPException:
        raise
    except Exception as e:
        logger.error("获取心法条目异常: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail={"error": "internal_error", "message": str(e)})


@router.put(
    "/{entry_id}",
    response_model=dict,
    responses={
        200: {"description": "更新成功"},
        404: {"description": "条目不存在", "model": ErrorResponse},
        500: {"description": "服务器错误", "model": ErrorResponse},
    },
    summary="更新心法条目",
    description="更新指定心法条目的字段。",
)
def update_xinfa(entry_id: int, data: XinfaUpdateRequest) -> dict:
    try:
        svc = XinfaService()
        ok = svc.update_entry(entry_id, data)
        if not ok:
            raise HTTPException(status_code=404, detail={"error": "not_found", "message": f"心法条目 {entry_id} 不存在"})
        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("更新心法条目异常: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail={"error": "internal_error", "message": str(e)})


@router.delete(
    "/{entry_id}",
    response_model=XinfaDeleteResponse,
    responses={
        200: {"description": "删除成功"},
        404: {"description": "条目不存在", "model": ErrorResponse},
        500: {"description": "服务器错误", "model": ErrorResponse},
    },
    summary="删除心法条目",
    description="删除指定心法条目。",
)
def delete_xinfa(entry_id: int) -> XinfaDeleteResponse:
    try:
        svc = XinfaService()
        ok = svc.delete_entry(entry_id)
        if not ok:
            raise HTTPException(status_code=404, detail={"error": "not_found", "message": f"心法条目 {entry_id} 不存在"})
        return XinfaDeleteResponse(success=True)
    except HTTPException:
        raise
    except Exception as e:
        logger.error("删除心法条目异常: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail={"error": "internal_error", "message": str(e)})
