# -*- coding: utf-8 -*-
"""
热点板块分析接口
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query

from api.v1.schemas.common import ErrorResponse
from api.v1.schemas.sectors import (
    HotSectorsResponse,
    HotSectorItem,
    ManualSectorInput,
    ManualSectorParseResponse,
    ScraperBoardDataResponse,
    ScraperLadderTierItem,
    ScraperLadderStockItem,
    ScraperSectorRankingItem,
    ScraperLimitUpItem,
    ScraperSectorDetailItem,
    ScraperSectorStockItem,
    SectorRankingsResponse,
    SectorRankingItem,
)
from src.core.sector_analyzer import SectorAnalyzer, HotSector

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get(
    "/hot",
    response_model=HotSectorsResponse,
    responses={
        200: {"description": "热点板块列表"},
        500: {"description": "服务器错误", "model": ErrorResponse},
    },
    summary="获取热点板块分析",
    description="获取热点板块分析。优先返回预计算数据，无预计算时实时分析。",
)
def get_hot_sectors(
    market: str = Query("cn", description="市场：cn/hk/us", pattern="^(cn|hk|us)$"),
    limit: int = Query(20, ge=1, le=50, description="返回板块数量上限"),
    min_limit_up: int = Query(1, ge=0, le=20, description="最小涨停家数门槛"),
    date: Optional[str] = Query(None, description="分析日期（YYYY-MM-DD），默认最近预计算日"),
) -> HotSectorsResponse:
    if market != "cn":
        raise HTTPException(
            status_code=400,
            detail={
                "error": "unsupported_market",
                "message": "当前仅支持 A 股市场（cn）的热点板块分析",
            },
        )

    try:
        from src.services.sector_analysis_storage import get_sector_analysis_storage
        from src.services.sector_cache_service import get_sector_cache

        storage = get_sector_analysis_storage()
        cache = get_sector_cache()
        progress = cache.get_warmup_progress()
        cache_status = "ready"
        if progress.get("is_warming_up"):
            cache_status = "warming_up"
        elif not progress.get("last_warmup_time"):
            cache_status = "empty"

        target_date = date

        # 如果指定了日期，优先返回预计算数据
        if target_date:
            stored = storage.get(target_date)
            if stored:
                return HotSectorsResponse(
                    date=target_date,
                    sectors=stored.get("sectors", []),
                    total=stored.get("total", 0),
                    cache_status="pre_computed",
                )

        # 没有指定日期，返回最近可用的预计算数据
        if not target_date:
            latest = storage.get_latest_available()
            if latest:
                return HotSectorsResponse(
                    date=latest.get("date", ""),
                    sectors=latest.get("sectors", []),
                    total=latest.get("total", 0),
                    cache_status="pre_computed",
                )
            # 没有任何预计算数据，回退到实时分析
            from src.services.sector_analysis_scheduler import get_latest_trading_day
            target_date = get_latest_trading_day()
            cache_status = "realtime_fallback"

        # 实时分析（预计算不存在时回退）
        # 若爬虫已采集过当日涨停池，则传入复用其连板数，避免逐股拉K线（fail-open）
        scraper_limit_up_pool = None
        try:
            from src.services.board_scraper_storage import get_board_scraper_storage
            pool_date = target_date or datetime.now().strftime("%Y-%m-%d")
            scraper_limit_up_pool = get_board_scraper_storage().get_limit_up_pool_by_date(pool_date) or None
        except Exception as e:
            logger.debug(f"[热点板块分析] 读取爬虫涨停池失败（忽略）: {e}")

        analyzer = SectorAnalyzer()
        hot_sectors = analyzer.analyze(
            top_n=limit, min_limit_up=min_limit_up,
            date=date, allow_realtime_fetch=True,
            scraper_limit_up_pool=scraper_limit_up_pool,
        )

        sectors = []
        for hs in hot_sectors:
            sectors.append(hs.to_dict() if hasattr(hs, "to_dict") else _hot_sector_to_dict(hs))

        return HotSectorsResponse(
            date=target_date,
            sectors=sectors,
            total=len(sectors),
            cache_status=cache_status,
        )
    except Exception as e:
        logger.error(f"获取热点板块失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "internal_error",
                "message": f"获取热点板块失败: {str(e)}",
            },
        )


@router.get(
    "/rankings",
    response_model=SectorRankingsResponse,
    responses={
        200: {"description": "板块涨跌榜"},
        500: {"description": "服务器错误", "model": ErrorResponse},
    },
    summary="获取板块涨跌榜",
    description="获取行业板块领涨/领跌排行榜。",
)
def get_sector_rankings(
    market: str = Query("cn", description="市场：cn/hk/us", pattern="^(cn|hk|us)$"),
    limit: int = Query(10, ge=1, le=50, description="返回数量"),
) -> SectorRankingsResponse:
    try:
        from data_provider.base import DataFetcherManager
        dm = DataFetcherManager()
        top, bottom = dm.get_sector_rankings(limit)
        return SectorRankingsResponse(
            market=market,
            top=[SectorRankingItem(name=s["name"], change_pct=s.get("change_pct", 0.0)) for s in top],
            bottom=[SectorRankingItem(name=s["name"], change_pct=s.get("change_pct", 0.0)) for s in bottom],
        )
    except Exception as e:
        logger.error(f"获取板块涨跌榜失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "internal_error",
                "message": f"获取板块涨跌榜失败: {str(e)}",
            },
        )


@router.post(
    "/parse-manual",
    response_model=ManualSectorParseResponse,
    responses={
        200: {"description": "手动复盘文本解析结果"},
        400: {"description": "请求参数错误", "model": ErrorResponse},
        500: {"description": "服务器错误", "model": ErrorResponse},
    },
    summary="解析手动复盘文本",
    description="接收用户输入的Markdown或纯文本复盘内容，解析出结构化热点板块数据。",
)
def parse_manual_sectors(
    input_data: ManualSectorInput,
) -> ManualSectorParseResponse:
    try:
        from src.services.sector_manual_parser import parse_manual_sector_text

        parsed = parse_manual_sector_text(input_data.text)
        sectors = []
        for item in parsed:
            try:
                sectors.append(HotSectorItem(**item))
            except Exception:
                logger.warning(f"解析出的板块数据格式不匹配，已跳过: {item}")

        target_date = input_data.date or __import__("datetime").datetime.now().strftime("%Y-%m-%d")

        parse_info: Dict[str, Any] = {"raw_count": len(parsed), "valid_count": len(sectors)}
        market_sentiment = getattr(parsed, "market_sentiment", None)
        if market_sentiment:
            parse_info["market_sentiment"] = market_sentiment

        return ManualSectorParseResponse(
            date=target_date,
            sectors=sectors,
            total=len(sectors),
            parse_info=parse_info,
        )
    except ValueError as e:
        logger.error(f"手动复盘文本解析参数错误: {e}", exc_info=True)
        raise HTTPException(
            status_code=400,
            detail={
                "error": "invalid_input",
                "message": f"解析失败: {str(e)}",
            },
        )
    except Exception as e:
        logger.error(f"手动复盘文本解析失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "internal_error",
                "message": f"手动复盘文本解析失败: {str(e)}",
            },
        )


@router.post(
    "/trigger-scraper",
    response_model=ScraperBoardDataResponse,
    responses={
        200: {"description": "爬虫采集完成"},
        500: {"description": "服务器错误", "model": ErrorResponse},
    },
    summary="手动触发爬虫采集",
    description="立即执行一次 Playwright 爬虫，采集板块涨跌榜和涨停板池数据并保存。",
)
def trigger_scraper(
    date: Optional[str] = Query(None, description="日期（YYYY-MM-DD），默认今日"),
) -> ScraperBoardDataResponse:
    try:
        from data_provider.board_scraper_fetcher import BoardScraperFetcher
        from src.services.board_scraper_storage import get_board_scraper_storage

        target_date = date or datetime.now().strftime("%Y-%m-%d")
        logger.info("[触发爬虫] 开始采集板块数据...")

        fetcher = BoardScraperFetcher(headless=True)
        try:
            data = fetcher.scrape_all()
        finally:
            fetcher.close()

        storage = get_board_scraper_storage()
        storage.save_scrape_result(data)

        raw_sectors = storage.get_sector_rankings_by_date(target_date)
        raw_pool = storage.get_limit_up_pool_by_date(target_date)

        sectors = [
            ScraperSectorRankingItem(
                code=str(s.get("code", "")),
                name=str(s.get("sector_name", "") or s.get("name", "")),
                change_pct=float(s.get("change_pct", 0) or 0),
                rank_type=str(s.get("rank_type", "")),
                leader=str(s.get("leader", "")),
            )
            for s in raw_sectors
        ]

        limit_up_pool = [
            ScraperLimitUpItem(
                code=str(stock.get("code", "")),
                name=str(stock.get("name", "")),
                price=float(stock.get("price", 0) or 0),
                change_pct=float(stock.get("change_pct", 0) or 0),
                consecutive_days=int(stock.get("consecutive_days", 0) or 0),
                industry=str(stock.get("industry", "") or stock.get("sector", "")),

            )
            for stock in raw_pool
        ]

        # Build ladder from fetcher result
        raw_ladder = data.get("board_ladder") or {}
        board_ladder = [
            ScraperLadderTierItem(
                days=int(days),
                stocks=[
                    ScraperLadderStockItem(**s) for s in stocks
                ],
            )
            for days, stocks in sorted(raw_ladder.items(), reverse=True)
        ]

        logger.info("[触发爬虫] 采集完成: sectors=%d limit_up=%d ladder_tiers=%d", len(sectors), len(limit_up_pool), len(board_ladder))

        sector_stocks_raw = storage.get_sector_stocks_by_date(target_date)
        sector_stocks = [
            ScraperSectorDetailItem(
                sector_code=str(s.get("sector_code", "")),
                sector_name=str(s.get("sector_name", "")),
                sector_change_pct=float(s.get("sector_change_pct", 0) or 0),
                limit_up_count=int(s.get("limit_up_count", 0) or 0),
                limit_down_count=int(s.get("limit_down_count", 0) or 0),
                limit_up_stocks=[
                    ScraperSectorStockItem(**st) for st in s.get("limit_up_stocks", [])
                ],
                limit_down_stocks=[
                    ScraperSectorStockItem(**st) for st in s.get("limit_down_stocks", [])
                ],
            )
            for s in sector_stocks_raw
        ]

        return ScraperBoardDataResponse(
            date=target_date,
            sector_rankings=sectors,
            limit_up_pool=limit_up_pool,
            sector_stocks=sector_stocks,
            board_ladder=board_ladder,
        )
    except Exception as e:
        logger.error(f"触发爬虫失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "scraper_failed",
                "message": f"爬虫采集失败: {str(e)}",
            },
        )


@router.get(
    "/scraper-available-dates",
    response_model=List[str],
    summary="获取爬虫数据可用日期",
    description="返回有爬虫采集数据的日期列表。",
)
def get_scraper_available_dates() -> List[str]:
    try:
        from src.services.board_scraper_storage import get_board_scraper_storage
        storage = get_board_scraper_storage()
        return storage.get_available_dates()
    except Exception as e:
        logger.error(f"获取爬虫可用日期失败: {e}", exc_info=True)
        return []


@router.get(
    "/scraper-board-data",
    response_model=ScraperBoardDataResponse,
    responses={
        200: {"description": "爬虫板块原始数据"},
        500: {"description": "服务器错误", "model": ErrorResponse},
    },
    summary="获取爬虫板块原始数据",
    description="返回 BoardScraperFetcher 采集的原始板块涨跌榜和涨停板池数据。",
)
def get_scraper_board_data(
    date: Optional[str] = Query(None, description="日期（YYYY-MM-DD），默认最近一日"),
) -> ScraperBoardDataResponse:
    try:
        from src.services.board_scraper_storage import get_board_scraper_storage

        storage = get_board_scraper_storage()
        available = storage.get_available_dates()
        target_date = date or (available[0] if available else datetime.now().strftime("%Y-%m-%d"))

        raw_sectors = storage.get_sector_rankings_by_date(target_date)
        raw_pool = storage.get_limit_up_pool_by_date(target_date)

        sectors = [
            ScraperSectorRankingItem(
                code=str(s.get("code", "")),
                name=str(s.get("sector_name", "") or s.get("name", "")),
                change_pct=float(s.get("change_pct", 0) or 0),
                rank_type=str(s.get("rank_type", "")),
                leader=str(s.get("leader", "")),
            )
            for s in raw_sectors
        ]

        limit_up_pool = [
            ScraperLimitUpItem(
                code=str(stock.get("code", "")),
                name=str(stock.get("name", "")),
                price=float(stock.get("price", 0) or 0),
                change_pct=float(stock.get("change_pct", 0) or 0),
                consecutive_days=int(stock.get("consecutive_days", 0) or 0),
                industry=str(stock.get("industry", "") or stock.get("sector", "")),

            )
            for stock in raw_pool
        ]

        # Build ladder from storage
        raw_ladder = storage.get_board_ladder_by_date(target_date)
        board_ladder = []
        if raw_ladder:
            board_ladder = [
                ScraperLadderTierItem(
                    days=item["days"],
                    stocks=[ScraperLadderStockItem(**s) for s in item["stocks"]],
                )
                for item in raw_ladder
            ]

        sector_stocks_raw = storage.get_sector_stocks_by_date(target_date)
        sector_stocks = [
            ScraperSectorDetailItem(
                sector_code=str(s.get("sector_code", "")),
                sector_name=str(s.get("sector_name", "")),
                sector_change_pct=float(s.get("sector_change_pct", 0) or 0),
                limit_up_count=int(s.get("limit_up_count", 0) or 0),
                limit_down_count=int(s.get("limit_down_count", 0) or 0),
                limit_up_stocks=[
                    ScraperSectorStockItem(**st) for st in s.get("limit_up_stocks", [])
                ],
                limit_down_stocks=[
                    ScraperSectorStockItem(**st) for st in s.get("limit_down_stocks", [])
                ],
            )
            for s in sector_stocks_raw
        ]

        return ScraperBoardDataResponse(
            date=target_date,
            sector_rankings=sectors,
            limit_up_pool=limit_up_pool,
            sector_stocks=sector_stocks,
            board_ladder=board_ladder,
        )
    except Exception as e:
        logger.error(f"获取爬虫板块数据失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "internal_error",
                "message": f"获取爬虫板块数据失败: {str(e)}",
            },
        )


def _hot_sector_to_dict(hs: HotSector) -> dict:
    return {
        "name": hs.name,
        "change_pct": hs.change_pct,
        "limit_up_count": hs.limit_up_count,
        "limit_up_stocks": [
            {
                "code": s.code,
                "name": s.name,
                "change_pct": s.change_pct,
                "price": s.price,
                "is_limit_up": s.is_limit_up,
                "consecutive_limit_up_days": s.consecutive_limit_up_days,
            }
            for s in hs.limit_up_stocks
        ],
        "ladder": [
            {
                "days": r.days,
                "stock_code": r.stock_code,
                "stock_name": r.stock_name,
            }
            for r in hs.ladder
        ],
        "leader": {
            "code": hs.leader.code,
            "name": hs.leader.name,
            "change_pct": hs.leader.change_pct,
            "price": hs.leader.price,
            "is_limit_up": hs.leader.is_limit_up,
            "consecutive_limit_up_days": hs.leader.consecutive_limit_up_days,
        } if hs.leader else None,
        "leader_correlation": hs.leader_correlation,
        "score": hs.score,
    }


@router.post(
    "/trigger-analysis",
    response_model=HotSectorsResponse,
    responses={
        200: {"description": "触发分析成功，返回最新热点板块"},
        500: {"description": "服务器错误", "model": ErrorResponse},
    },
    summary="手动触发热点分析",
    description="立即执行一次热点板块分析，等待完成后返回最新结果。",
)
def trigger_analysis(
    limit: int = Query(20, ge=1, le=50, description="返回板块数量上限"),
    min_limit_up: int = Query(1, ge=0, le=20, description="最小涨停家数门槛"),
) -> HotSectorsResponse:
    try:
        from src.services.sector_analysis_scheduler import run_sector_analysis_now
        from src.services.sector_analysis_storage import get_sector_analysis_storage

        logger.info("[触发分析] 收到手动触发请求，开始执行...")
        ok = run_sector_analysis_now()

        if not ok:
            raise HTTPException(
                status_code=500,
                detail={"error": "analysis_failed", "message": "热点分析执行失败"},
            )

        # 返回刚生成的最新数据
        storage = get_sector_analysis_storage()
        latest = storage.get_latest_available()
        if not latest:
            raise HTTPException(
                status_code=500,
                detail={"error": "no_data", "message": "分析完成但未找到存储数据"},
            )

        sectors = latest.get("sectors", [])[:limit]
        return HotSectorsResponse(
            date=latest.get("date", ""),
            sectors=sectors,
            total=latest.get("total", 0),
            cache_status="pre_computed",
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"手动触发分析失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={"error": "internal_error", "message": f"触发分析失败: {str(e)}"},
        )


@router.get(
    "/available-dates",
    response_model=List[str],
    summary="获取有预计算数据的日期列表",
    description="返回最近 30 个有预计算热点板块分析的日期。",
)
def get_available_dates() -> List[str]:
    try:
        from src.services.sector_analysis_storage import get_sector_analysis_storage
        storage = get_sector_analysis_storage()
        return storage.get_available_dates(30)
    except Exception as e:
        logger.error(f"获取可用日期失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={"error": "internal_error", "message": str(e)},
        )
