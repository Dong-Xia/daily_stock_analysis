# -*- coding: utf-8 -*-
"""
预计算热点板块分析存储服务

职责：
1. 存储每日收盘后预计算的热点板块分析结果（JSON）
2. 按日期查询已存储的分析
3. 获取最近可用的分析（自动跳过周末/节假日）
4. 定期清理 14 天前的旧数据
"""

import json
import logging
import os
import sqlite3
import threading
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "sector_analysis.db"
DEFAULT_RETENTION_DAYS = int(os.getenv("SECTOR_ANALYSIS_RETENTION_DAYS", "14"))


class SectorAnalysisStorage:
    """预计算热点板块分析的持久化存储（SQLite）"""

    def __init__(self, db_path: Optional[str] = None, retention_days: int = DEFAULT_RETENTION_DAYS):
        self.db_path = str(db_path or DEFAULT_DB_PATH)
        self.retention_days = retention_days
        self._lock = threading.RLock()
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, check_same_thread=False, timeout=10.0)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        with self._get_conn() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS sector_analysis (
                    analysis_date TEXT PRIMARY KEY,
                    data          TEXT NOT NULL,
                    sector_count  INTEGER DEFAULT 0,
                    created_at    TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_analysis_date
                ON sector_analysis(analysis_date DESC)
                """
            )
            conn.commit()

    def save(self, analysis_date: str, data: Dict[str, Any]) -> None:
        """存储某日的热点板块分析"""
        with self._lock:
            with self._get_conn() as conn:
                sectors = data.get("sectors", [])
                conn.execute(
                    """
                    INSERT OR REPLACE INTO sector_analysis
                    (analysis_date, data, sector_count, created_at)
                    VALUES (?, ?, ?, ?)
                    """,
                    (
                        analysis_date,
                        json.dumps(data, ensure_ascii=False),
                        len(sectors),
                        datetime.now().isoformat(),
                    ),
                )
                conn.commit()
                logger.info(
                    f"[SectorStorage] 已存储 {analysis_date} 的分析: "
                    f"{len(sectors)} 个板块"
                )
        self._cleanup_old()

    def get(self, analysis_date: str) -> Optional[Dict[str, Any]]:
        """获取某日的预计算分析"""
        with self._lock:
            with self._get_conn() as conn:
                cur = conn.execute(
                    "SELECT data FROM sector_analysis WHERE analysis_date = ?",
                    (analysis_date,),
                )
                row = cur.fetchone()
                if row:
                    return json.loads(row["data"])
                return None

    def get_latest_available(self, before_date: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        获取最近可用的分析数据。

        如果 before_date 为空，返回最近一条记录。
        如果指定了 before_date，返回不晚于该日期的最近一条。
        """
        with self._lock:
            with self._get_conn() as conn:
                if before_date:
                    cur = conn.execute(
                        "SELECT analysis_date, data FROM sector_analysis "
                        "WHERE analysis_date <= ? "
                        "ORDER BY analysis_date DESC LIMIT 1",
                        (before_date,),
                    )
                else:
                    cur = conn.execute(
                        "SELECT analysis_date, data FROM sector_analysis "
                        "ORDER BY analysis_date DESC LIMIT 1"
                    )
                row = cur.fetchone()
                if row:
                    logger.debug(f"[SectorStorage] 返回最近分析: {row['analysis_date']}")
                    return json.loads(row["data"])
                return None

    def get_available_dates(self, limit: int = 30) -> List[str]:
        """获取有预计算数据的日期列表"""
        with self._lock:
            with self._get_conn() as conn:
                cur = conn.execute(
                    "SELECT analysis_date FROM sector_analysis "
                    "ORDER BY analysis_date DESC LIMIT ?",
                    (limit,),
                )
                return [r["analysis_date"] for r in cur.fetchall()]

    def has_data(self, analysis_date: str) -> bool:
        """检查是否有某日的预计算数据"""
        with self._lock:
            with self._get_conn() as conn:
                cur = conn.execute(
                    "SELECT 1 FROM sector_analysis WHERE analysis_date = ? LIMIT 1",
                    (analysis_date,),
                )
                return cur.fetchone() is not None

    def _cleanup_old(self) -> None:
        """删除 retention_days 天前的旧数据"""
        cutoff = (datetime.now() - timedelta(days=self.retention_days)).strftime("%Y-%m-%d")
        with self._lock:
            with self._get_conn() as conn:
                cur = conn.execute(
                    "DELETE FROM sector_analysis WHERE analysis_date < ?",
                    (cutoff,),
                )
                deleted = cur.rowcount
                if deleted > 0:
                    conn.commit()
                    logger.info(f"[SectorStorage] 清理 {deleted} 条旧数据 (早于 {cutoff})")


_storage_instance: Optional[SectorAnalysisStorage] = None
_storage_lock = threading.Lock()


def get_sector_analysis_storage() -> SectorAnalysisStorage:
    global _storage_instance
    if _storage_instance is None:
        with _storage_lock:
            if _storage_instance is None:
                _storage_instance = SectorAnalysisStorage()
    return _storage_instance
