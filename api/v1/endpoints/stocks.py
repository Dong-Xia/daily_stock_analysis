# -*- coding: utf-8 -*-
"""
===================================
股票数据接口
===================================

职责：
1. POST /api/v1/stocks/extract-from-image 从图片提取股票代码
2. POST /api/v1/stocks/parse-import 解析 CSV/Excel/剪贴板
3. GET /api/v1/stocks/{code}/quote 实时行情接口
4. GET /api/v1/stocks/{code}/history 历史行情接口
"""

import logging
import threading
from datetime import date
from typing import Optional

from fastapi import APIRouter, File, HTTPException, Query, Request, UploadFile

from api.v1.schemas.stocks import (
    ExtractFromImageResponse,
    ExtractItem,
    KLineData,
    StockHistoryResponse,
    StockQuote,
)
from api.v1.schemas.common import ErrorResponse
from src.services.image_stock_extractor import (
    ALLOWED_MIME,
    MAX_SIZE_BYTES,
    extract_stock_codes_from_image,
)
from src.services.import_parser import (
    MAX_FILE_BYTES,
    parse_import_from_bytes,
    parse_import_from_text,
)
from src.services.stock_service import StockService

logger = logging.getLogger(__name__)

router = APIRouter()

# 须在 /{stock_code} 路由之前定义
ALLOWED_MIME_STR = ", ".join(ALLOWED_MIME)


@router.post(
    "/extract-from-image",
    response_model=ExtractFromImageResponse,
    responses={
        200: {"description": "提取的股票代码"},
        400: {"description": "图片无效", "model": ErrorResponse},
        500: {"description": "服务器错误", "model": ErrorResponse},
    },
    summary="从图片提取股票代码",
    description="上传截图/图片，通过 Vision LLM 提取股票代码。支持 JPEG、PNG、WebP、GIF，最大 5MB。",
)
def extract_from_image(
    file: Optional[UploadFile] = File(None, description="图片文件（表单字段名 file）"),
    include_raw: bool = Query(False, description="是否在结果中包含原始 LLM 响应"),
) -> ExtractFromImageResponse:
    """
    从上传的图片中提取股票代码（使用 Vision LLM）。

    表单字段请使用 file 上传图片。优先级：Gemini / Anthropic / OpenAI（首个可用）。
    """
    if not file or not file.filename:
        raise HTTPException(
            status_code=400,
            detail={"error": "bad_request", "message": "未提供文件，请使用表单字段 file 上传图片"},
        )

    content_type = (file.content_type or "").split(";")[0].strip().lower()
    if content_type not in ALLOWED_MIME:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "unsupported_type",
                "message": f"不支持的类型: {content_type}。允许: {ALLOWED_MIME_STR}",
            },
        )

    try:
        # 先读取限定大小，再检查是否还有剩余（语义清晰：超出则拒绝）
        data = file.file.read(MAX_SIZE_BYTES)
        if file.file.read(1):
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "file_too_large",
                    "message": f"图片超过 {MAX_SIZE_BYTES // (1024 * 1024)}MB 限制",
                },
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.warning(f"读取上传文件失败: {e}")
        raise HTTPException(
            status_code=400,
            detail={"error": "read_failed", "message": "读取上传文件失败"},
        )

    try:
        items, raw_text = extract_stock_codes_from_image(data, content_type)
        extract_items = [
            ExtractItem(code=code, name=name, confidence=conf) for code, name, conf in items
        ]
        codes = [i.code for i in extract_items]
        return ExtractFromImageResponse(
            codes=codes,
            items=extract_items,
            raw_text=raw_text if include_raw else None,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail={"error": "extract_failed", "message": str(e)})
    except Exception as e:
        logger.error(f"图片提取失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={"error": "internal_error", "message": "图片提取失败"},
        )


