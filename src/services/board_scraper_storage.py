"""
Board Scraper 数据存储模块。

将 BoardScraperFetcher 抓取的数据持久化到:
1. CSV 文件 (data/board_scraper/ 目录，按日期命名)
2. SQLite 数据库 (data/board_scraper.db)

遵循项目现有的存储模式:
- CSV 使用 pandas 输出，便于用户本地复盘分析
- SQLite 使用 raw sqlite3 + RLock（与 sector_analysis_storage.py 一致）
- 保留最近 N 天的数据（默认 14 天，与 SECTOR_ANALYSIS_RETENTION_DAYS 一致）
"""

import csv
import logging
import os
import sqlite3
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

logger = logging.getLogger(__name__)

# 数据存储根目录
DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
BOARD_SCRAPER_DIR = DATA_DIR / "board_scraper"
DB_PATH = DATA_DIR / "board_scraper.db"

# 保留天数
RETENTION_DAYS = 14


class BoardScraperStorage:
    """
    Board scraper data persistence.

    Stores scraped market data in two formats:
    - CSV files by date for easy analysis
    - SQLite database for programmatic access with history
    """

    def __init__(self, data_dir: Optional[Path] = None):
        self._data_dir = Path(data_dir) if data_dir else BOARD_SCRAPER_DIR
        self._lock = threading.RLock()
        self._db_path = str(self._data_dir.parent / "board_scraper.db")
        self._ensure_dirs()
        self._init_db()

    def _ensure_dirs(self) -> None:
        """Create data directories if they don't exist."""
        self._data_dir.mkdir(parents=True, exist_ok=True)

    # ---------- SQLite ----------

    def _get_conn(self) -> sqlite3.Connection:
        """Get a thread-safe SQLite connection."""
        conn = sqlite3.connect(self._db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        return conn

    def _init_db(self) -> None:
        """Create tables if they don't exist."""
        try:
            conn = self._get_conn()
            try:
                conn.executescript("""
                    CREATE TABLE IF NOT EXISTS board_scraper_log (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        scrape_date TEXT NOT NULL,
                        created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
                        sector_count INTEGER DEFAULT 0,
                        limit_up_count INTEGER DEFAULT 0,
                        ladder_tiers TEXT,
                        errors TEXT,
                        status TEXT DEFAULT 'ok'
                    );

                    CREATE TABLE IF NOT EXISTS board_sector_rankings (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        scrape_date TEXT NOT NULL,
                        sector_name TEXT NOT NULL,
                        change_pct REAL DEFAULT 0,
                        rank_type TEXT NOT NULL DEFAULT 'top',
                        up_count INTEGER DEFAULT 0,
                        limit_up_count INTEGER DEFAULT 0,
                        leader TEXT DEFAULT '',
                        board_code TEXT DEFAULT '',
                        created_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
                    );

                    CREATE TABLE IF NOT EXISTS board_limit_up_pool (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        scrape_date TEXT NOT NULL,
                        code TEXT NOT NULL,
                        name TEXT NOT NULL,
                        price REAL DEFAULT 0,
                        change_pct REAL DEFAULT 0,
                        consecutive_days INTEGER DEFAULT 0,
                        industry TEXT DEFAULT '',
                        created_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
                    );

                    CREATE TABLE IF NOT EXISTS board_sector_stocks (
                        scrape_date TEXT NOT NULL,
                        sector_code TEXT NOT NULL,
                        sector_name TEXT NOT NULL,
                        sector_change_pct REAL DEFAULT 0,
                        limit_up_count INTEGER DEFAULT 0,
                        limit_down_count INTEGER DEFAULT 0,
                        limit_up_stocks TEXT DEFAULT '[]',
                        limit_down_stocks TEXT DEFAULT '[]',
                        created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
                        PRIMARY KEY (scrape_date, sector_code)
                    );

                    CREATE INDEX IF NOT EXISTS idx_sector_rankings_date
                        ON board_sector_rankings(scrape_date);
                    CREATE INDEX IF NOT EXISTS idx_limit_up_date
                        ON board_limit_up_pool(scrape_date);
                    CREATE INDEX IF NOT EXISTS idx_scraper_log_date
                        ON board_scraper_log(scrape_date);
                """)
            finally:
                conn.close()
        except Exception as e:
            logger.error("[BoardScraperStorage] 初始化数据库失败: %s", e)

    def save_scrape_result(self, data: Dict[str, Any]) -> bool:
        """
        Save a full scrape result to both SQLite and CSV.

        Args:
            data: Result from BoardScraperFetcher.scrape_all()

        Returns:
            True if at least sector rankings or limit-up pool was saved
        """
        scrape_date = data.get("date", datetime.now().strftime("%Y-%m-%d"))
        errors = data.get("errors", [])
        status = "error" if errors and not (data.get("sector_rankings") or data.get("limit_up_pool")) else "ok"

        with self._lock:
            try:
                # 1. Save sector rankings
                sector_count = 0
                rankings = data.get("sector_rankings")
                if rankings:
                    top_sectors, bottom_sectors = rankings
                    sector_count = self._save_sector_rankings(scrape_date, top_sectors, bottom_sectors)
                    self._save_csv_sector_rankings(scrape_date, top_sectors, bottom_sectors)

                # 2. Save limit-up pool
                limit_up_count = 0
                pool = data.get("limit_up_pool")
                if pool:
                    limit_up_count = self._save_limit_up_pool(scrape_date, pool)
                    self._save_csv_limit_up_pool(scrape_date, pool)

                # 3. Save board ladder
                ladder_json = None
                ladder = data.get("board_ladder")
                if ladder:
                    import json as _json
                    ladder_json = _json.dumps(
                        {str(k): v for k, v in ladder.items()},
                        ensure_ascii=False,
                    )

                # 4. Save per-sector stocks
                sector_detail = data.get("sector_stocks")
                if sector_detail:
                    self._save_sector_stocks(scrape_date, sector_detail)

                # 5. Log this scrape
                self._save_log(scrape_date, sector_count, limit_up_count, ladder_json, errors, status)

                # 6. Cleanup old data
                self._cleanup_old_data(scrape_date)

                logger.info(
                    "[BoardScraperStorage] 保存完成: date=%s sectors=%d limit_up=%d status=%s",
                    scrape_date, sector_count, limit_up_count, status,
                )
                return True

            except Exception as e:
                logger.error("[BoardScraperStorage] 保存失败: %s", e)
                return False

    def _save_sector_rankings(
        self, date: str, top_sectors: List[Dict], bottom_sectors: List[Dict]
    ) -> int:
        """Save sector rankings to SQLite, return count."""
        conn = self._get_conn()
        try:
            cursor = conn.cursor()
            # Delete existing data for this date first
            cursor.execute("DELETE FROM board_sector_rankings WHERE scrape_date = ?", (date,))

            count = 0
            for sector in top_sectors:
                cursor.execute(
                    """INSERT INTO board_sector_rankings
                       (scrape_date, sector_name, change_pct, rank_type, up_count, limit_up_count, leader)
                       VALUES (?, ?, ?, 'top', ?, ?, ?)""",
                    (date, sector.get("name", ""), sector.get("change_pct", 0),
                     sector.get("up_count", 0), sector.get("limit_up_count", 0),
                     sector.get("leader", "")),
                )
                count += 1

            for sector in bottom_sectors:
                cursor.execute(
                    """INSERT INTO board_sector_rankings
                       (scrape_date, sector_name, change_pct, rank_type, up_count, limit_up_count, leader)
                       VALUES (?, ?, ?, 'bottom', ?, ?, ?)""",
                    (date, sector.get("name", ""), sector.get("change_pct", 0),
                     sector.get("up_count", 0), sector.get("limit_up_count", 0),
                     sector.get("leader", "")),
                )
                count += 1

            conn.commit()
            return count
        finally:
            conn.close()

    def _save_limit_up_pool(self, date: str, pool: List[Dict]) -> int:
        """Save limit-up pool to SQLite, return count."""
        conn = self._get_conn()
        try:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM board_limit_up_pool WHERE scrape_date = ?", (date,))

            count = 0
            for stock in pool:
                cursor.execute(
                    """INSERT INTO board_limit_up_pool
                       (scrape_date, code, name, price, change_pct, consecutive_days, industry)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (date, stock.get("code", ""), stock.get("name", ""),
                     stock.get("price", 0), stock.get("change_pct", 0),
                     stock.get("consecutive_days", 0),
                     stock.get("industry", "")),
                )
                count += 1

            conn.commit()
            return count
        finally:
            conn.close()

    def _save_sector_stocks(self, date: str, sectors: List[Dict]) -> None:
        """Save per-sector limit-up/down stocks."""
        conn = self._get_conn()
        try:
            cursor = conn.cursor()
            import json as _json
            for s in sectors:
                cursor.execute(
                    """INSERT OR REPLACE INTO board_sector_stocks
                       (scrape_date, sector_code, sector_name, sector_change_pct,
                        limit_up_count, limit_down_count, limit_up_stocks, limit_down_stocks)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (date, s.get("sector_code", ""), s.get("sector_name", ""),
                     s.get("sector_change_pct", 0),
                     s.get("limit_up_count", 0), s.get("limit_down_count", 0),
                     _json.dumps(s.get("limit_up_stocks", []), ensure_ascii=False),
                     _json.dumps(s.get("limit_down_stocks", []), ensure_ascii=False)),
                )
            conn.commit()
        finally:
            conn.close()

    def get_sector_stocks_by_date(self, date: str) -> List[Dict[str, Any]]:
        """Query per-sector stocks for a given date."""
        conn = self._get_conn()
        try:
            import json as _json
            cursor = conn.cursor()
            cursor.execute(
                """SELECT sector_code, sector_name, sector_change_pct,
                          limit_up_count, limit_down_count,
                          limit_up_stocks, limit_down_stocks
                   FROM board_sector_stocks
                   WHERE scrape_date = ?
                   ORDER BY sector_change_pct DESC""",
                (date,),
            )
            result = []
            for row in cursor.fetchall():
                d = dict(row)
                d["limit_up_stocks"] = _json.loads(d.get("limit_up_stocks", "[]") or "[]")
                d["limit_down_stocks"] = _json.loads(d.get("limit_down_stocks", "[]") or "[]")
                result.append(d)
            return result
        finally:
            conn.close()

    def _save_log(
        self, date: str, sector_count: int, limit_up_count: int,
        ladder_json: Optional[str], errors: List[str], status: str,
    ) -> None:
        """Save scrape log entry."""
        conn = self._get_conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """INSERT OR REPLACE INTO board_scraper_log
                   (scrape_date, sector_count, limit_up_count, ladder_tiers, errors, status)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (date, sector_count, limit_up_count, ladder_json,
                 "; ".join(errors) if errors else "", status),
            )
            conn.commit()
        finally:
            conn.close()

    # ---------- CSV ----------

    def _save_csv_sector_rankings(
        self, date: str, top_sectors: List[Dict], bottom_sectors: List[Dict]
    ) -> None:
        """Save sector rankings to CSV."""
        if not top_sectors and not bottom_sectors:
            return

        rows = []
        for s in top_sectors:
            s["rank_type"] = "top"
            rows.append(s)
        for s in bottom_sectors:
            s["rank_type"] = "bottom"
            rows.append(s)

        df = pd.DataFrame(rows)
        df.insert(0, "date", date)

        filepath = self._data_dir / f"sector_rankings_{date}.csv"
        df.to_csv(filepath, index=False, encoding="utf-8-sig")
        logger.info("[BoardScraperStorage] CSV 板块排行已保存: %s", filepath)

    def _save_csv_limit_up_pool(self, date: str, pool: List[Dict]) -> None:
        """Save limit-up pool to CSV."""
        if not pool:
            return

        df = pd.DataFrame(pool)
        df.insert(0, "date", date)

        filepath = self._data_dir / f"limit_up_pool_{date}.csv"
        df.to_csv(filepath, index=False, encoding="utf-8-sig")
        logger.info("[BoardScraperStorage] CSV 涨停板池已保存: %s", filepath)

    def _save_csv_board_ladder(self, date: str, ladder: Dict) -> None:
        """Save board ladder to CSV."""
        if not ladder:
            return

        rows = []
        for days, stocks in ladder.items():
            for s in stocks:
                rows.append({
                    "consecutive_days": days,
                    "stock_code": s.get("code", ""),
                    "stock_name": s.get("name", ""),
                    "sector": s.get("sector", ""),
                    "price": s.get("price", 0),
                    "change_pct": s.get("change_pct", 0),
                })

        df = pd.DataFrame(rows)
        df.insert(0, "date", date)

        filepath = self._data_dir / f"board_ladder_{date}.csv"
        df.to_csv(filepath, index=False, encoding="utf-8-sig")
        logger.info("[BoardScraperStorage] CSV 连板梯队已保存: %s", filepath)

    # ---------- 清理 ----------

    def _cleanup_old_data(self, current_date_str: str) -> None:
        """Remove data older than RETENTION_DAYS."""
        try:
            current = datetime.strptime(current_date_str, "%Y-%m-%d")
            cutoff = current - timedelta(days=RETENTION_DAYS)
            cutoff_str = cutoff.strftime("%Y-%m-%d")

            conn = self._get_conn()
            try:
                cursor = conn.cursor()
                for table in ["board_sector_rankings", "board_limit_up_pool", "board_scraper_log"]:
                    cursor.execute(
                        f"DELETE FROM {table} WHERE scrape_date < ?", (cutoff_str,)
                    )
                conn.commit()
            finally:
                conn.close()

            # Clean up old CSV files
            for f in self._data_dir.glob("*.csv"):
                try:
                    fdate_str = f.stem.split("_")[-1] if "_" in f.stem else ""
                    if fdate_str:
                        fdate = datetime.strptime(fdate_str, "%Y-%m-%d")
                        if fdate < cutoff:
                            f.unlink()
                except (ValueError, OSError):
                    pass

        except Exception as e:
            logger.debug("[BoardScraperStorage] 清理旧数据时出错: %s", e)

    # ---------- 查询 ----------

    def get_sector_rankings_by_date(
        self, date: str, rank_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Query sector rankings for a given date."""
        conn = self._get_conn()
        try:
            cursor = conn.cursor()
            if rank_type:
                cursor.execute(
                    """SELECT * FROM board_sector_rankings
                       WHERE scrape_date = ? AND rank_type = ?
                       ORDER BY change_pct DESC""",
                    (date, rank_type),
                )
            else:
                cursor.execute(
                    """SELECT * FROM board_sector_rankings
                       WHERE scrape_date = ?
                       ORDER BY rank_type, change_pct DESC""",
                    (date,),
                )
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    def get_limit_up_pool_by_date(self, date: str) -> List[Dict[str, Any]]:
        """Query limit-up stocks for a given date."""
        conn = self._get_conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """SELECT code, name, price, change_pct, consecutive_days, industry
                   FROM board_limit_up_pool
                   WHERE scrape_date = ?
                   ORDER BY change_pct DESC""",
                (date,),
            )
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    def get_board_ladder_by_date(self, date: str) -> Optional[List[Dict[str, Any]]]:
        """Query board ladder for a given date from the scrape log."""
        conn = self._get_conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT ladder_tiers FROM board_scraper_log WHERE scrape_date = ?",
                (date,),
            )
            row = cursor.fetchone()
            if not row:
                return None
            raw = row["ladder_tiers"]
            if not raw:
                return None
            import json as _json
            data = _json.loads(raw)
            # data: {str(day): [{code, name, price, change_pct}, ...], ...}
            result = []
            for day_str, stocks in data.items():
                result.append({
                    "days": int(day_str),
                    "stocks": stocks,
                })
            result.sort(key=lambda x: x["days"], reverse=True)
            return result
        finally:
            conn.close()

    def get_available_dates(self) -> List[str]:
        """Get dates with saved data."""
        conn = self._get_conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT DISTINCT scrape_date FROM board_scraper_log ORDER BY scrape_date DESC"
            )
            return [row["scrape_date"] for row in cursor.fetchall()]
        finally:
            conn.close()

    def get_latest_scrape(self) -> Optional[Dict[str, Any]]:
        """Get the most recent scrape log entry."""
        conn = self._get_conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM board_scraper_log ORDER BY scrape_date DESC LIMIT 1"
            )
            row = cursor.fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def export_all_to_csv(self, output_dir: Optional[Path] = None) -> int:
        """Export all saved data to CSV files (one per date)."""
        export_dir = Path(output_dir) if output_dir else self._data_dir
        export_dir.mkdir(parents=True, exist_ok=True)
        dates = self.get_available_dates()
        count = 0

        for date in dates:
            sectors = self.get_sector_rankings_by_date(date)
            pool = self.get_limit_up_pool_by_date(date)

            if sectors:
                df = pd.DataFrame(sectors)
                df.to_csv(export_dir / f"sector_rankings_{date}.csv", index=False, encoding="utf-8-sig")
                count += 1

            if pool:
                df = pd.DataFrame(pool)
                df.to_csv(export_dir / f"limit_up_pool_{date}.csv", index=False, encoding="utf-8-sig")
                count += 1

        logger.info("[BoardScraperStorage] 导出完成: %d 个文件到 %s", count, export_dir)
        return count


# Module-level singleton
_storage_instance: Optional[BoardScraperStorage] = None
_storage_lock = threading.Lock()


def get_board_scraper_storage() -> BoardScraperStorage:
    """Get or create the singleton storage instance."""
    global _storage_instance
    if _storage_instance is None:
        with _storage_lock:
            if _storage_instance is None:
                _storage_instance = BoardScraperStorage()
    return _storage_instance
