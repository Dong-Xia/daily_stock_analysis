# -*- coding: utf-8 -*-
"""
大盘复盘报告 API 端点
"""

import logging
import re
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, HTTPException

logger = logging.getLogger(__name__)

router = APIRouter()

REPORTS_DIR = Path(__file__).resolve().parent.parent.parent.parent / "reports"

REVIEW_FILENAME_PATTERN = re.compile(r"^market_review_(\d{8})\.md$")


def _list_report_files() -> List[dict]:
    """List all market review report files, sorted by date descending."""
    if not REPORTS_DIR.exists():
        return []
    entries = []
    for f in sorted(REPORTS_DIR.iterdir(), key=lambda p: p.name, reverse=True):
        m = REVIEW_FILENAME_PATTERN.match(f.name)
        if m:
            date_str = m.group(1)
            try:
                formatted = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]}"
            except Exception:
                formatted = date_str
            entries.append({"date": date_str, "date_formatted": formatted, "filename": f.name})
    return entries


def _read_report(filename: str) -> Optional[str]:
    """Read a report file, return None if not found."""
    filepath = REPORTS_DIR / filename
    if not filepath.exists() or not filepath.is_file():
        return None
    try:
        return filepath.read_text(encoding="utf-8")
    except Exception as e:
        logger.error("读取复盘报告失败 %s: %s", filename, e)
        return None


@router.post("/generate")
def trigger_market_review() -> dict:
    """触发大盘复盘分析并生成报告。"""
    try:
        from analyzer_service import perform_market_review
        report = perform_market_review()
        if report:
            # 重新读取报告文件获取最新列表
            files = _list_report_files()
            return {"success": True, "report": report, "reports": files}
        raise HTTPException(status_code=500, detail="复盘生成失败")
    except Exception as e:
        logger.error("触发大盘复盘失败: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"复盘生成异常: {e}")


@router.get("/list")
def list_reports() -> dict:
    """列出所有可用的复盘报告。"""
    return {"reports": _list_report_files(), "total": len(_list_report_files())}


@router.get("/latest")
def get_latest_report() -> dict:
    """获取最新一份复盘报告。"""
    files = _list_report_files()
    if not files:
        raise HTTPException(status_code=404, detail="暂无复盘报告")
    content = _read_report(files[0]["filename"])
    if content is None:
        raise HTTPException(status_code=404, detail="报告文件读取失败")
    return {"report": {"meta": files[0], "content": content}}


@router.get("/{date}")
def get_report_by_date(date: str) -> dict:
    """按日期获取复盘报告。"""
    # validate date format
    if not re.match(r"^\d{8}$", date):
        raise HTTPException(status_code=400, detail="日期格式错误，应为 YYYYMMDD")
    filename = f"market_review_{date}.md"
    content = _read_report(filename)
    if content is None:
        raise HTTPException(status_code=404, detail=f"未找到 {date} 的复盘报告")
    return {
        "report": {
            "meta": {
                "date": date,
                "date_formatted": f"{date[:4]}-{date[4:6]}-{date[6:]}",
                "filename": filename,
            },
            "content": content,
        }
    }