@router.post(
    "/parse-import",
    response_model=ExtractFromImageResponse,
    responses={
        200: {"description": "解析结果"},
        400: {"description": "未提供数据或解析失败", "model": ErrorResponse},
        500: {"description": "服务器错误", "model": ErrorResponse},
    },
    summary="解析 CSV/Excel/剪贴板",
    description="上传 CSV/Excel 文件或粘贴文本，自动解析股票代码。文件上限 2MB，文本上限 100KB。",
)
async def parse_import(request: Request) -> ExtractFromImageResponse:
    """
    解析 CSV/Excel 文件或剪贴板文本。

    - multipart/form-data + file: 上传文件
    - application/json + {"text": "..."}: 粘贴文本
    - 优先使用 file，若同时提供则忽略 text
    """
    content_type = (request.headers.get("content-type") or "").lower()

    if "application/json" in content_type:
        try:
            body = await request.json()
        except Exception as e:
            logger.warning("[parse_import] JSON parse failed: %s", e)
            raise HTTPException(
                status_code=400,
                detail={"error": "invalid_json", "message": f"JSON 解析失败: {e}"},
            )
        text = body.get("text") if isinstance(body, dict) else None
        if not text or not isinstance(text, str):
            raise HTTPException(
                status_code=400,
                detail={"error": "bad_request", "message": "未提供 text，请使用 {\"text\": \"...\"}"},
            )
        try:
            items = parse_import_from_text(text)
        except ValueError as e:
            text_bytes = len(text.encode("utf-8"))
            logger.warning(
                "[parse_import] parse_import_from_text failed: text_bytes=%d, error=%s",
                text_bytes,
                e,
            )
            raise HTTPException(status_code=400, detail={"error": "parse_failed", "message": str(e)})
    elif "multipart" in content_type:
        form = await request.form()
        file = form.get("file")
        if not file or not hasattr(file, "read"):
            raise HTTPException(
                status_code=400,
                detail={"error": "bad_request", "message": "未提供文件，请使用表单字段 file"},
            )
        file_size = getattr(file, "size", None)
        if isinstance(file_size, int) and file_size > MAX_FILE_BYTES:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "file_too_large",
                    "message": f"文件超过 {MAX_FILE_BYTES // (1024 * 1024)}MB 限制",
                },
            )
        try:
            data = file.file.read(MAX_FILE_BYTES)
            if file.file.read(1):
                raise HTTPException(
                    status_code=400,
                    detail={
                        "error": "file_too_large",
                        "message": f"文件超过 {MAX_FILE_BYTES // (1024 * 1024)}MB 限制",
                    },
                )
        except HTTPException:
            raise
        except Exception as e:
            filename = getattr(file, "filename", None) or ""
            size = getattr(file, "size", None)
            logger.warning(
                "[parse_import] file read failed: filename=%r, size=%s, error=%s",
                filename,
                size,
                e,
            )
            raise HTTPException(
                status_code=400,
                detail={"error": "read_failed", "message": "读取文件失败"},
            )
        filename = getattr(file, "filename", None) or ""
        try:
            items = parse_import_from_bytes(data, filename=filename)
        except ValueError as e:
            ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
            logger.warning(
                "[parse_import] parse_import_from_bytes failed: filename=%r, ext=%r, bytes=%d, error=%s",
                filename,
                ext,
                len(data),
                e,
            )
            raise HTTPException(status_code=400, detail={"error": "parse_failed", "message": str(e)})
    else:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "bad_request",
                "message": "请使用 multipart/form-data 上传文件，或 application/json 提交 {\"text\": \"...\"}",
            },
        )

    extract_items = [
        ExtractItem(code=code, name=name, confidence=conf)
        for code, name, conf in items
    ]
    codes = list(dict.fromkeys(i.code for i in extract_items if i.code))
    return ExtractFromImageResponse(codes=codes, items=extract_items, raw_text=None)


@router.post(
    "/triple-volume",
    summary="三倍量战法选股",
    description="基于通达信三倍量战法公式的A股选股器。实时行情预筛选（涨幅≥5%、换手≥3%）→ K线细筛（3倍量、均线多头、低位区间、实体阳线）。",
)
async def triple_volume_screen(
    min_volume_ratio: float = Query(3.0, ge=2.0, le=5.0, description="最低量比倍数"),
    min_change_pct: float = Query(5.0, ge=3.0, le=10.0, description="最低涨幅(%)"),
    min_turnover_rate: float = Query(3.0, ge=1.0, le=10.0, description="最低换手率(%)"),
):
    import asyncio

    from src.services.triple_volume_screener import TripleVolumeScreener

    screener = TripleVolumeScreener(
        min_volume_ratio=min_volume_ratio,
        min_change_pct=min_change_pct,
        min_turnover_rate=min_turnover_rate,
    )
    try:
        result = await asyncio.wait_for(asyncio.to_thread(screener.screen), timeout=180.0)
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="三倍量选股超时，请稍后重试")
    return result


