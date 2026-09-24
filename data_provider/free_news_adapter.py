# -*- coding: utf-8 -*-
"""
免费新闻/公告源(akshare,国内直连,无 API key,fail-open)。

- get_stock_news: ak.stock_news_em — 东方财富个股新闻
- get_stock_announcements: ak.stock_individual_notice_report — 东方财富公告大全(个股,法定信源)

所有异常吞入 errors,不向调用方抛出。
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def _find_col(df: Any, keys, exclude=()):
    """列名关键词定位(先全等再子串,可排除),应对 akshare 列名漂移。"""
    for col in df.columns:
        if str(col) in keys:
            return col
    for col in df.columns:
        col_str = str(col)
        if any(k in col_str for k in keys) and not any(e in col_str for e in exclude):
            return col
    return None


def _safe_str(value) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _safe_date_str(value) -> Optional[str]:
    """日期列可能是 date/datetime/str,统一为 YYYY-MM-DD;解析失败返回 None。"""
    try:
        import pandas as pd

        if pd.isna(value):
            return None
        return pd.to_datetime(value).strftime("%Y-%m-%d")
    except Exception:
        return None


class FreeNewsAdapter:
    """akshare 免费新闻/公告源(无状态,fail-open)。"""

    def get_stock_news(self, stock_code: str, max_items: int = 10) -> Dict[str, Any]:
        result: Dict[str, Any] = {"status": "failed", "items": [], "errors": []}
        try:
            import akshare as ak

            df = ak.stock_news_em(symbol=stock_code)
        except Exception as exc:
            result["errors"].append(f"stock_news_em:{type(exc).__name__}")
            return result
        if df is None or df.empty:
            result["status"] = "ok"
            return result
        title_col = _find_col(df, ["新闻标题", "标题"])
        content_col = _find_col(df, ["新闻内容", "内容"])
        time_col = _find_col(df, ["发布时间", "时间"])
        source_col = _find_col(df, ["文章来源", "来源"])
        link_col = _find_col(df, ["新闻链接", "链接"])
        if title_col is None:
            result["errors"].append("stock_news_em:missing_title_column")
            return result
        items: List[Dict[str, Any]] = []
        for _, row in df.head(max(int(max_items), 1)).iterrows():
            snippet = _safe_str(row[content_col]) if content_col else None
            items.append({
                "title": _safe_str(row[title_col]),
                "snippet": snippet[:200] if snippet else None,
                "url": _safe_str(row[link_col]) if link_col else None,
                "source": _safe_str(row[source_col]) if source_col else None,
                "published_date": _safe_date_str(row[time_col]) if time_col else None,
            })
        result["status"] = "ok"
        result["items"] = items
        return result

    def get_stock_announcements(
        self,
        stock_code: str,
        days: int = 90,
        keyword: Optional[str] = None,
    ) -> Dict[str, Any]:
        result: Dict[str, Any] = {"status": "failed", "items": [], "errors": []}
        end = date.today()
        begin = end - timedelta(days=max(1, int(days)))

        def _call(with_dates: bool):
            import akshare as ak

            if with_dates:
                return ak.stock_individual_notice_report(
                    security=stock_code,
                    symbol="全部",
                    begin_date=begin.strftime("%Y%m%d"),
                    end_date=end.strftime("%Y%m%d"),
                )
            return ak.stock_individual_notice_report(security=stock_code, symbol="全部")

        df = None
        try:
            df = _call(with_dates=True)
        except Exception as exc:
            result["errors"].append(f"stock_individual_notice_report:{type(exc).__name__}")
            logger.debug("公告接口带日期调用失败,尝试无日期重试: %s", exc)
            try:
                df = _call(with_dates=False)
            except Exception as exc2:
                result["errors"].append(f"stock_individual_notice_report_retry:{type(exc2).__name__}")
                return result
        if df is None or df.empty:
            result["status"] = "ok"
            return result
        title_col = _find_col(df, ["公告标题", "标题"])
        type_col = _find_col(df, ["公告类型", "类型"])
        date_col = _find_col(df, ["公告日期", "日期"])
        url_col = _find_col(df, ["网址", "链接"])
        if title_col is None or date_col is None:
            result["errors"].append("stock_individual_notice_report:missing_columns")
            return result
        kw = (keyword or "").strip().lower()
        window_begin = begin.isoformat()
        items: List[Dict[str, Any]] = []
        for _, row in df.iterrows():
            title = _safe_str(row[title_col])
            if not title:
                continue
            if kw and kw not in title.lower():
                continue
            date_str = _safe_date_str(row[date_col])
            if date_str and date_str < window_begin:
                continue
            items.append({
                "date": date_str,
                "notice_type": _safe_str(row[type_col]) if type_col else None,
                "title": title,
                "url": _safe_str(row[url_col]) if url_col else None,
            })
        items.sort(key=lambda r: r.get("date") or "", reverse=True)
        result["status"] = "ok"
        result["items"] = items
        return result


FREE_NEWS_ADAPTER = FreeNewsAdapter()


def get_free_news_adapter() -> FreeNewsAdapter:
    """共享单例。"""
    return FREE_NEWS_ADAPTER
