# -*- coding: utf-8 -*-
"""
选股结果缓存服务

职责：
1. 使用 SQLite 缓存个股筛选结果，按 (板块名称, 交易日) 键值
2. 收盘后同一板块同日查询直接返回缓存，避免重复调用数据源
3. 自动清理过期数据
"""
from __future__ import annotations

import json
import logging
import os
import sqlite3
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "screener_cache.db"
DEFAULT_RETENTION_DAYS = int(os.getenv("SCREENER_CACHE_RETENTION_DAYS", "7"))


class ScreenerCache:
    """基于交易日的选股结果缓存。

    缓存键: (sector_name, analysis_date)
    - sector_name: 板块名称, e.g. "半导体"
    - analysis_date: 有效交易日 (ISO, e.g. "2026-05-11")
    """

    def __init__(
        self,
        db_path: Optional[str] = None,
        retention_days: int = DEFAULT_RETENTION_DAYS,
    ) -> None:
        self.db_path = str(db_path or DEFAULT_DB_PATH)
        self.retention_days = retention_days
        self._lock = threading.RLock()
        self._conn: Optional[sqlite3.Connection] = None
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(self.db_path, check_same_thread=False, timeout=10.0)
            self._conn.row_factory = sqlite3.Row
        return self._conn

    def _init_db(self) -> None:
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        with self._lock:
            with self._get_conn() as conn:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS screener_cache (
                        sector_name   TEXT NOT NULL,
                        analysis_date TEXT NOT NULL,
                        data          TEXT NOT NULL,
                        created_at    TEXT NOT NULL,
                        PRIMARY KEY (sector_name, analysis_date)
                    )
                    """
                )
                conn.commit()

    def get(self, sector_name: str, analysis_date: str) -> Optional[dict]:
        """获取缓存的选股结果。

        Args:
            sector_name: 板块名称
            analysis_date: 交易日 (ISO 格式, e.g. "2026-05-11")

        Returns:
            缓存的结果字典或 None
        """
        with self._lock:
            with self._get_conn() as conn:
                cur = conn.execute(
                    "SELECT data, created_at FROM screener_cache "
                    "WHERE sector_name = ? AND analysis_date = ?",
                    (sector_name, analysis_date),
                )
                row = cur.fetchone()
                if not row:
                    return None

                logger.info(
                    "[ScreenerCache] 缓存命中 %s (%s), 创建于 %s",
                    sector_name,
                    analysis_date,
                    row["created_at"],
                )
                return json.loads(row["data"])

    def set(self, sector_name: str, analysis_date: str, result: dict) -> None:
        """写入选股结果到缓存。

        Args:
            sector_name: 板块名称
            analysis_date: 交易日 (ISO 格式)
            result: 选股结果 (可 JSON 序列化)
        """
        now = datetime.now().isoformat()
        data_json = json.dumps(result, ensure_ascii=False, default=str)

        with self._lock:
            with self._get_conn() as conn:
                conn.execute(
                    "INSERT OR REPLACE INTO screener_cache "
                    "(sector_name, analysis_date, data, created_at) "
                    "VALUES (?, ?, ?, ?)",
                    (sector_name, analysis_date, data_json, now),
                )
                conn.commit()
                logger.info(
                    "[ScreenerCache] 写入缓存 %s (%s)", sector_name, analysis_date
                )

        self._cleanup_old()

    def has(self, sector_name: str, analysis_date: str) -> bool:
        """检查缓存是否存在。"""
        with self._lock:
            with self._get_conn() as conn:
                cur = conn.execute(
                    "SELECT 1 FROM screener_cache "
                    "WHERE sector_name = ? AND analysis_date = ?",
                    (sector_name, analysis_date),
                )
                return cur.fetchone() is not None

    def _cleanup_old(self) -> None:
        """清理超过保留天数的缓存。"""
        cutoff = (datetime.now() - timedelta(days=self.retention_days)).isoformat()
        with self._lock:
            with self._get_conn() as conn:
                cur = conn.execute(
                    "DELETE FROM screener_cache WHERE created_at < ?", (cutoff,)
                )
                deleted = cur.rowcount
                if deleted > 0:
                    conn.commit()
                    logger.info(
                        "[ScreenerCache] 清理 %d 条过期缓存 (保留 %d 天)",
                        deleted,
                        self.retention_days,
                    )

    def clear(self) -> None:
        """清空所有缓存。"""
        with self._lock:
            with self._get_conn() as conn:
                conn.execute("DELETE FROM screener_cache")
                conn.commit()
                logger.info("[ScreenerCache] 缓存已清空")


_screener_cache_instance: Optional[ScreenerCache] = None
_screener_cache_lock = threading.Lock()


def get_screener_cache() -> ScreenerCache:
    """获取 ScreenerCache 单例。"""
    global _screener_cache_instance
    if _screener_cache_instance is None:
        with _screener_cache_lock:
            if _screener_cache_instance is None:
                _screener_cache_instance = ScreenerCache()
    return _screener_cache_instance