@router.post(
    "/oversold-bounce",
    summary="超跌反弹战法选股",
    description="基于恐慌情绪的超跌反弹选股器。大盘恐慌判断（连续下跌+大阴线+远离5日线）+ 个股超跌筛选（跌幅大、乖离率高、换手放大）。",
)
async def oversold_bounce_screen(
    lookback_days: int = Query(5, ge=3, le=10, description="回看天数"),
    min_drop_pct: float = Query(20.0, ge=10.0, le=40.0, description="最低N日跌幅(%)"),
    max_bias_pct: float = Query(-8.0, ge=-15.0, le=-5.0, description="5日线乖离率上限(%)"),
):
    import asyncio

    from src.services.oversold_bounce_screener import OversoldBounceScreener

    screener = OversoldBounceScreener(
        lookback_days=lookback_days,
        min_drop_pct=min_drop_pct,
        max_bias_pct=max_bias_pct,
    )
    try:
        result = await asyncio.wait_for(asyncio.to_thread(screener.screen), timeout=180.0)
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="超跌反弹选股超时，请稍后重试")
    return result


@router.post(
    "/industry-research",
    summary="产业链研究战法选股",
    description="基于逆向工程拆解产业链BOM，锁定'扩产周期长、技术门槛高、不可替代'的物理级瓶颈环节，筛选市值30-500亿的中小盘隐形冠军，穿透财务拐点，AI红队测试+熔断机制。",
)
async def industry_research_screen(
    sector: str = Query(..., min_length=1, description="行业/板块名称，如：半导体、新能源"),
    min_market_cap_yi: float = Query(30.0, description="最低市值(亿)"),
    max_market_cap_yi: float = Query(500.0, description="最高市值(亿)"),
    min_composite_score: float = Query(60.0, description="最低综合评分"),
):
    import asyncio

    from src.services.industry_research_screener import IndustryResearchScreener

    screener = IndustryResearchScreener(
        min_market_cap_yi=min_market_cap_yi,
        max_market_cap_yi=max_market_cap_yi,
        min_composite_score=min_composite_score,
    )
    try:
        result = await asyncio.wait_for(
            asyncio.to_thread(screener.screen, sector),
            timeout=120.0,
        )
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="产业链研究选股超时，请稍后重试")
    return result


@router.get(
    "/{stock_code}/quote",
    response_model=StockQuote,
    responses={
        200: {"description": "行情数据"},
        404: {"description": "股票不存在", "model": ErrorResponse},
        500: {"description": "服务器错误", "model": ErrorResponse},
    },
    summary="获取股票实时行情",
    description="获取指定股票的最新行情数据"
)
def get_stock_quote(stock_code: str) -> StockQuote:
    """
    获取股票实时行情
    
    获取指定股票的最新行情数据
    
    Args:
        stock_code: 股票代码（如 600519、00700、AAPL）
        
    Returns:
        StockQuote: 实时行情数据
        
    Raises:
        HTTPException: 404 - 股票不存在
    """
    try:
        service = StockService()
        
        # 使用 def 而非 async def，FastAPI 自动在线程池中执行
        result = service.get_realtime_quote(stock_code)
        
        if result is None:
            raise HTTPException(
                status_code=404,
                detail={
                    "error": "not_found",
                    "message": f"未找到股票 {stock_code} 的行情数据"
                }
            )
        
        return StockQuote(
            stock_code=result.get("stock_code", stock_code),
            stock_name=result.get("stock_name"),
            current_price=result.get("current_price", 0.0),
            change=result.get("change"),
            change_percent=result.get("change_percent"),
            open=result.get("open"),
            high=result.get("high"),
            low=result.get("low"),
            prev_close=result.get("prev_close"),
            volume=result.get("volume"),
            amount=result.get("amount"),
            update_time=result.get("update_time")
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取实时行情失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "internal_error",
                "message": f"获取实时行情失败: {str(e)}"
            }
        )


