# -*- coding: utf-8 -*-
"""
板块数据本地缓存服务

职责：
1. 使用 SQLite 缓存板块成分股数据，避免每次请求都实时爬取东财接口
2. 支持按板块名称+类型缓存，TTL 默认 24 小时
3. 提供 stale-while-revalidate 语义：即使缓存过期，仍返回旧数据并在后台更新
4. 启动时支持后台预热

表结构：
- board_members_cache: board_name, board_type, code, name, price, change_pct, updated_at
- cache_meta: key, value (存储全局元数据如 last_warmup_time)
"""

import json
import logging
import os
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Tuple

logger = logging.getLogger(__name__)

DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "sector_cache.db"
DEFAULT_TTL_HOURS = int(os.getenv("SECTOR_CACHE_TTL_HOURS", "24"))


class SectorCacheService:
    def __init__(self, db_path: Optional[str] = None, ttl_hours: int = DEFAULT_TTL_HOURS) -> None:
        self.db_path = str(db_path or DEFAULT_DB_PATH)
        self.ttl_hours = ttl_hours
        self._lock = threading.RLock()
        self._init_db()

    @contextmanager
    def _get_conn(self) -> Iterator[sqlite3.Connection]:
        """获取连接：退出 with 块时提交/回滚并关闭（sqlite3 的连接上下文管理器本身不会 close）。"""
        conn = sqlite3.connect(self.db_path, check_same_thread=False, timeout=10.0)
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            with conn:
                yield conn
        finally:
            conn.close()

    def _init_db(self) -> None:
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        with self._get_conn() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS board_members_cache (
                    board_name TEXT NOT NULL,
                    board_type TEXT NOT NULL,
                    code       TEXT NOT NULL,
                    name       TEXT,
                    price      REAL,
                    change_pct REAL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (board_name, board_type, code)
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_board_members_lookup
                ON board_members_cache(board_name, board_type)
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS cache_meta (
                    key   TEXT PRIMARY KEY,
                    value TEXT
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS sector_rankings_cache (
                    data          TEXT NOT NULL,
                    ranking_type  TEXT NOT NULL,
                    updated_at    TEXT NOT NULL
                )
                """
            )
            conn.commit()

    def get_board_members(
        self,
        board_name: str,
        board_type: str = "industry",
        accept_stale: bool = True,
    ) -> Optional[List[Dict[str, Any]]]:
        with self._lock:
            with self._get_conn() as conn:
                cur = conn.execute(
                    """
                    SELECT updated_at FROM board_members_cache
                    WHERE board_name = ? AND board_type = ?
                    LIMIT 1
                    """,
                    (board_name, board_type),
                )
                row = cur.fetchone()
                if not row:
                    return None

                updated_at = datetime.fromisoformat(row["updated_at"])
                expired = datetime.now() - updated_at > timedelta(hours=self.ttl_hours)

                if expired and not accept_stale:
                    return None

                cur = conn.execute(
                    """
                    SELECT code, name, price, change_pct
                    FROM board_members_cache
                    WHERE board_name = ? AND board_type = ?
                    """,
                    (board_name, board_type),
                )
                records = [dict(r) for r in cur.fetchall()]
                if not records:
                    return None

                if expired:
                    logger.info(
                        f"[SectorCache] 返回过期缓存 {board_name}({board_type}), "
                        f"上次更新 {updated_at.isoformat()}"
                    )
                else:
                    logger.debug(
                        f"[SectorCache] 缓存命中 {board_name}({board_type}), "
                        f"{len(records)} 条"
                    )
                return records

    def set_board_members(
        self,
        board_name: str,
        board_type: str,
        members: List[Dict[str, Any]],
    ) -> None:
        if not members:
            return

        now = datetime.now().isoformat()
        with self._lock:
            with self._get_conn() as conn:
                conn.execute(
                    "DELETE FROM board_members_cache WHERE board_name = ? AND board_type = ?",
                    (board_name, board_type),
                )
                rows = [
                    (
                        board_name,
                        board_type,
                        str(m.get("code", "")),
                        str(m.get("name", "")),
                        float(m.get("price", 0.0) or 0.0),
                        float(m.get("change_pct", 0.0) or 0.0),
                        now,
                    )
                    for m in members
                    if m.get("code")
                ]
                conn.executemany(
                    """
                    INSERT INTO board_members_cache
                    (board_name, board_type, code, name, price, change_pct, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    rows,
                )
                conn.commit()
                logger.info(
                    f"[SectorCache] 写入缓存 {board_name}({board_type}), {len(rows)} 条"
                )

    def is_cache_fresh(self, board_name: str, board_type: str = "industry") -> bool:
        with self._lock:
            with self._get_conn() as conn:
                cur = conn.execute(
                    "SELECT updated_at FROM board_members_cache WHERE board_name = ? AND board_type = ? LIMIT 1",
                    (board_name, board_type),
                )
                row = cur.fetchone()
                if not row:
                    return False
                updated_at = datetime.fromisoformat(row["updated_at"])
                return datetime.now() - updated_at <= timedelta(hours=self.ttl_hours)

    def get_meta(self, key: str, default: Optional[str] = None) -> Optional[str]:
        with self._lock:
            with self._get_conn() as conn:
                cur = conn.execute("SELECT value FROM cache_meta WHERE key = ?", (key,))
                row = cur.fetchone()
                return row["value"] if row else default

    def set_meta(self, key: str, value: str) -> None:
        with self._lock:
            with self._get_conn() as conn:
                conn.execute(
                    "INSERT OR REPLACE INTO cache_meta (key, value) VALUES (?, ?)",
                    (key, value),
                )
                conn.commit()

    def get_sector_rankings(self) -> Optional[Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]]:
        with self._lock:
            with self._get_conn() as conn:
                cur = conn.execute(
                    "SELECT updated_at FROM sector_rankings_cache LIMIT 1"
                )
                row = cur.fetchone()
                if not row:
                    return None
                updated_at = datetime.fromisoformat(row["updated_at"])
                if datetime.now() - updated_at > timedelta(hours=self.ttl_hours):
                    return None

                cur = conn.execute("SELECT data, ranking_type FROM sector_rankings_cache")
                top, bottom = [], []
                for r in cur.fetchall():
                    item = json.loads(r["data"])
                    if r["ranking_type"] == "top":
                        top.append(item)
                    else:
                        bottom.append(item)
                return top, bottom

    def get_sector_rankings_age_hours(self) -> Optional[float]:
        with self._lock:
            with self._get_conn() as conn:
                cur = conn.execute(
                    "SELECT updated_at FROM sector_rankings_cache LIMIT 1"
                )
                row = cur.fetchone()
                if not row:
                    return None
                updated_at = datetime.fromisoformat(row["updated_at"])
                return (datetime.now() - updated_at).total_seconds() / 3600

    def set_sector_rankings(
        self, top: List[Dict[str, Any]], bottom: List[Dict[str, Any]]
    ) -> None:
        now = datetime.now().isoformat()
        with self._lock:
            with self._get_conn() as conn:
                conn.execute("DELETE FROM sector_rankings_cache")
                rows = []
                for item in top:
                    rows.append((json.dumps(item, ensure_ascii=False), "top", now))
                for item in bottom:
                    rows.append((json.dumps(item, ensure_ascii=False), "bottom", now))
                conn.executemany(
                    "INSERT INTO sector_rankings_cache (data, ranking_type, updated_at) VALUES (?, ?, ?)",
                    rows,
                )
                conn.commit()

    def get_warmup_progress(self) -> Dict[str, Any]:
        last_warmup = self.get_meta("last_warmup_time")
        total_sectors = self.get_meta("warmup_total_sectors")
        completed_sectors = self.get_meta("warmup_completed_sectors")
        return {
            "last_warmup_time": last_warmup,
            "total_sectors": int(total_sectors or 0),
            "completed_sectors": int(completed_sectors or 0),
            "is_warming_up": self.get_meta("is_warming_up") == "true",
        }

    def clear_cache(self) -> None:
        with self._lock:
            with self._get_conn() as conn:
                conn.execute("DELETE FROM board_members_cache")
                conn.execute("DELETE FROM cache_meta")
                conn.commit()
                logger.info("[SectorCache] 缓存已清空")


_sector_cache_instance: Optional[SectorCacheService] = None
_sector_cache_lock = threading.Lock()


def get_sector_cache() -> SectorCacheService:
    global _sector_cache_instance
    if _sector_cache_instance is None:
        with _sector_cache_lock:
            if _sector_cache_instance is None:
                _sector_cache_instance = SectorCacheService()
    return _sector_cache_instance
