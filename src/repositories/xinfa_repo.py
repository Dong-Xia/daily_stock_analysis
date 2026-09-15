# -*- coding: utf-8 -*-
"""
心法模块数据访问层
"""

import json
import logging
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import and_, desc, func, select

from src.storage import DatabaseManager, XinfaEntry

logger = logging.getLogger(__name__)


class XinfaRepository:
    """心法条目的数据库操作封装。"""

    CATEGORY_LABELS = {
        "general": "通用",
        "review": "复盘反思",
        "discipline": "交易纪律",
        "mindset": "心态建设",
        "experience": "经验总结",
        "plan": "交易计划",
    }

    VALID_CATEGORIES = set(CATEGORY_LABELS.keys())

    def __init__(self, db_manager: Optional[DatabaseManager] = None):
        self.db = db_manager or DatabaseManager.get_instance()

    # ------------------------------------------------------------------
    # 内部 helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _serialize_tags(tags: Optional[List[str]]) -> Optional[str]:
        if tags is None:
            return None
        return json.dumps(tags, ensure_ascii=False)

    @staticmethod
    def _deserialize_tags(raw: Optional[str]) -> Optional[List[str]]:
        if not raw:
            return None
        try:
            parsed = json.loads(raw)
            return parsed if isinstance(parsed, list) else None
        except (json.JSONDecodeError, TypeError):
            return None

    def _row_to_dict(self, row: XinfaEntry) -> Dict[str, Any]:
        d = row.to_dict()
        d["tags"] = self._deserialize_tags(row.tags)
        return d

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def create(
        self,
        title: str,
        content: str,
        category: str = "general",
        tags: Optional[List[str]] = None,
        stock_code: Optional[str] = None,
        stock_name: Optional[str] = None,
        sentiment: Optional[int] = None,
        is_starred: bool = False,
    ) -> Optional[Dict[str, Any]]:
        if category not in self.VALID_CATEGORIES:
            category = "general"
        if sentiment is not None and not (1 <= sentiment <= 5):
            sentiment = None

        def _write(session) -> Dict[str, Any]:
            entry = XinfaEntry(
                title=title,
                content=content,
                category=category,
                tags=self._serialize_tags(tags),
                stock_code=stock_code,
                stock_name=stock_name,
                sentiment=sentiment,
                is_starred=is_starred,
            )
            session.add(entry)
            session.flush()
            session.refresh(entry)
            return self._row_to_dict(entry)

        try:
            return self.db._run_write_transaction("xinfa_create", _write)
        except Exception as e:
            logger.error("创建心法条目失败: %s", e)
            return None

    def get_by_id(self, entry_id: int) -> Optional[Dict[str, Any]]:
        with self.db.get_session() as session:
            row = session.execute(
                select(XinfaEntry).where(XinfaEntry.id == entry_id)
            ).scalar_one_or_none()
            return self._row_to_dict(row) if row else None

    def update(
        self,
        entry_id: int,
        **kwargs,
    ) -> bool:
        allowed_keys = {
            "title", "content", "category", "tags",
            "stock_code", "stock_name", "sentiment", "is_starred",
        }
        updates = {k: v for k, v in kwargs.items() if k in allowed_keys and v is not None}
        if not updates:
            return False

        if "category" in updates and updates["category"] not in self.VALID_CATEGORIES:
            updates.pop("category")
        if "sentiment" in updates and not (1 <= updates["sentiment"] <= 5):
            updates.pop("sentiment")
        if "tags" in updates:
            updates["tags"] = self._serialize_tags(updates["tags"])

        def _write(session) -> bool:
            row = session.execute(
                select(XinfaEntry).where(XinfaEntry.id == entry_id)
            ).scalar_one_or_none()
            if row is None:
                return False
            for key, val in updates.items():
                setattr(row, key, val)
            return True

        try:
            return self.db._run_write_transaction("xinfa_update", _write)
        except Exception as e:
            logger.error("更新心法条目失败: %s", e)
            return False

    def delete(self, entry_id: int) -> bool:
        def _write(session) -> bool:
            row = session.execute(
                select(XinfaEntry).where(XinfaEntry.id == entry_id)
            ).scalar_one_or_none()
            if row is None:
                return False
            session.delete(row)
            return True

        try:
            return self.db._run_write_transaction("xinfa_delete", _write)
        except Exception as e:
            logger.error("删除心法条目失败: %s", e)
            return False

    # ------------------------------------------------------------------
    # 查询
    # ------------------------------------------------------------------

    def list_entries(
        self,
        category: Optional[str] = None,
        keyword: Optional[str] = None,
        stock_code: Optional[str] = None,
        is_starred: Optional[bool] = None,
        offset: int = 0,
        limit: int = 20,
    ) -> Tuple[List[Dict[str, Any]], int]:
        with self.db.get_session() as session:
            conditions = []
            if category and category in self.VALID_CATEGORIES:
                conditions.append(XinfaEntry.category == category)
            if stock_code:
                conditions.append(XinfaEntry.stock_code == stock_code)
            if is_starred is not None:
                conditions.append(XinfaEntry.is_starred == is_starred)
            if keyword:
                like = f"%{keyword}%"
                conditions.append(
                    XinfaEntry.title.ilike(like) | XinfaEntry.content.ilike(like)
                )

            where_clause = and_(*conditions) if conditions else True

            total = session.execute(
                select(func.count(XinfaEntry.id)).where(where_clause)
            ).scalar() or 0

            rows = session.execute(
                select(XinfaEntry)
                .where(where_clause)
                .order_by(desc(XinfaEntry.created_at))
                .offset(offset)
                .limit(limit)
            ).scalars().all()

            items = [self._row_to_dict(r) for r in rows]
            return items, total

    def get_category_summary(self) -> List[Dict[str, Any]]:
        with self.db.get_session() as session:
            rows = session.execute(
                select(
                    XinfaEntry.category,
                    func.count(XinfaEntry.id).label("count"),
                )
                .group_by(XinfaEntry.category)
                .order_by(desc("count"))
            ).all()

            results = []
            for r in rows:
                cat = r.category or "general"
                results.append({
                    "category": cat,
                    "count": r.count,
                    "label": self.CATEGORY_LABELS.get(cat, cat),
                })
            return results

    def get_starred_entries(self, limit: int = 50) -> List[Dict[str, Any]]:
        with self.db.get_session() as session:
            rows = session.execute(
                select(XinfaEntry)
                .where(XinfaEntry.is_starred.is_(True))
                .order_by(desc(XinfaEntry.updated_at))
                .limit(limit)
            ).scalars().all()
            return [self._row_to_dict(r) for r in rows]