@router.get(
    "/{stock_code}/history",
    response_model=StockHistoryResponse,
    responses={
        200: {"description": "历史行情数据"},
        422: {"description": "不支持的周期参数", "model": ErrorResponse},
        500: {"description": "服务器错误", "model": ErrorResponse},
    },
    summary="获取股票历史行情",
    description="获取指定股票的历史 K 线数据"
)
def get_stock_history(
    stock_code: str,
    period: str = Query("daily", description="K 线周期", pattern="^(daily|weekly|monthly)$"),
    days: int = Query(30, ge=1, le=365, description="获取天数")
) -> StockHistoryResponse:
    """
    获取股票历史行情
    
    获取指定股票的历史 K 线数据
    
    Args:
        stock_code: 股票代码
        period: K 线周期 (daily/weekly/monthly)
        days: 获取天数
        
    Returns:
        StockHistoryResponse: 历史行情数据
    """
    try:
        service = StockService()
        
        # 使用 def 而非 async def，FastAPI 自动在线程池中执行
        result = service.get_history_data(
            stock_code=stock_code,
            period=period,
            days=days
        )
        
        # 转换为响应模型
        data = [
            KLineData(
                date=item.get("date"),
                open=item.get("open"),
                high=item.get("high"),
                low=item.get("low"),
                close=item.get("close"),
                volume=item.get("volume"),
                amount=item.get("amount"),
                change_percent=item.get("change_percent")
            )
            for item in result.get("data", [])
        ]
        
        return StockHistoryResponse(
            stock_code=stock_code,
            stock_name=result.get("stock_name"),
            period=period,
            data=data
        )
    
    except ValueError as e:
        # period 参数不支持的错误（如 weekly/monthly）
        raise HTTPException(
            status_code=422,
            detail={
                "error": "unsupported_period",
                "message": str(e)
            }
        )
    except Exception as e:
        logger.error(f"获取历史行情失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "internal_error",
                "message": f"获取历史行情失败: {str(e)}"
            }
        )


# ── 市场状态缓存（按交易日缓存，当天触发分析后直接存下来，下次点击直返） ──
_market_regime_cache: dict[str, object] = {}
_market_regime_cache_lock = threading.Lock()


@router.get(
    "/market-regime",
    summary="市场状态分类",
    description="基于趋势/量能/宽度/波动率/情绪维度的7阶段市场分类器。当天触发分析后缓存结果，下次点击直接返回。",
)
async def market_regime():
    from src.core.market_regime import MarketRegimeClassifier
    from src.schemas.stock_screener_schema import (
        DimensionEvidence,
        MarketRegime,
        RegimeResult,
        get_regime_label,
        get_regime_recommendation,
    )
    import asyncio

    today = date.today().isoformat()

    with _market_regime_cache_lock:
        cached = _market_regime_cache.get(today)
        if cached is not None:
            logger.info("[MarketRegime] 命中当天缓存 %s", today)
            return cached

    logger.info("[MarketRegime] 无缓存，执行分析 %s", today)
    classifier = MarketRegimeClassifier()

    try:
        result = await asyncio.wait_for(
            asyncio.to_thread(classifier.classify),
            timeout=90.0,
        )
        # 分析成功 → 写入缓存
        with _market_regime_cache_lock:
            _market_regime_cache[today] = result
            logger.info("[MarketRegime] 缓存已写入 %s", today)

    except asyncio.TimeoutError:
        logger.warning("[MarketRegime] 分析超时（90s），返回默认横盘震荡（不缓存，下次可重试）")
        result = RegimeResult(
            regime=MarketRegime.RANGE_BOUND,
            regime_label=get_regime_label(MarketRegime.RANGE_BOUND),
            confidence=30,
            position_factor=0.30,
            recommendation=get_regime_recommendation(MarketRegime.RANGE_BOUND),
            evidence=[
                DimensionEvidence(dimension="trend", score=50, signal="neutral", detail="超时: 默认中立"),
                DimensionEvidence(dimension="volume", score=50, signal="neutral", detail="超时: 默认中立"),
                DimensionEvidence(dimension="breadth", score=50, signal="neutral", detail="超时: 默认中立"),
                DimensionEvidence(dimension="volatility", score=50, signal="neutral", detail="超时: 默认中立"),
                DimensionEvidence(dimension="sentiment", score=50, signal="neutral", detail="超时: 默认中立"),
            ],
        )

    return result


@router.post(
    "/screen",
    summary="板块选股",
    description="基于板块成分股执行4层漏斗筛选（流动性→趋势→排名→评分），返回候选股票列表。",
)
async def screen_stocks(
    sector_name: str = Query(..., min_length=1, description="板块名称, e.g. 半导体"),
    min_avg_amount_yi: float = Query(1.0, description="日均成交额最低门槛(亿)"),
    min_turnover_rate: float = Query(1.0, description="最低换手率(%)"),
    require_ma_alignment: bool = Query(True, description="是否要求均线多头排列"),
):
    import asyncio

    from src.services.stock_screener_service import StockScreenerService
    from src.schemas.stock_screener_schema import ScreenerCriteria

    if not sector_name.strip():
        raise HTTPException(status_code=400, detail={"error": "bad_request", "message": "板块名称不能为空"})

    criteria = ScreenerCriteria(
        sector_name=sector_name.strip(),
        min_avg_amount_yi=min_avg_amount_yi,
        min_turnover_rate=min_turnover_rate,
        require_ma_alignment=require_ma_alignment,
    )
    service = StockScreenerService()
    try:
        result = await asyncio.wait_for(asyncio.to_thread(service.screen, criteria), timeout=180.0)
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="板块选股超时，请稍后重试")
    return result


