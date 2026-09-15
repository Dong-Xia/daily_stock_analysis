# -*- coding: utf-8 -*-
"""
心法模块业务逻辑层
"""

import logging
from typing import Any, Dict, List, Optional

from src.repositories.xinfa_repo import XinfaRepository
from src.schemas.xinfa import (
    XinfaEntryCreate,
    XinfaEntryUpdate,
)

logger = logging.getLogger(__name__)


class XinfaService:
    """心法模块业务逻辑封装。"""

    def __init__(self, repo: Optional[XinfaRepository] = None):
        self.repo = repo or XinfaRepository()

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def create_entry(self, data: XinfaEntryCreate) -> Optional[Dict[str, Any]]:
        return self.repo.create(
            title=data.title,
            content=data.content,
            category=data.category,
            tags=data.tags,
            stock_code=data.stock_code,
            stock_name=data.stock_name,
            sentiment=data.sentiment,
            is_starred=data.is_starred,
        )

    def get_entry(self, entry_id: int) -> Optional[Dict[str, Any]]:
        return self.repo.get_by_id(entry_id)

    def update_entry(self, entry_id: int, data: XinfaEntryUpdate) -> bool:
        kwargs = data.model_dump(exclude_none=True)
        return self.repo.update(entry_id, **kwargs)

    def delete_entry(self, entry_id: int) -> bool:
        return self.repo.delete(entry_id)

    def list_entries(
        self,
        category: Optional[str] = None,
        keyword: Optional[str] = None,
        stock_code: Optional[str] = None,
        is_starred: Optional[bool] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Dict[str, Any]:
        offset = (page - 1) * page_size
        items, total = self.repo.list_entries(
            category=category,
            keyword=keyword,
            stock_code=stock_code,
            is_starred=is_starred,
            offset=offset,
            limit=page_size,
        )
        return {
            "total": total,
            "items": items,
            "page": page,
            "page_size": page_size,
        }

    def get_category_summary(self) -> List[Dict[str, Any]]:
        return self.repo.get_category_summary()

    def get_starred_entries(self, limit: int = 50) -> List[Dict[str, Any]]:
        return self.repo.get_starred_entries(limit)

    # ------------------------------------------------------------------
    # 格式化输出（供 CLI 使用）
    # ------------------------------------------------------------------

    @staticmethod
    def format_terminal(entry: Dict[str, Any]) -> str:
        lines = []
        lines.append(f"  {'='*60}")
        lines.append(f"  [{entry.get('id', '?')}] {entry.get('title', '')}")
        lines.append(f"  分类: {XinfaRepository.CATEGORY_LABELS.get(entry.get('category', 'general'), entry.get('category', ''))}")
        if entry.get("tags"):
            lines.append(f"  标签: {', '.join(entry['tags'])}")
        if entry.get("stock_code"):
            lines.append(f"  股票: {entry.get('stock_code')} {entry.get('stock_name') or ''}")
        if entry.get("sentiment"):
            stars = "★" * entry["sentiment"] + "☆" * (5 - entry["sentiment"])
            lines.append(f"  情绪: {stars}")
        if entry.get("is_starred"):
            lines.append("  ⭐ 已标星")
        lines.append(f"  时间: {entry.get('created_at', '')}")
        lines.append(f"  {'─'*60}")
        content = entry.get("content", "")
        if len(content) > 500:
            content = content[:500] + "...(截断)"
        lines.append(content)
        lines.append(f"  {'='*60}")
        return "\n".join(lines)

    @staticmethod
    def format_terminal_list(items: List[Dict[str, Any]], total: int) -> str:
        lines = [f"心法条目共 {total} 条:\n"]
        for i, item in enumerate(items, 1):
            cat_label = XinfaRepository.CATEGORY_LABELS.get(item.get("category", "general"), "")
            starred = " ⭐" if item.get("is_starred") else ""
            lines.append(
                f"  #{i} [{item.get('id')}] {item.get('title', '')} "
                f"({cat_label}){starred}"
            )
            if item.get("tags"):
                lines.append(f"      标签: {', '.join(item['tags'])}")
            if item.get("stock_code"):
                lines.append(f"      股票: {item['stock_code']} {item.get('stock_name') or ''}")
            lines.append(f"      时间: {item.get('created_at', '')}")
            lines.append("")
        return "\n".join(lines)
