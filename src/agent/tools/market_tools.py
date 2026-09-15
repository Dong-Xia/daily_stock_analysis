# -*- coding: utf-8 -*-
"""
Market tools — wraps DataFetcherManager market-level methods as agent tools.

Tools:
- get_market_indices: major market index data
- get_sector_rankings: sector performance rankings
- get_market_overview: market breadth stats (up/down counts, limit up/down, total amount)
"""

import logging

from src.agent.tools.registry import ToolParameter, ToolDefinition

logger = logging.getLogger(__name__)


def _get_fetcher_manager():
    """Lazy import to avoid circular deps."""
    from data_provider import DataFetcherManager
    return DataFetcherManager()


# ============================================================
# get_market_indices
# ============================================================

def _handle_get_market_indices(region: str = "cn") -> dict:
    """Get major market indices."""
    manager = _get_fetcher_manager()
    indices = manager.get_main_indices(region=region)

    if not indices:
        return {"error": f"No market index data available for region '{region}'"}

    return {
        "region": region,
        "indices_count": len(indices),
        "indices": indices,
    }


get_market_indices_tool = ToolDefinition(
    name="get_market_indices",
    description="Get major market indices (e.g., Shanghai Composite, Shenzhen Component, "
                "CSI 300 for China; S&P 500, Nasdaq, Dow for US). Provides market overview.",
    parameters=[
        ToolParameter(
            name="region",
            type="string",
            description="Market region: 'cn' for China A-shares, 'us' for US stocks (default: 'cn')",
            required=False,
            default="cn",
            enum=["cn", "us"],
        ),
    ],
    handler=_handle_get_market_indices,
    category="market",
)


# ============================================================
# get_sector_rankings
# ============================================================

def _handle_get_sector_rankings(top_n: int = 10) -> dict:
    """Get sector performance rankings."""
    manager = _get_fetcher_manager()
    result = manager.get_sector_rankings(n=top_n)

    if result is None:
        return {"error": "No sector ranking data available"}

    # get_sector_rankings returns Tuple[List[Dict], List[Dict]]
    # (top_sectors, bottom_sectors)
    if isinstance(result, tuple) and len(result) == 2:
        top_sectors, bottom_sectors = result
        return {
            "top_sectors": top_sectors,
            "bottom_sectors": bottom_sectors,
        }
    elif isinstance(result, list):
        return {"sectors": result}
    else:
        return {"data": str(result)}


get_sector_rankings_tool = ToolDefinition(
    name="get_sector_rankings",
    description="Get sector/industry performance rankings. Returns top N and bottom N "
                "sectors by daily change percentage. Useful for sector rotation analysis.",
    parameters=[
        ToolParameter(
            name="top_n",
            type="integer",
            description="Number of top/bottom sectors to return (default: 10)",
            required=False,
            default=10,
        ),
    ],
    handler=_handle_get_sector_rankings,
    category="market",
)


# ============================================================
# get_market_overview
# ============================================================

def _handle_get_market_overview() -> dict:
    """Get market breadth overview — rising/falling stock counts, limit-up/down, total turnover.

    Returns A-share market-wide statistics including:
    - up_count: number of rising stocks
    - down_count: number of falling stocks
    - flat_count: number of flat/unchanged stocks
    - limit_up_count: number of stocks hitting daily upper limit
    - limit_down_count: number of stocks hitting daily lower limit
    - total_amount: total market turnover (in CNY)
    """
    manager = _get_fetcher_manager()
    stats = manager.get_market_stats()

    if not stats:
        return {"error": "No market overview data available"}

    return {
        "up_count": stats.get("up_count", 0),
        "down_count": stats.get("down_count", 0),
        "flat_count": stats.get("flat_count", 0),
        "limit_up_count": stats.get("limit_up_count", 0),
        "limit_down_count": stats.get("limit_down_count", 0),
        "total_amount": stats.get("total_amount", 0),
    }


get_market_overview_tool = ToolDefinition(
    name="get_market_overview",
    description="Get A-share market breadth overview: number of rising/falling stocks, "
                "limit-up/limit-down counts, and total market turnover. "
                "Use this to assess overall market sentiment and decide position sizing. "
                "Key thresholds: 3000+ rising = healthy market; < 3000 rising = caution.",
    parameters=[],
    handler=_handle_get_market_overview,
    category="market",
)


ALL_MARKET_TOOLS = [
    get_market_indices_tool,
    get_sector_rankings_tool,
    get_market_overview_tool,
]