@router.get(
    "/sector-rotation",
    summary="板块轮动分析",
    description="基于多日排行榜分析板块持续性、动量和分类（主线/轮动/脉冲/退潮）。",
)
async def sector_rotation(
    lookback_days: int = Query(20, ge=5, le=60, description="回看天数"),
):
    from src.services.sector_rotation_tracker import SectorRotationTracker
    import asyncio

    tracker = SectorRotationTracker(lookback_days=lookback_days)
    result = await asyncio.to_thread(tracker.analyze)
    return result


@router.post(
    "/position-size",
    summary="仓位计算",
    description="基于Kelly公式和风控参数的动态仓位计算。",
)
async def position_size(
    stock_code: str = Query(...),
    entry_price: float = Query(...),
    stop_loss_price: float = Query(...),
    account_equity: float = Query(...),
    market_regime_factor: float = Query(0.5),
    signal_confidence: int = Query(50),
    max_positions: int = Query(5),
):
    from src.services.position_sizer import PositionSizer, SizeRequest
    import asyncio

    req = SizeRequest(
        stock_code=stock_code,
        entry_price=entry_price,
        stop_loss_price=stop_loss_price,
        account_equity=account_equity,
        market_regime_factor=market_regime_factor,
        signal_confidence=signal_confidence,
        max_positions=max_positions,
    )
    sizer = PositionSizer()
    result = await asyncio.to_thread(sizer.calculate, req)
    return result


@router.post(
    "/stop-loss",
    summary="止损评估",
    description="计算入场止损位并评估当前价格是否触发止损（硬止损/时间止损）。",
)
async def stop_loss_check(
    stock_code: str = Query(...),
    entry_price: float = Query(...),
    current_price: float = Query(...),
    stop_price: float = Query(...),
    entry_date: str = Query(""),
):
    from src.services.stop_loss_manager import StopLossManager, StopConfig
    import asyncio

    mgr = StopLossManager()
    config = StopConfig(
        stock_code=stock_code,
        entry_price=entry_price,
        stop_price=stop_price,
        entry_date=entry_date,
    )
    result = await asyncio.to_thread(mgr.evaluate, config, current_price)
    return result


@router.post(
    "/rebalance",
    summary="调仓分析",
    description="持仓排名（RS相对强度）+去弱留强调仓信号生成。",
)
async def rebalance(
    positions: str = Query(..., description="持仓数据: CODE:PRICE:SECTOR,CODE:PRICE:SECTOR"),
):
    from src.services.rebalance_engine import RebalanceEngine
    import asyncio

    parsed = []
    for pair in positions.split(","):
        parts = pair.split(":")
        if len(parts) >= 2:
            parsed.append({"code": parts[0], "current_price": float(parts[1]), "cost_price": float(parts[1]), "sector": parts[2] if len(parts) > 2 else "", "return_pct": 0})
    engine = RebalanceEngine()
    result = await asyncio.to_thread(engine.analyze, parsed)
    return result


@router.post(
    "/hot-sector-chain",
    summary="热点板块链式选股",
    description="自动从板块轮动锁定结果中选取 Top 5 热点板块，逐个调用个股精选（带限流间隔），聚合返回结果。",
)
async def hot_sector_chain():
    import asyncio

    from src.services.sector_to_stock_selector import SectorToStockSelector

    selector = SectorToStockSelector()
    try:
        result = await asyncio.wait_for(
            asyncio.to_thread(selector.execute),
            timeout=300.0,
        )
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="热点板块链式选股超时，请稍后重试")
    return result


@router.get(
    "/fundamental",
    summary="基本面选股",
    description="全市场财报数据多条件筛选（营收增长、利润增长、净利润门槛）。基于 AkShare stock_yjbb_em。",
)
async def fundamental_screen(
    quarter_date: str = Query("", description="财报日期 YYYYMMDD, 空=最新季度"),
):
    import asyncio

    from src.config import get_config
    from src.services.fundamental_screener import FundamentalScreener

    q = quarter_date if quarter_date else None
    screener = FundamentalScreener(max_candidates=get_config().fundamental_max_candidates)
    try:
        result = await asyncio.wait_for(asyncio.to_thread(screener.screen, q), timeout=180.0)
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="基本面选股超时，请稍后重试")
    return result
