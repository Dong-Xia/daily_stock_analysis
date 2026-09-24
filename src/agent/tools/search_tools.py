# -*- coding: utf-8 -*-
"""
Search tools — wraps SearchService methods as agent-callable tools.

Tools:
- search_stock_news: search latest stock news
- search_comprehensive_intel: multi-dimensional intelligence search
"""

import logging
from typing import Optional

from src.agent.tools.registry import ToolParameter, ToolDefinition

logger = logging.getLogger(__name__)


def _get_search_service():
    """Return shared SearchService singleton."""
    from src.search_service import get_search_service
    return get_search_service()


def _handle_search_stock_news(stock_code: str, stock_name: str) -> dict:
    """Search latest news for a stock; falls back to free Eastmoney news on engine failure."""
    service = _get_search_service()

    engine_error = None
    if not service.is_available:
        engine_error = "No search engine available (no API keys configured)"
    else:
        response = service.search_stock_news(stock_code, stock_name, max_results=5)
        if response.success:
            return {
                "query": response.query,
                "provider": response.provider,
                "success": True,
                "results_count": len(response.results),
                "results": [
                    {
                        "title": r.title,
                        "snippet": r.snippet,
                        "url": r.url,
                        "source": r.source,
                        "published_date": r.published_date,
                    }
                    for r in response.results
                ],
            }
        engine_error = response.error_message or "search engine failed"

    # 免费源降级(仅引擎不可用/失败时;东财个股新闻,仅 A 股,国内直连)
    from data_provider.base import normalize_stock_code, _market_tag

    code = normalize_stock_code(stock_code or "")
    if not code or _market_tag(code) != "cn":
        return {
            "query": f"{stock_code} {stock_name}".strip(),
            "success": False,
            "error": f"{engine_error}; free fallback only supports A-shares",
            "retriable": False,
        }

    from data_provider.free_news_adapter import get_free_news_adapter

    free = get_free_news_adapter().get_stock_news(code)
    if free.get("status") == "ok" and free.get("items"):
        return {
            "query": f"{stock_code} {stock_name}".strip(),
            "provider": "eastmoney_free",
            "fallback": True,
            "note": "搜索引擎不可用,已降级为东方财富免费个股新闻(覆盖面低于全网搜索,结论措辞请留余地)",
            "success": True,
            "results_count": len(free["items"]),
            "results": free["items"],
        }
    fallback_error = (
        "; ".join(free.get("errors", [])) or "free source returned no items"
    )
    return {
        "query": f"{stock_code} {stock_name}".strip(),
        "success": False,
        "error": engine_error,
        "fallback_error": fallback_error,
    }


search_stock_news_tool = ToolDefinition(
    name="search_stock_news",
    description="Search for the latest news articles about a specific stock. "
                "Requires both stock_code and stock_name for accurate search. "
                "Returns news titles, snippets, sources, and URLs.",
    parameters=[
        ToolParameter(
            name="stock_code",
            type="string",
            description="Stock code, e.g., '600519'",
        ),
        ToolParameter(
            name="stock_name",
            type="string",
            description="Stock name in Chinese, e.g., '贵州茅台'",
        ),
    ],
    handler=_handle_search_stock_news,
    category="search",
)


# ============================================================
# search_comprehensive_intel
# ============================================================

def _handle_search_comprehensive_intel(stock_code: str, stock_name: str) -> dict:
    """Multi-dimensional intelligence search."""
    service = _get_search_service()

    if not service.is_available:
        return {"error": "No search engine available (no API keys configured)"}

    intel_results = service.search_comprehensive_intel(
        stock_code=stock_code,
        stock_name=stock_name,
        max_searches=6,
    )

    if not intel_results:
        return {"error": "Comprehensive intel search returned no results"}

    # Format into readable report
    report = service.format_intel_report(intel_results, stock_name)

    # Also return structured data
    dimensions = {}
    for dim_name, response in intel_results.items():
        if response and response.success:
            dimensions[dim_name] = {
                "query": response.query,
                "results_count": len(response.results),
                "results": [
                    {
                        "title": r.title,
                        "snippet": r.snippet,
                        "source": r.source,
                    }
                    for r in response.results[:3]  # limit to 3 per dimension to save tokens
                ],
            }

    return {
        "report": report,
        "dimensions": dimensions,
    }


search_comprehensive_intel_tool = ToolDefinition(
    name="search_comprehensive_intel",
    description="Multi-dimensional intelligence search: latest news, market analysis, "
                "risk checking, earnings outlook, and industry trends for a stock. "
                "Returns a formatted report and structured results.",
    parameters=[
        ToolParameter(
            name="stock_code",
            type="string",
            description="Stock code, e.g., '600519'",
        ),
        ToolParameter(
            name="stock_name",
            type="string",
            description="Stock name in Chinese, e.g., '贵州茅台'",
        ),
    ],
    handler=_handle_search_comprehensive_intel,
    category="search",
)


# ============================================================
# get_stock_announcements (B2-lite 免费法定公告源)
# ============================================================

def _handle_get_stock_announcements(stock_code: str, days: int = 90, keyword: str = "") -> dict:
    """Fetch statutory announcements for an A-share stock (primary-source data)."""
    from data_provider.base import normalize_stock_code, _market_tag

    code = normalize_stock_code(stock_code or "")
    if not code or _market_tag(code) != "cn":
        return {"success": False, "error": "announcements only support A-shares", "retriable": False}

    from data_provider.free_news_adapter import get_free_news_adapter

    payload = get_free_news_adapter().get_stock_announcements(
        code, days=days, keyword=(keyword or "").strip() or None
    )
    if payload.get("status") != "ok":
        return {
            "success": False,
            "error": "; ".join(payload.get("errors", [])) or "announcement fetch failed",
        }
    items = payload.get("items", [])
    truncated = len(items) > 100
    return {
        "success": True,
        "stock_code": code,
        "days": days,
        "keyword": (keyword or "").strip() or None,
        "count": min(len(items), 100),
        "truncated": truncated,
        "announcements": items[:100],
        "note": "法定公告一手信源(东方财富公告大全);适用于减持/质押/回购/问询函/举牌等监管痕迹核验",
    }


get_stock_announcements_tool = ToolDefinition(
    name="get_stock_announcements",
    description="Fetch statutory announcements (法定公告) for an A-share stock: 减持/质押/回购/问询函/举牌/"
                "定期报告 etc. Primary-source data from Eastmoney notice center. "
                "Use for regulatory-trace verification (监管痕迹核验).",
    parameters=[
        ToolParameter(
            name="stock_code",
            type="string",
            description="A-share stock code, e.g., '600519'",
        ),
        ToolParameter(
            name="days",
            type="integer",
            description="Lookback window in days, default 90",
        ),
        ToolParameter(
            name="keyword",
            type="string",
            description="Optional keyword filter on announcement title (e.g., '减持')",
        ),
    ],
    handler=_handle_get_stock_announcements,
    category="search",
)


ALL_SEARCH_TOOLS = [
    search_stock_news_tool,
    search_comprehensive_intel_tool,
    get_stock_announcements_tool,
]
