# -*- coding: utf-8 -*-
"""
===================================
Stock Screener Service - 4-Layer Funnel
===================================

Layer 1: liquidity filter → Layer 2: trend filter → Layer 3: intra-sector ranking → Layer 4: composite scoring.
"""
from __future__ import annotations

import json
import logging
import time
from concurrent.futures import ThreadPoolExecutor, wait
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from data_provider.base import DataFetcherManager, normalize_stock_code

from src.schemas.stock_screener_schema import (
    FactorBreakdown,
    MarketRegime,
    RegimeResult,
    ScreenerCandidate,
    ScreenerCriteria,
    ScreenerResult,
    get_regime_label,
)

logger = logging.getLogger(__name__)


class StockScreenerService:
    """4-layer sector-based stock screener: liquidity → trend → ranking → scoring."""

    def __init__(
        self,
        data_manager: Optional[DataFetcherManager] = None,
        regime_classifier=None,
        min_avg_amount_yi: float = 1.0,
        min_turnover_rate: float = 1.0,
        rs_lookback_days: int = 20,
        top_n_ratio: float = 0.3,
        max_candidates: int = 10,
        max_l2_analyze: int = 30,
        score_weights: Optional[Dict[str, float]] = None,
        parallel_workers: int = 5,
        timeout_budget: float = 170.0,
    ):
        self.data_manager = data_manager or DataFetcherManager()
        self.min_avg_amount_yi = min_avg_amount_yi
        self.min_turnover_rate = min_turnover_rate
        self.rs_lookback_days = rs_lookback_days
        self.top_n_ratio = top_n_ratio
        self.max_candidates = max_candidates
        self.max_l2_analyze = max_l2_analyze
        self.parallel_workers = parallel_workers
        self.timeout_budget = timeout_budget

        default_weights = {
            "trend_strength": 0.25,
            "rs_score": 0.25,
            "volume_confirmation": 0.15,
            "bias_from_ma5": 0.10,
            "limit_up_proximity": 0.10,
            "sector_leadership": 0.15,
        }
        self.score_weights = score_weights or default_weights

        self._regime_classifier = regime_classifier

    def _get_regime_classifier(self):
        if self._regime_classifier is None:
            try:
                from src.core.market_regime import MarketRegimeClassifier

                self._regime_classifier = MarketRegimeClassifier()
            except ImportError:
                logger.warning(
                    "MarketRegimeClassifier not available; "
                    "regime classification will return None."
                )
                self._regime_classifier = None
        return self._regime_classifier

    def screen(self, criteria: ScreenerCriteria) -> ScreenerResult:
        """Execute the 4-layer screening pipeline.

        收盘后同一板块同日查询优先使用缓存，避免重复数据源调用。
        """
        sector_name = criteria.sector_name or ""
        backtest_date = criteria.backtest_date

        # Calculate deadline for time-budget control (realtime mode only)
        deadline = (time.monotonic() + self.timeout_budget) if not backtest_date else None

        # Cache check (realtime mode only, same-day reuse)
        if not backtest_date:
            try:
                from src.core.trading_calendar import get_effective_trading_date
                from src.services.screener_cache import get_screener_cache

                effective_date = get_effective_trading_date("cn")
                date_str = effective_date.isoformat() if effective_date else None
                if date_str:
                    cache = get_screener_cache()
                    cached = cache.get(sector_name, date_str)
                    if cached is not None:
                        return ScreenerResult.model_validate(cached)
            except Exception as e:
                logger.debug("[选股] 缓存查询失败, 继续实时计算: %s", e)

        # Pre-classify market regime
        try:
            classifier = self._get_regime_classifier()
            regime_result = classifier.classify(date=backtest_date)
        except Exception as e:
            logger.warning("[选股] 市场状态分类失败: %s, 使用默认", e)
            regime_result = RegimeResult(
                regime=MarketRegime.RANGE_BOUND,
                regime_label=get_regime_label(MarketRegime.RANGE_BOUND),
                confidence=30,
                position_factor=0.3,
                recommendation="",
                evidence=[],
            )

        # Get sector stock codes
        stocks = self._get_sector_stock_codes(sector_name, backtest_date)
        total_considered = len(stocks)
        if not stocks:
            return ScreenerResult(
                regime=regime_result,
                candidates=[],
                total_considered=0,
                after_liquidity=0,
                after_trend=0,
                after_ranking=0,
                sector_name=sector_name,
                timestamp=datetime.now().isoformat(),
                mode="backtest" if backtest_date else "realtime",
            )

        # Pre-trim: limit stocks entering expensive realtime-quote fetch (Layer 1)
        # and daily-data fetch (Layer 2). change_pct is already available from
        # board members, so sort by absolute change to focus on actively moving stocks.
        before_trim = len(stocks)
        stocks.sort(key=lambda s: abs(s.get("change_pct", 0)), reverse=True)
        pre_l1_max = max(self.max_l2_analyze, self.parallel_workers * 2)  # keep ~2x L2 for fallback
        stocks = stocks[:pre_l1_max]
        logger.info("[选股] 预裁剪: %d → %d (保留涨幅最大)", before_trim, len(stocks))

        # Layer 1: liquidity (parallel enriched, all pass through)
        survivors_l1, _ = self._layer1_liquidity_filter(stocks, criteria, backtest_date, deadline=deadline)
        after_liquidity = len(survivors_l1)
        if not survivors_l1:
            return ScreenerResult(
                regime=regime_result,
                candidates=[],
                total_considered=total_considered,
                after_liquidity=after_liquidity,
                after_trend=0,
                after_ranking=0,
                sector_name=sector_name,
                timestamp=datetime.now().isoformat(),
                mode="backtest" if backtest_date else "realtime",
            )

        # Trim: limit stocks entering expensive Layer 2 (Tushare calls)
        before_trim = len(survivors_l1)
        survivors_l1.sort(key=lambda s: abs(s.get("change_pct", 0)), reverse=True)
        survivors_l1 = survivors_l1[:self.max_l2_analyze]
        after_liquidity = len(survivors_l1)
        logger.info("[选股] L1→L2 裁剪: %d → %d (保留涨幅最大)", before_trim, after_liquidity)

        # Layer 2: trend (parallel daily data fetch, with deadline guard)
        survivors_l2, _ = self._layer2_trend_filter(survivors_l1, criteria, backtest_date, deadline=deadline)
        after_trend = len(survivors_l2)
        if not survivors_l2:
            return ScreenerResult(
                regime=regime_result,
                candidates=[],
                total_considered=total_considered,
                after_liquidity=after_liquidity,
                after_trend=after_trend,
                after_ranking=0,
                sector_name=sector_name,
                timestamp=datetime.now().isoformat(),
                mode="backtest" if backtest_date else "realtime",
            )

        # Layer 3: intra-sector ranking
        survivors_l3, _ = self._layer3_intra_sector_ranking(survivors_l2, backtest_date)
        after_ranking = len(survivors_l3)

        # Layer 4: composite scoring
        candidates = self._layer4_composite_scoring(survivors_l3, sector_name=sector_name)

        result = ScreenerResult(
            regime=regime_result,
            candidates=candidates[:criteria.max_candidates],
            total_considered=total_considered,
            after_liquidity=after_liquidity,
            after_trend=after_trend,
            after_ranking=after_ranking,
            sector_name=sector_name,
            timestamp=datetime.now().isoformat(),
            mode="backtest" if backtest_date else "realtime",
        )

        # Cache the result for same-day reuse (realtime mode only)
        if not backtest_date and candidates:
            try:
                from src.services.screener_cache import get_screener_cache
                from src.core.trading_calendar import get_effective_trading_date

                effective_date = get_effective_trading_date("cn")
                if effective_date:
                    cache = get_screener_cache()
                    cache.set(
                        sector_name,
                        effective_date.isoformat(),
                        result.model_dump(mode="json"),
                    )
            except Exception as e:
                logger.debug("[选股] 缓存写入失败: %s", e)

        return result

    def _get_sector_stock_codes(
        self, sector_name: str, date: Optional[str]
    ) -> List[Dict[str, Any]]:
        """Fetch board members for a sector via DataFetcherManager."""
        if not sector_name:
            return []

        members = self.data_manager.get_board_members(sector_name, board_type="industry")
        if not members:
            members = self.data_manager.get_board_members(sector_name, board_type="concept")

        if not members:
            logger.warning("[选股] 板块 '%s' 无成分股数据", sector_name)
            return []

        stocks: List[Dict[str, Any]] = []
        for m in members:
            code = normalize_stock_code(str(m.get("code", "")))
            name = str(m.get("name", ""))
            try:
                price = float(m.get("price", 0) or 0)
                change_pct = float(m.get("change_pct", 0) or 0)
            except (ValueError, TypeError):
                price = 0.0
                change_pct = 0.0
            stocks.append({
                "code": code,
                "name": name,
                "price": price,
                "change_pct": change_pct,
            })

        logger.info("[选股] 板块 '%s' 共 %d 只成分股 (来源: %s)", sector_name, len(stocks),
                     "board_scraper" if members else "data_manager")
        return stocks

    def _get_daily_data_best_effort(self, code: str, days: int = 60, end_date: Optional[str] = None) -> Optional[pd.DataFrame]:
        try:
            df, _ = self.data_manager.get_daily_data(code, end_date=end_date, days=days)
            if df is not None and not df.empty:
                return df
        except Exception:
            pass
        return None

    def _parallel_fetch_realtime_quotes(
        self, codes: List[str], max_workers: Optional[int] = None,
        deadline: Optional[float] = None
    ) -> Dict[str, Optional[Any]]:
        if not codes:
            return {}
        n_workers = max_workers or self.parallel_workers
        results: Dict[str, Optional[Any]] = {}
        executor = ThreadPoolExecutor(max_workers=n_workers)
        try:
            future_map = {}
            for code in codes:
                future_map[executor.submit(
                    self.data_manager.get_realtime_quote, code, log_final_failure=False
                )] = code
            pending = set(future_map.keys())
            while pending:
                if deadline is not None and time.monotonic() > deadline:
                    logger.warning("[选股] 并行获取实时行情已达 deadline，跳过剩余 %d 只", len(pending))
                    break
                done, pending = wait(pending, timeout=5)
                for future in done:
                    code = future_map[future]
                    try:
                        results[code] = future.result(timeout=1)
                    except Exception:
                        results[code] = None
        finally:
            executor.shutdown(wait=False)
        return results

    def _parallel_fetch_daily_data(
        self, codes: List[str], days: int = 60, end_date: Optional[str] = None,
        max_workers: Optional[int] = None, deadline: Optional[float] = None
    ) -> Dict[str, Optional[pd.DataFrame]]:
        if not codes:
            return {}
        n_workers = max_workers or self.parallel_workers
        results: Dict[str, Optional[pd.DataFrame]] = {}
        executor = ThreadPoolExecutor(max_workers=n_workers)
        try:
            future_map = {
                executor.submit(self._get_daily_data_best_effort, code, days, end_date): code
                for code in codes
            }
            pending = set(future_map.keys())
            while pending:
                if deadline is not None and time.monotonic() > deadline:
                    logger.warning("[选股] 并行获取日线已达 deadline，跳过剩余 %d 只", len(pending))
                    break
                done, pending = wait(pending, timeout=5)
                for future in done:
                    code = future_map[future]
                    try:
                        results[code] = future.result(timeout=1)
                    except Exception:
                        results[code] = None
        finally:
            executor.shutdown(wait=False)
        return results

    def _layer1_liquidity_filter(
        self, stocks: List[Dict], criteria: ScreenerCriteria, date: Optional[str],
        deadline: Optional[float] = None,
    ) -> Tuple[List[Dict], int]:
        survivors: List[Dict] = []
        input_count = len(stocks)

        min_amount = getattr(criteria, "min_avg_amount_yi", self.min_avg_amount_yi)
        min_turnover = getattr(criteria, "min_turnover_rate", self.min_turnover_rate)

        codes_to_fetch = [
            s["code"] for s in stocks
            if s.get("turnover_rate", 0) <= 0 and s.get("code", "")
        ]
        if codes_to_fetch:
            quotes = self._parallel_fetch_realtime_quotes(codes_to_fetch, deadline=deadline)
            for stock in stocks:
                code = stock.get("code", "")
                q = quotes.get(code)
                if q and hasattr(q, "turnover_rate") and q.turnover_rate and q.turnover_rate > 0:
                    tr = q.turnover_rate
                    stock["turnover_rate"] = round(tr if tr < 1 else tr / 100 if tr > 50 else tr, 2)

        for stock in stocks:
            code = stock.get("code", "")
            turnover_rate = stock.get("turnover_rate", 0) or 0
            avg_amount = stock.get("avg_amount_yi", 0) or 0

            # If we have both metrics, apply the filter
            if turnover_rate > 0 and avg_amount > 0:
                if turnover_rate >= min_turnover and avg_amount >= min_amount:
                    survivors.append(stock)
                else:
                    logger.debug(
                        "[选股] L1: 跳过 %s (换手率=%.2f%%, 日均额=%.2f亿)",
                        code, turnover_rate, avg_amount,
                    )
            else:
                # Pass through if data unavailable — L4 scoring deprioritizes
                survivors.append(stock)

        logger.info(
            "[选股] L1: %d → %d (流动性过滤: 换手率>=%.1f%%, 日均额>=%.1f亿)",
            input_count, len(survivors), min_turnover, min_amount,
        )
        return survivors, input_count

    def _layer2_trend_filter(
        self, stocks: List[Dict], criteria: ScreenerCriteria, date: Optional[str],
        deadline: Optional[float] = None,
    ) -> Tuple[List[Dict], int]:
        input_count = len(stocks)

        codes_to_fetch = [
            s["code"] for s in stocks
            if s.get("_df") is None and s.get("code", "")
        ]
        if codes_to_fetch:
            daily_data_map = self._parallel_fetch_daily_data(codes_to_fetch, days=60, end_date=date, deadline=deadline)
            for stock in stocks:
                code = stock.get("code", "")
                df = daily_data_map.get(code)
                if df is not None:
                    stock["_df"] = df

        survivors: List[Dict] = []
        for idx, stock in enumerate(stocks):
            if deadline is not None and time.monotonic() > deadline:
                remaining = len(stocks) - idx
                logger.warning("[选股] L2: 已达 deadline，跳过剩余 %d 只股票", remaining)
                break

            df = stock.get("_df")
            ma5 = None
            ma10 = None
            ma20 = None

            if df is not None and not df.empty and len(df) >= 20:
                close = df["close"].values
                ma5 = np.mean(close[-5:])
                ma10 = np.mean(close[-10:])
                ma20 = np.mean(close[-20:])

                last_close = float(close[-1])
                if stock.get("price", 0) <= 0 and last_close > 0:
                    stock["price"] = last_close
                prev_close = float(close[-2]) if len(close) >= 2 else last_close
                if stock.get("change_pct", 0) == 0 and prev_close > 0:
                    stock["change_pct"] = round((last_close / prev_close - 1) * 100, 2)
                stock["_df"] = df

                if "turnover_rate" in df.columns:
                    tr = float(df["turnover_rate"].values[-1])
                    stock["turnover_rate"] = round(tr if tr < 100 else tr / 100, 2)

                if "amount" in df.columns:
                    amt = df["amount"].values
                    avg_amt = float(np.mean(amt[-20:])) if len(amt) >= 20 else float(amt[-1])
                    stock["avg_amount_yi"] = round(avg_amt / 1e8, 2)

            if ma5 is not None and ma10 is not None and ma20 is not None:
                is_bull = ma5 > ma10 > ma20
                is_bear = ma5 < ma10 < ma20
                if is_bull:
                    stock["ma_alignment"] = "多头排列"
                elif is_bear:
                    stock["ma_alignment"] = "空头排列"
                else:
                    stock["ma_alignment"] = "横盘震荡"
                stock["ma5"] = ma5
                stock["ma10"] = ma10
                stock["ma20"] = ma20
            else:
                stock["ma_alignment"] = "无数据"

            if criteria.require_ma_alignment:
                if stock.get("ma_alignment") == "多头排列":
                    survivors.append(stock)
                else:
                    logger.debug("[选股] L2: 跳过 %s (均线=%s)", stock["code"], stock.get("ma_alignment"))
            else:
                survivors.append(stock)

        logger.info("[选股] L2: %d → %d", input_count, len(survivors))
        return survivors, input_count

    def _enrich_turnover_rate(self, stocks: List[Dict]) -> None:
        enriched = 0
        codes = [s["code"] for s in stocks if s.get("code", "")]
        if not codes:
            return
        quotes = self._parallel_fetch_realtime_quotes(codes)
        for stock in stocks:
            code = stock.get("code", "")
            q = quotes.get(code)
            if q:
                if hasattr(q, "turnover_rate") and q.turnover_rate and q.turnover_rate > 0:
                    stock["turnover_rate"] = round(q.turnover_rate, 2)
                    enriched += 1
                if hasattr(q, "price") and q.price and q.price > 0:
                    stock["price"] = round(q.price, 2)
                if hasattr(q, "change_pct") and q.change_pct is not None:
                    stock["change_pct"] = round(q.change_pct, 2)
        if enriched:
            logger.info("[选股] 批量获取换手率: %d/%d 成功", enriched, len(stocks))

    def _layer3_intra_sector_ranking(
        self, stocks: List[Dict], date: Optional[str]
    ) -> Tuple[List[Dict], int]:
        """Rank stocks by N-day return within sector, keep top ratio."""
        input_count = len(stocks)

        # Compute N-day return for each stock
        for stock in stocks:
            df = stock.get("_df")
            if df is None or df.empty or len(df) < self.rs_lookback_days:
                stock["n_day_return"] = stock.get("change_pct", 0.0)
                continue

            close = df["close"].values
            current = close[-1]
            past = close[-self.rs_lookback_days]
            if past > 0:
                stock["n_day_return"] = (current / past - 1) * 100
            else:
                stock["n_day_return"] = 0.0

        # Sort by N-day return descending
        stocks.sort(key=lambda s: s.get("n_day_return", 0), reverse=True)

        # Keep top ratio
        keep_count = max(3, int(len(stocks) * self.top_n_ratio))
        kept = stocks[:keep_count]

        # Compute sector average return for RS calculation
        if kept:
            returns = [s.get("n_day_return", 0) for s in kept]
            avg_return = np.mean(returns) if returns else 0.0
        else:
            avg_return = 0.0

        for stock in kept:
            n_day_ret = stock.get("n_day_return", 0)
            stock["rs_ratio"] = n_day_ret / avg_return if avg_return != 0 else 1.0

        logger.info("[选股] L3: %d → %d", input_count, len(kept))
        return kept, input_count

    def _layer4_composite_scoring(
        self, stocks: List[Dict], sector_name: str = ""
    ) -> List[ScreenerCandidate]:
        """Score each surviving stock with multi-factor composite."""
        candidates: List[ScreenerCandidate] = []

        for stock in stocks:
            df = stock.get("_df")

            trend_strength = self._compute_trend_strength(df) if df is not None else 50.0
            rs_score = self._normalize_rs(stock.get("rs_ratio", 1.0))
            volume_confirmation = self._compute_volume_confirmation(df) if df is not None else 50.0
            bias_from_ma5 = self._compute_bias_score(
                stock.get("price", 0), stock.get("ma5", 0)
            )
            pre_close = stock.get("price", 0) / (1 + stock.get("change_pct", 0) / 100) if stock.get("change_pct", 0) > -99 else stock.get("price", 0)
            limit_up_ratio = self._get_limit_up_ratio(stock.get("code", ""), stock.get("name", ""))
            limit_up_proximity = self._compute_limit_up_proximity(
                stock.get("price", 0), pre_close, limit_up_ratio
            )
            sector_leadership = self._compute_sector_leadership(stock)

            factors = FactorBreakdown(
                trend_strength=round(trend_strength, 1),
                rs_score=round(rs_score, 1),
                volume_confirmation=round(volume_confirmation, 1),
                bias_from_ma5=round(bias_from_ma5, 1),
                limit_up_proximity=round(limit_up_proximity, 1),
                sector_leadership=round(sector_leadership, 1),
            )

            factor_scores = {
                "trend_strength": trend_strength,
                "rs_score": rs_score,
                "volume_confirmation": volume_confirmation,
                "bias_from_ma5": bias_from_ma5,
                "limit_up_proximity": limit_up_proximity,
                "sector_leadership": sector_leadership,
            }
            composite = 0.0
            weight_sum = 0.0
            for name, score in factor_scores.items():
                w = self.score_weights.get(name, 0.0)
                composite += score * w
                weight_sum += w
            if weight_sum > 0:
                composite = composite / weight_sum
            factors.composite_score = round(composite, 1)

            candidates.append(ScreenerCandidate(
                code=stock.get("code", ""),
                name=stock.get("name", ""),
                price=stock.get("price", 0),
                change_pct=stock.get("change_pct", 0),
                factors=factors,
                ma_alignment=stock.get("ma_alignment", ""),
                turnover_rate=stock.get("turnover_rate", 0),
                avg_amount_yi=stock.get("avg_amount_yi", 0),
                sector_name=sector_name,
                is_leader=stock.get("is_leader", False),
            ))

        candidates.sort(key=lambda c: c.factors.composite_score, reverse=True)
        logger.info("[选股] L4: %d 只候选股评分完成", len(candidates))

        # Enrich final candidates with turnover_rate from realtime quotes
        # also update price and change_pct for accuracy
        if candidates:
            top_stocks = [{"code": c.code, "price": c.price, "change_pct": c.change_pct,
                           "turnover_rate": c.turnover_rate}
                          for c in candidates]
            self._enrich_turnover_rate(top_stocks)
            top_stock_by_code = {s["code"]: s for s in top_stocks}
            for c in candidates:
                s = top_stock_by_code.get(c.code)
                if s:
                    if s.get("turnover_rate", 0) > 0:
                        c.turnover_rate = s["turnover_rate"]
                    if s.get("price", 0) > 0:
                        c.price = round(s["price"], 2)
                    if s.get("change_pct") is not None and s["change_pct"] != 0:
                        c.change_pct = round(s["change_pct"], 2)

        return candidates

    # ── Static Scoring Methods ──────────────────────────────

    @staticmethod
    def _compute_trend_strength(df: pd.DataFrame) -> float:
        """0-100: alignment quality of MA5/10/20."""
        if df is None or df.empty or len(df) < 20:
            return 50.0
        close = df["close"].values
        ma5 = np.mean(close[-5:])
        ma10 = np.mean(close[-10:])
        ma20 = np.mean(close[-20:])
        if ma5 is None or ma10 is None or ma20 is None:
            return 50.0

        score = 50.0
        if ma5 > ma10:
            score += 15
        elif ma5 < ma10:
            score -= 15
        if ma10 > ma20:
            score += 15
        elif ma10 < ma20:
            score -= 15

        if len(close) >= 40:
            ma20_prev = np.mean(close[-40:-20])
            if ma20_prev > 0:
                slope = (ma20 / ma20_prev - 1) * 100
                if slope > 2:
                    score += 15
                elif slope < -2:
                    score -= 15

        current = close[-1]
        if ma20 > 0 and current > ma20:
            score += 5

        return max(0.0, min(100.0, score))

    @staticmethod
    def _compute_volume_confirmation(df: pd.DataFrame) -> float:
        """0-100: recent volume vs longer-term average."""
        if df is None or df.empty or "volume" not in df.columns or len(df) < 20:
            return 50.0
        vol = df["volume"].values
        recent = np.mean(vol[-5:])
        longer = np.mean(vol[-20:])
        if longer <= 0:
            return 50.0
        ratio = recent / longer
        if ratio > 1.3:
            return min(100.0, 70 + (ratio - 1.3) / 0.5 * 30)
        if ratio >= 1.0:
            return 50 + (ratio - 1.0) / 0.3 * 20
        if ratio >= 0.7:
            return 30 + (ratio - 0.7) / 0.3 * 20
        return max(0.0, 30 - (0.7 - ratio) / 0.5 * 30)

    @staticmethod
    def _compute_bias_score(price: float, ma5: float) -> float:
        """0-100: distance from MA5 (lower bias = better, anti-chasing)."""
        if price <= 0 or ma5 <= 0:
            return 50.0
        bias_pct = abs((price - ma5) / ma5) * 100
        if bias_pct < 3:
            return max(80.0, 100 - bias_pct / 3 * 20)
        if bias_pct < 5:
            return 60 + (5 - bias_pct) / 2 * 20
        if bias_pct < 8:
            return 40 + (8 - bias_pct) / 3 * 20
        return max(0.0, 40 - (bias_pct - 8) / 7 * 40)

    @staticmethod
    def _compute_limit_up_proximity(
        price: float, pre_close: float, limit_up_ratio: float
    ) -> float:
        """0-100: distance from limit-up price (closer = riskier = lower score)."""
        if price <= 0 or pre_close <= 0 or limit_up_ratio <= 0:
            return 50.0
        limit_up_price = pre_close * (1 + limit_up_ratio)
        distance_pct = (limit_up_price - price) / limit_up_price * 100
        if distance_pct < 5:
            return max(0.0, 30 - (5 - distance_pct) / 5 * 30)
        if distance_pct < 10:
            return 30 + (distance_pct - 5) / 5 * 30
        if distance_pct < 20:
            return 60 + (distance_pct - 10) / 10 * 20
        return min(100.0, 80 + (distance_pct - 20) / 30 * 20)

    @staticmethod
    def _get_limit_up_ratio(code: str, name: str = "") -> float:
        c = (code or "").strip().split(".")[0]
        n = (name or "").upper()
        if "ST" in n:
            return 0.05
        if c.startswith(("688", "30")):
            return 0.20
        if c.startswith(("92", "43", "81", "82", "83", "87", "88")):
            return 0.30
        # Non-A-share codes (HK/US) default to A-share normal ratio;
        # callers should override for markets with no limit-up mechanism.
        return 0.10

    @staticmethod
    def _compute_sector_leadership(sd: Dict[str, Any]) -> float:
        """Score sector leadership potential on a 0-100 scale.

        Positive change (leading) gets higher scores; negative change
        (lagging/declining) gets low scores, as the metric reflects
        板块内领涨地位 not absolute volatility.
        """
        change = sd.get("change_pct", 0.0) or 0.0
        if change >= 9.0:
            return 90.0
        elif change >= 7.0:
            return 70.0
        elif change >= 5.0:
            return 50.0
        elif change >= 3.0:
            return 30.0
        elif change >= 0:
            return 10.0
        elif change >= -3.0:
            return 5.0
        elif change >= -7.0:
            return 2.0
        else:
            return 0.0

    @staticmethod
    def _normalize_rs(rs_value: float) -> float:
        """Normalize RS ratio to 0-100. RS=1.0 → 60, RS>1.3 → >80."""
        if rs_value > 2.0:
            return 100.0
        if rs_value > 1.0:
            return min(100.0, 60 + (rs_value - 1.0) / 1.0 * 40)
        if rs_value > 0.5:
            return 30 + (rs_value - 0.5) / 0.5 * 30
        return max(0.0, 30 * rs_value / 0.5)
