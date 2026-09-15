#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
从 data/board_scraper/ CSV 文件重建 sector_analysis.db 和 board_scraper.db 的历史数据。

用法：
    python scripts/rebuild_sector_data.py [--dry-run] [--db-dir data]

--dry-run: 仅预览将要导入的数据，不实际写入数据库
--db-dir:  数据库目录（默认 data）
"""

import argparse
import csv
import json
import logging
import os
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# 确保项目根目录在 sys.path 中
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# CSV 解析
# ---------------------------------------------------------------------------


def parse_sector_rankings_csv(filepath: Path) -> List[Dict[str, Any]]:
    """解析 sector_rankings_*.csv 文件"""
    rows = []
    try:
        with open(filepath, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                rows.append({
                    "date": row.get("date", "").strip(),
                    "code": row.get("code", "").strip(),
                    "name": row.get("name", "").strip(),
                    "change_pct": float(row.get("change_pct", 0) or 0),
                    "price": float(row.get("price", 0) or 0),
                    "leader": row.get("leader", "").strip(),
                    "up_count": int(row.get("up_count", 0) or 0),
                    "limit_up_count": int(row.get("limit_up_count", 0) or 0),
                    "rank_type": row.get("rank_type", "top").strip(),
                })
    except Exception as e:
        logger.error(f"解析 CSV 失败 {filepath}: {e}")
    return rows


def parse_limit_up_pool_csv(filepath: Path) -> List[Dict[str, Any]]:
    """解析 limit_up_pool_*.csv 文件"""
    rows = []
    try:
        with open(filepath, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                rows.append({
                    "date": row.get("date", "").strip(),
                    "code": row.get("code", "").strip(),
                    "name": row.get("name", "").strip(),
                    "price": float(row.get("price", 0) or 0),
                    "change_pct": float(row.get("change_pct", 0) or 0),
                    "consecutive_days": int(row.get("consecutive_days", 0) or 0),
                    "industry": row.get("industry", "").strip(),
                })
    except Exception as e:
        logger.error(f"解析 CSV 失败 {filepath}: {e}")
    return rows


def parse_board_ladder_csv(filepath: Path) -> List[Dict[str, Any]]:
    """解析 board_ladder_*.csv 文件"""
    rows = []
    try:
        with open(filepath, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                rows.append({
                    "date": row.get("date", "").strip(),
                    "consecutive_days": int(row.get("consecutive_days", 1) or 1),
                    "stock_code": row.get("stock_code", "").strip(),
                    "stock_name": row.get("stock_name", "").strip(),
                    "sector": row.get("sector", "").strip(),
                    "price": float(row.get("price", 0) or 0),
                    "change_pct": float(row.get("change_pct", 0) or 0),
                })
    except Exception as e:
        logger.error(f"解析 CSV 失败 {filepath}: {e}")
    return rows


def scan_csv_files(csv_dir: Path) -> Dict[str, Dict[str, Any]]:
    """扫描 CSV 目录，按日期组织所有数据"""
    dates_data: Dict[str, Dict[str, Any]] = {}

    # sector_rankings
    for f in sorted(csv_dir.glob("sector_rankings_*.csv")):
        date_str = f.stem.replace("sector_rankings_", "")
        rows = parse_sector_rankings_csv(f)
        if not rows:
            continue
        if date_str not in dates_data:
            dates_data[date_str] = {}
        dates_data[date_str]["sector_rankings"] = rows
        logger.info(f"  日期 {date_str}: 读取到 {len(rows)} 条板块排名")

    # limit_up_pool
    for f in sorted(csv_dir.glob("limit_up_pool_*.csv")):
        date_str = f.stem.replace("limit_up_pool_", "")
        rows = parse_limit_up_pool_csv(f)
        if not rows:
            continue
        if date_str not in dates_data:
            dates_data[date_str] = {}
        dates_data[date_str]["limit_up_pool"] = rows
        logger.info(f"  日期 {date_str}: 读取到 {len(rows)} 条涨停池数据")

    # board_ladder
    for f in sorted(csv_dir.glob("board_ladder_*.csv")):
        date_str = f.stem.replace("board_ladder_", "")
        rows = parse_board_ladder_csv(f)
        if not rows:
            continue
        if date_str not in dates_data:
            dates_data[date_str] = {}
        dates_data[date_str]["board_ladder"] = rows
        logger.info(f"  日期 {date_str}: 读取到 {len(rows)} 条连板梯队数据")

    return dates_data


# ---------------------------------------------------------------------------
# 数据库操作
# ---------------------------------------------------------------------------


def rebuild_board_scraper_db(
    dates_data: Dict[str, Dict[str, Any]],
    db_path: str,
) -> int:
    """将 CSV 数据导入 board_scraper.db（直接写 SQLite，不依赖 pandas）"""
    conn = sqlite3.connect(db_path, timeout=10.0)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
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
        CREATE INDEX IF NOT EXISTS idx_sector_rankings_date ON board_sector_rankings(scrape_date);
        CREATE INDEX IF NOT EXISTS idx_limit_up_date ON board_limit_up_pool(scrape_date);
        CREATE INDEX IF NOT EXISTS idx_scraper_log_date ON board_scraper_log(scrape_date);
    """)
    conn.commit()

    count = 0
    for date_str in sorted(dates_data.keys()):
        data = dates_data[date_str]
        sector_rankings = data.get("sector_rankings", [])
        limit_up_pool = data.get("limit_up_pool", [])
        board_ladder = data.get("board_ladder", [])

        if not sector_rankings and not limit_up_pool:
            logger.warning(f"  跳过 {date_str}: 无有效数据")
            continue

        top_sectors = [r for r in sector_rankings if r.get("rank_type") == "top"]
        bottom_sectors = [r for r in sector_rankings if r.get("rank_type") == "bottom"]

        conn.execute("DELETE FROM board_sector_rankings WHERE scrape_date = ?", (date_str,))
        sector_count = 0
        for s in top_sectors:
            conn.execute(
                """INSERT INTO board_sector_rankings
                   (scrape_date, sector_name, change_pct, rank_type, up_count, limit_up_count, leader)
                   VALUES (?, ?, ?, 'top', ?, ?, ?)""",
                (date_str, s.get("name", ""), s.get("change_pct", 0),
                 s.get("up_count", 0), s.get("limit_up_count", 0), s.get("leader", "")),
            )
            sector_count += 1
        for s in bottom_sectors:
            conn.execute(
                """INSERT INTO board_sector_rankings
                   (scrape_date, sector_name, change_pct, rank_type, up_count, limit_up_count, leader)
                   VALUES (?, ?, ?, 'bottom', ?, ?, ?)""",
                (date_str, s.get("name", ""), s.get("change_pct", 0),
                 s.get("up_count", 0), s.get("limit_up_count", 0), s.get("leader", "")),
            )
            sector_count += 1

        conn.execute("DELETE FROM board_limit_up_pool WHERE scrape_date = ?", (date_str,))
        for s in limit_up_pool:
            conn.execute(
                """INSERT INTO board_limit_up_pool
                   (scrape_date, code, name, price, change_pct, consecutive_days, industry)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (date_str, s.get("code", ""), s.get("name", ""),
                 s.get("price", 0), s.get("change_pct", 0),
                 s.get("consecutive_days", 0), s.get("industry", "")),
            )

        ladder_json = None
        if board_ladder:
            ladder_dict = {}
            for r in board_ladder:
                days = r.get("consecutive_days", 1)
                if days not in ladder_dict:
                    ladder_dict[days] = []
                ladder_dict[days].append({
                    "code": r.get("stock_code", ""),
                    "name": r.get("stock_name", ""),
                    "price": r.get("price", 0),
                    "change_pct": r.get("change_pct", 0),
                })
            ladder_json = json.dumps({str(k): v for k, v in ladder_dict.items()}, ensure_ascii=False)

        conn.execute("DELETE FROM board_scraper_log WHERE scrape_date = ?", (date_str,))
        conn.execute(
            """INSERT INTO board_scraper_log
               (scrape_date, sector_count, limit_up_count, ladder_tiers, errors, status)
               VALUES (?, ?, ?, ?, ?, 'ok')""",
            (date_str, sector_count, len(limit_up_pool), ladder_json, ""),
        )
        conn.commit()
        count += 1
        logger.info(f"  ✓ {date_str}: 已导入 board_scraper.db (板块={sector_count}, 涨停={len(limit_up_pool)})")

    conn.close()
    return count


def rebuild_sector_analysis_db(
    dates_data: Dict[str, Dict[str, Any]],
    db_path: str,
) -> int:
    """从 CSV 数据重建 sector_analysis.db（供 SectorAnalysisStorage 使用）

    由于 CSV 只有板块排名和涨停池的原始数据，
    我们无法重建龙头带动效应和筹码质量评分（需要实时股价数据），
    但可以重建基础板块分析数据，足够支持板块轮动追踪。

    Returns: 导入的日期数
    """
    conn = sqlite3.connect(db_path, timeout=10.0)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS sector_analysis (
            analysis_date TEXT PRIMARY KEY,
            data          TEXT NOT NULL,
            sector_count  INTEGER DEFAULT 0,
            created_at    TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_analysis_date
        ON sector_analysis(analysis_date DESC)
    """)
    conn.commit()

    count = 0

    for date_str in sorted(dates_data.keys()):
        data = dates_data[date_str]
        sector_rankings = data.get("sector_rankings", [])
        limit_up_pool = data.get("limit_up_pool", [])

        top_sectors = [r for r in sector_rankings if r.get("rank_type") == "top"]
        bottom_sectors = [r for r in sector_rankings if r.get("rank_type") == "bottom"]

        if not top_sectors and not bottom_sectors:
            logger.warning(f"  跳过 {date_str}: 无板块排名数据")
            continue

        # 构造与 SectorAnalyzer 输出相同格式的 sectors 列表
        sectors = []
        for r in top_sectors:
            sector_name = r.get("name", "")
            change_pct = r.get("change_pct", 0)
            up_count = r.get("up_count", 0)
            limit_up_count = r.get("limit_up_count", 0)
            leader_name = r.get("leader", "")

            # 从涨停池中找到该板块的涨停股
            sector_limit_ups = [
                s for s in limit_up_pool
                if s.get("industry", "").strip() == sector_name or
                   (leader_name and s.get("name", "") == leader_name)
            ][:10]  # 限制数量

            # 构造 limit_up_stocks
            limit_up_stocks = []
            for s in sector_limit_ups:
                limit_up_stocks.append({
                    "code": s.get("code", ""),
                    "name": s.get("name", ""),
                    "change_pct": s.get("change_pct", 0),
                    "price": s.get("price", 0),
                    "is_limit_up": True,
                    "consecutive_limit_up_days": s.get("consecutive_days", 0),
                })

            # 用涨停池数据构造简单 ladder
            ladder = []
            seen_codes = set()
            for s in sorted(sector_limit_ups, key=lambda x: x.get("consecutive_days", 0), reverse=True):
                code = s.get("code", "")
                days = s.get("consecutive_days", 0)
                if code not in seen_codes and days > 0:
                    ladder.append({
                        "days": days,
                        "stock_code": code,
                        "stock_name": s.get("name", ""),
                    })
                    seen_codes.add(code)

            # 构造 leader 信息
            leader = None
            if leader_name:
                leader_stock = next(
                    (s for s in limit_up_stocks if s.get("name") == leader_name), None
                )
                if leader_stock:
                    leader = {
                        "code": leader_stock["code"],
                        "name": leader_stock["name"],
                        "change_pct": leader_stock.get("change_pct", 0),
                        "price": leader_stock.get("price", 0),
                        "is_limit_up": True,
                        "consecutive_limit_up_days": leader_stock.get("consecutive_limit_up_days", 0),
                    }

            # 估算分数（简化版，与 SectorAnalyzer._calc_score 一致）
            score = max(0, change_pct) * 2.0 + limit_up_count * 5.0
            # ladder_completeness 用 ladder 去重天数
            ladder_days = len({r["days"] for r in ladder}) if ladder else 0
            score += ladder_days * 8.0
            # leader_correlation 无法从 CSV 重建，设为 0
            score += 0 * 15.0  # leader_correlation * 15
            score = round(score, 2)

            sector_item = {
                "name": sector_name,
                "change_pct": change_pct,
                "limit_up_count": limit_up_count,
                "limit_up_stocks": limit_up_stocks,
                "ladder": ladder,
                "leader": leader,
                "leader_correlation": 0.0,  # 无法从 CSV 重建
                "score": score,
                "catalyst": "",  # 无法从 CSV 重建
                "effect_summary": "",  # 无法从 CSV 重建
                "related_stocks": [],  # 无法从 CSV 重建
            }
            sectors.append(sector_item)

        # 按 score 降序排列
        sectors.sort(key=lambda s: s.get("score", 0), reverse=True)

        # 构建完整的分析结果
        result = {
            "date": date_str,
            "sectors": sectors,
            "total": len(sectors),
            "cache_status": "reconstructed_from_csv",
            "hotspot_summary": {
                "limit_up_count": len(limit_up_pool),
                "reconstructed": True,
            },
            "analyzed_at": datetime.now().isoformat(),
        }

        # 写入数据库
        try:
            conn.execute(
                """
                INSERT OR REPLACE INTO sector_analysis
                (analysis_date, data, sector_count, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (
                    date_str,
                    json.dumps(result, ensure_ascii=False),
                    len(sectors),
                    datetime.now().isoformat(),
                ),
            )
            conn.commit()
            count += 1
            logger.info(
                f"  ✓ {date_str}: 已重建 sector_analysis.db "
                f"({len(sectors)} 个板块, {len(limit_up_pool)} 只涨停股)"
            )
        except Exception as e:
            logger.error(f"  ✗ {date_str}: 写入失败: {e}")

    conn.close()
    return count


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(
        description="从 CSV 文件重建 sector_analysis.db 和 board_scraper.db"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="仅预览，不实际写入数据库",
    )
    parser.add_argument(
        "--db-dir",
        default=str(PROJECT_ROOT / "data"),
        help="数据库目录（默认 data/）",
    )
    parser.add_argument(
        "--csv-dir",
        default=str(PROJECT_ROOT / "data" / "board_scraper"),
        help="CSV 文件目录（默认 data/board_scraper/）",
    )
    parser.add_argument(
        "--skip-board-scraper",
        action="store_true",
        help="跳过 board_scraper.db 重建（只重建 sector_analysis.db）",
    )
    parser.add_argument(
        "--skip-sector-analysis",
        action="store_true",
        help="跳过 sector_analysis.db 重建（只重建 board_scraper.db）",
    )
    args = parser.parse_args()

    csv_dir = Path(args.csv_dir)
    db_dir = Path(args.db_dir)

    if not csv_dir.exists():
        logger.error(f"CSV 目录不存在: {csv_dir}")
        sys.exit(1)

    logger.info("=" * 60)
    logger.info("从 CSV 文件重建数据库")
    logger.info(f"CSV 目录: {csv_dir}")
    logger.info(f"数据库目录: {db_dir}")
    logger.info(f"干跑模式: {'是' if args.dry_run else '否'}")
    logger.info("=" * 60)

    # 1. 扫描 CSV 文件
    logger.info("\n📂 扫描 CSV 文件...")
    dates_data = scan_csv_files(csv_dir)

    if not dates_data:
        logger.error("未找到任何 CSV 数据文件")
        sys.exit(1)

    logger.info(f"\n找到 {len(dates_data)} 个日期的数据:")
    for date_str in sorted(dates_data.keys()):
        data = dates_data[date_str]
        sr_count = len(data.get("sector_rankings", []))
        lu_count = len(data.get("limit_up_pool", []))
        bl_count = len(data.get("board_ladder", []))
        logger.info(f"  {date_str}: 板块排名={sr_count}, 涨停池={lu_count}, 连板梯队={bl_count}")

    if args.dry_run:
        logger.info("\n🔍 [干跑模式] 不写入数据库。以上为预览数据。")
        return

    # 2. 重建 board_scraper.db
    if not args.skip_board_scraper:
        logger.info("\n📊 重建 board_scraper.db...")
        board_db_path = str(db_dir / "board_scraper.db")
        count = rebuild_board_scraper_db(dates_data, board_db_path)
        logger.info(f"  board_scraper.db: 导入 {count} 个日期")

    # 3. 重建 sector_analysis.db
    if not args.skip_sector_analysis:
        logger.info("\n📊 重建 sector_analysis.db...")
        sector_db_path = str(db_dir / "sector_analysis.db")

        # 备份现有数据库
        if Path(sector_db_path).exists():
            backup_path = sector_db_path + ".bak"
            import shutil
            shutil.copy2(sector_db_path, backup_path)
            logger.info(f"  已备份现有数据库到: {backup_path}")

        count = rebuild_sector_analysis_db(dates_data, sector_db_path)
        logger.info(f"  sector_analysis.db: 重建 {count} 个日期")

    # 4. 验证结果
    logger.info("\n✅ 重建完成，验证结果:")

    if not args.skip_sector_analysis:
        sector_db_path = str(db_dir / "sector_analysis.db")
        conn = sqlite3.connect(sector_db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM sector_analysis")
        total = cursor.fetchone()[0]
        cursor.execute("SELECT analysis_date, sector_count FROM sector_analysis ORDER BY analysis_date")
        rows = cursor.fetchall()
        logger.info(f"  sector_analysis.db: {total} 条记录")
        for row in rows:
            logger.info(f"    {row[0]}: {row[1]} 个板块")
        conn.close()

    if not args.skip_board_scraper:
        board_db_path = str(db_dir / "board_scraper.db")
        conn = sqlite3.connect(board_db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(DISTINCT scrape_date) FROM board_scraper_log")
        total_dates = cursor.fetchone()[0]
        cursor.execute("SELECT scrape_date, sector_count, limit_up_count FROM board_scraper_log ORDER BY scrape_date")
        rows = cursor.fetchall()
        logger.info(f"  board_scraper.db: {total_dates} 个日期")
        for row in rows:
            logger.info(f"    {row[0]}: 板块={row[1]}, 涨停={row[2]}")
        conn.close()

    logger.info("\n🎉 重建完成！")
    logger.info("⚠️  注意: leader_correlation 和 chip_quality 字段为 0（需实时数据计算），板块轮动追踪可正常使用。")


if __name__ == "__main__":
    main()