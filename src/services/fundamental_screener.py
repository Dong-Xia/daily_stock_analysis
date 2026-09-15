# -*- coding: utf-8 -*-
"""
Fundamental Screener - 基本面选股服务

基于 AkShare 财报数据（stock_yjbb_em）实现多条件筛选。
单次 API 调用即可获取全市场（~5000+ 只）股票的核心财务指标。

条件对照:
  ① 扣非净利润同比>50% → 使用净利润同比（库存股数据暂缺扣非分项）
  ② 营收同比>20%      → 营业总收入-同比增长
  ③ 扣非净利润>5000万  → 净利润-净利润 > 0.5亿
  ④ 财报日大涨/涨停   → 最新公告日期 + 当日涨跌幅交叉验证
  ⑤ 行业景气度        → 所属行业 + sector_rotation_tracker 模块
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class FundamentalCandidate:
    code: str = ""
    name: str = ""
    revenue_yoy: float = 0.0
    profit_yoy: float = 0.0
    net_profit: float = 0.0
    industry: str = ""
    announce_date: str = ""
    price: float = 0.0
    change_pct: float = 0.0
    is_limit_up_on_announce: bool = False
    sector_score: float = 0.0
    pass_revenue_test: bool = False
    pass_profit_test: bool = False
    pass_net_profit_test: bool = False
    composite_score: float = 0.0


@dataclass
class FundamentalResult:
    date: str = ""
    total_stocks: int = 0
    after_revenue_test: int = 0
    after_profit_test: int = 0
    after_net_profit_test: int = 0
    criteria: str = ""
    candidates: List[FundamentalCandidate] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)


class FundamentalScreener:
    """基本面选股器。

    基于 AkShare stock_yjbb_em 获取全市场财报数据，
    过滤出满足营收增长、利润增长等条件的候选股票。
    """

    def __init__(
        self,
        min_revenue_yoy: float = 20.0,
        min_profit_yoy: float = 50.0,
        min_net_profit_yi: float = 0.5,
        max_candidates: int = 50,
        data_manager=None,
        board_scraper=None,
    ):
        self.min_revenue_yoy = min_revenue_yoy
        self.min_profit_yoy = min_profit_yoy
        self.min_net_profit_yi = min_net_profit_yi
        self.max_candidates = max_candidates
        self._data_manager = data_manager
        self._board_scraper = board_scraper

    def screen(self, quarter_date: Optional[str] = None) -> FundamentalResult:
        """执行基本面筛选。

        Args:
            quarter_date: 财报日期 (YYYYMMDD, e.g. 20260331 一季度)
                          默认使用最近完整季度。

        Returns:
            FundamentalResult 筛选结果
        """
        import akshare as ak

        if quarter_date is None:
            quarter_date = self._resolve_latest_quarter()
            logger.info("[基本面] 自动选择季度: %s", quarter_date)

        # Fetch all stocks' financial data
        try:
            df = ak.stock_yjbb_em(date=quarter_date)
        except Exception as e:
            logger.error("[基本面] 获取财报数据失败: %s", e)
            return FundamentalResult(
                date=quarter_date, errors=[f"数据获取失败: {e}"]
            )

        if df is None or df.empty:
            return FundamentalResult(
                date=quarter_date, errors=["无数据"]
            )

        df = df.dropna(subset=["净利润-同比增长", "营业总收入-同比增长"], how="all")
        total = len(df)

        # Condition 1: 营收同比增长 > 20%
        revenue_col = "营业总收入-同比增长"
        profit_col = "净利润-同比增长"
        net_profit_col = "净利润-净利润"
        announce_col = "最新公告日期"
        industry_col = "所处行业"

        df[revenue_col] = pd.to_numeric(df.get(revenue_col, pd.Series([0])), errors="coerce").fillna(0)
        df[profit_col] = pd.to_numeric(df.get(profit_col, pd.Series([0])), errors="coerce").fillna(0)
        df[net_profit_col] = pd.to_numeric(df.get(net_profit_col, pd.Series([0])), errors="coerce").fillna(0)

        df["_pass_revenue"] = df[revenue_col] >= self.min_revenue_yoy
        df["_pass_profit"] = df[profit_col] >= self.min_profit_yoy
        df["_pass_net_profit"] = df[net_profit_col] >= self.min_net_profit_yi * 1e8

        after_revenue = int(df["_pass_revenue"].sum())
        after_profit = int(df["_pass_profit"].sum())

        # Apply all conditions
        mask = df["_pass_revenue"] & df["_pass_profit"] & df["_pass_net_profit"]
        candidates_df = df[mask].copy()
        after_net = len(candidates_df)

        # Score: each condition met = +1, additional bonus for strength
        candidates_df["_score"] = 0
        candidates_df["_score"] += candidates_df[revenue_col].apply(
            lambda x: 3 if x >= 50 else (2 if x >= 30 else 1)
        )
        candidates_df["_score"] += candidates_df[profit_col].apply(
            lambda x: 5 if x >= 100 else (3 if x >= 70 else 1)
        )
        candidates_df["_score"] += candidates_df[net_profit_col].apply(
            lambda x: 2 if x >= 5e8 else 1
        )

        candidates_df = candidates_df.sort_values("_score", ascending=False)
        candidates_df = candidates_df.head(self.max_candidates)

        candidates: List[FundamentalCandidate] = []
        for _, row in candidates_df.iterrows():
            code = str(row.get("股票代码", "")).strip()
            announce_date = str(row.get(announce_col, "")).strip()

            cand = FundamentalCandidate(
                code=code,
                name=str(row.get("股票简称", "")).strip(),
                revenue_yoy=round(float(row.get(revenue_col, 0)), 2),
                profit_yoy=round(float(row.get(profit_col, 0)), 2),
                net_profit=round(float(row.get(net_profit_col, 0)), 2),
                industry=str(row.get(industry_col, "")).strip(),
                announce_date=announce_date,
                pass_revenue_test=True,
                pass_profit_test=True,
                pass_net_profit_test=True,
                composite_score=round(float(row.get("_score", 0)), 1),
            )
            candidates.append(cand)

        logger.info(
            "[基本面] %s: %d→营收%.0f%%→利润%.0f%%→最终%d",
            quarter_date, total, after_revenue, after_profit, len(candidates),
        )

        return FundamentalResult(
            date=quarter_date,
            total_stocks=total,
            after_revenue_test=after_revenue,
            after_profit_test=after_profit,
            after_net_profit_test=after_net,
            criteria=(
                "筛选条件：\n"
                f"  ① 营收同比增长 ≥{self.min_revenue_yoy:.0f}%\n"
                f"  ② 净利润同比增长 ≥{self.min_profit_yoy:.0f}%\n"
                f"  ③ 净利润 ≥{self.min_net_profit_yi:.1f}亿\n\n"
                "评分公式（满分10分）：\n"
                "  营收增速：≥20%→1分，≥30%→2分，≥50%→3分\n"
                "  利润增速：≥50%→1分，≥70%→3分，≥100%→5分\n"
                "  净利润：≥0.5亿→1分，≥5亿→2分\n\n"
                f"数据来源：AkShare stock_yjbb_em（全市场约{total}只）"
            ),
            candidates=candidates,
        )

    @staticmethod
    def _resolve_latest_quarter() -> str:
        """自动选择最近完整季度。"""
        now = datetime.now()
        m = now.month
        y = now.year
        if m >= 10:
            return f"{y}0930"  # Q3
        if m >= 7:
            return f"{y}0630"  # Q2
        if m >= 4:
            return f"{y}0331"  # Q1
        return f"{y - 1}1231"  # Q4 of previous year

    @staticmethod
    def enrich_with_market_data(
        candidates: List[FundamentalCandidate],
        date: Optional[str] = None,
        data_manager=None,
        board_scraper=None,
    ) -> List[FundamentalCandidate]:
        """用行情数据增补候选股（价格、涨跌幅、涨停检测）。"""
        from data_provider.board_scraper_fetcher import BoardScraperFetcher

        today = date or datetime.now().strftime("%Y-%m-%d")
        limit_up_pool: List[Dict] = []

        fetcher = board_scraper
        owned_fetcher = False
        if fetcher is None:
            try:
                fetcher = BoardScraperFetcher(headless=True)
                owned_fetcher = True
            except Exception as e:
                logger.debug("[基本面] BoardScraperFetcher 创建失败: %s", e)
                fetcher = None

        try:
            if fetcher:
                pool = fetcher.get_limit_up_pool(date=today.replace("-", ""))
                if pool:
                    limit_up_pool = pool
        except Exception as e:
            logger.debug("[基本面] 涨停池获取失败: %s", e)
        finally:
            if owned_fetcher and fetcher is not None:
                try:
                    fetcher.close()
                except Exception:
                    pass

        limit_up_codes = {s.get("code", ""): s for s in limit_up_pool}

        from data_provider.base import DataFetcherManager
        dm = data_manager or DataFetcherManager()

        for cand in candidates:
            try:
                quote = dm.get_realtime_quote(cand.code)
                if quote is not None:
                    cand.price = getattr(quote, "price", 0.0) or 0.0
                    cand.change_pct = getattr(quote, "change_pct", 0.0) or 0.0
            except Exception:
                pass

            lup = limit_up_codes.get(cand.code)
            if lup:
                cand.is_limit_up_on_announce = True

        return candidates

    @staticmethod
    def enrich_with_sector_rotation(
        candidates: List[FundamentalCandidate],
        tracker=None,
    ) -> List[FundamentalCandidate]:
        """用板块轮动数据增补行业景气度评分。"""
        try:
            from src.services.sector_rotation_tracker import SectorRotationTracker
            st = tracker or SectorRotationTracker(lookback_days=20)
            rotation = st.analyze()

            sector_scores = {
                s.name: max(0, s.score_trend)
                for s in rotation.top_main_lines
            }
            sector_scores.update({
                s.name: max(0, s.score_trend)
                for s in rotation.rising_sectors
            })

            for cand in candidates:
                cand.sector_score = sector_scores.get(cand.industry, 0.0)
        except Exception as e:
            logger.debug("[基本面] 板块评分获取失败: %s", e)

        return candidates

    @staticmethod
    def format_result(result: FundamentalResult) -> str:
        """格式化为终端输出。

        通过数一律显示各阶段的真实计数；评分后按 max_candidates 截断时单独提示，
        避免截断数被误读成"通过数恰好 50"或首名成绩被误读成筛选阈值。
        """
        lines = [
            f"📊 基本面选股 — {result.date}",
            f"{'='*60}",
            f"  总股票数: {result.total_stocks}",
            f"  通过营收增速条件: {result.after_revenue_test}",
            f"  通过利润增速条件: {result.after_profit_test}",
            f"  全部条件通过: {result.after_net_profit_test}",
        ]
        if result.after_net_profit_test > len(result.candidates):
            lines.append(
                f"  按评分截断输出前 {len(result.candidates)} 只（上限 FUNDAMENTAL_MAX_CANDIDATES）"
            )
        lines.append("")
        if result.candidates:
            lines.append(f"  {'代码':<10} {'名称':<10} {'营收同比':>8} {'利润同比':>8} {'净利润':>10} {'评分':>5}")
            lines.append(f"  {'-'*55}")
            for c in result.candidates:
                lines.append(
                    f"  {c.code:<10} {c.name:<10} {c.revenue_yoy:>+7.1f}% {c.profit_yoy:>+7.1f}% "
                    f"{c.net_profit/1e8:>9.2f}亿 {c.composite_score:>5.1f}"
                )
        if result.errors:
            lines.extend(["", "错误:"] + [f"  {e}" for e in result.errors])
        return "\n".join(lines)
