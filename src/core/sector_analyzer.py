# -*- coding: utf-8 -*-
"""
热点板块分析核心模块 — "今天谁在涨"的探测器

热点板块负责每日板块排行榜检测，是板块轮动分析的输入上游。
输出供 SectorRotationTracker（板块锁定/轮动）进行多日持续性过滤。

职责：
1. 获取板块涨幅榜并筛选候选热点板块
2. 获取板块内成分股并统计涨停、连板梯队
3. 识别龙头股并计算带动效应
4. 综合打分排序输出热点板块列表
"""

import logging
import time
from concurrent.futures import ThreadPoolExecutor, wait
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from data_provider.base import DataFetcherManager, normalize_stock_code
from src.config import get_config

logger = logging.getLogger(__name__)

LIMIT_UP_RATIOS = {
    "st": 0.05,
    "kc_cy": 0.20,
    "bse": 0.30,
    "normal": 0.10,
}

# 题材级别关键词映射（用于 _calc_topic_level）
# 国家级 > 行业级 > 个股消息 — 陈小群题材级别判断框架
TOPIC_LEVEL_KEYWORDS: Dict[str, Tuple[str, int, List[str]]] = {
    "国家级": ("国家级", 15, [
        "新能源", "光伏", "风电", "储能", "氢能", "核能", "锂电",
        "新能源汽车", "智能汽车", "自动驾驶",
        "芯片", "半导体", "集成电路", "光刻",
        "人工智能", "AI", "机器人", "人形机器人", "大模型", "算力", "CPO",
        "军工", "航母", "大飞机", "卫星", "航天", "航空发动机", "无人机",
        "碳中和", "碳交易", "绿色电力", "环保",
        "国企改革", "中特估", "中字头",
        "一带一路", "跨境电商",
        "数字经济", "数据要素", "信创", "国产替代", "自主可控",
        "新质生产力", "低空经济", "量子",
    ]),
    "行业级": ("行业级", 10, [
        "涨价", "供需", "库存", "景气", "周期",
        "消费", "白酒", "食品", "饮料", "免税",
        "医药", "医疗", "创新药", "CXO", "中药", "医美", "医疗器械",
        "地产", "基建", "建材", "装修", "家居",
        "汽车", "整车", "零部件", "汽配",
        "有色", "钢铁", "煤炭", "化工", "石油", "黄金",
        "金融", "证券", "保险", "银行", "多元金融",
        "通信", "5G", "6G", "光通信",
        "游戏", "传媒", "影视", "元宇宙",
        "教育", "旅游", "酒店", "航空", "物流",
        "养殖", "猪肉", "农业", "种业",
        "电子", "消费电子", "面板",
    ]),
}


def _calc_topic_level(sector_name: str) -> Tuple[str, int]:
    """判断题材级别：国家级 > 行业级 > 个股消息

    基于陈小群的方法论：题材级别决定了行情的高度和持续性。
    国家级题材可以走数月，行业级题材走数周，个股消息往往一日游。

    Returns:
        (级别中文名, 得分)
    """
    name = sector_name.lower()
    for level_name, (label, score, keywords) in TOPIC_LEVEL_KEYWORDS.items():
        for kw in keywords:
            if kw.lower() in name:
                return label, score
    return "个股消息", 5


def _classify_sector_lifecycle(
    ladder: List["LimitUpLadder"],
    limit_up_count: int,
    leader_correlation: float,
) -> str:
    """判断题材所处的生命周期阶段（基于日内数据）

    92科比四阶段框架映射：
    - 低位试错：龙头未明、连板高度低、散乱
    - 主升期：龙头清晰、连板≥5、板块批量涨停
    - 高位震荡：龙头高位分歧、跟风掉队
    - 主跌期：龙头大跌、无连板梯队

    Returns:
        生命周期中文名
    """
    if not ladder:
        return "未知"

    max_days = ladder[0].days if ladder else 0

    if max_days >= 5 and limit_up_count >= 5 and leader_correlation > 0.3:
        return "主升期"
    if max_days >= 3 and limit_up_count >= 8:
        return "主升期"
    if max_days >= 3:
        return "强势轮动"
    if max_days >= 1 and limit_up_count >= 3:
        return "低位试错"
    if leader_correlation < 0.2 or limit_up_count < 3:
        return "脉冲"
    return "轮动"


def _get_limit_up_ratio(code: str, name: str = "") -> float:
    c = (code or "").strip().split(".")[0]
    n = (name or "").upper()
    if "ST" in n:
        return LIMIT_UP_RATIOS["st"]
    if c.startswith(("688", "30")):
        return LIMIT_UP_RATIOS["kc_cy"]
    if c.startswith(("92", "43", "81", "82", "83", "87", "88")):
        return LIMIT_UP_RATIOS["bse"]
    return LIMIT_UP_RATIOS["normal"]


@dataclass
class SectorStock:
    code: str
    name: str
    change_pct: float = 0.0
    price: float = 0.0
    is_limit_up: bool = False
    consecutive_limit_up_days: int = 0


@dataclass
class LimitUpLadder:
    days: int
    stock_code: str
    stock_name: str


@dataclass
class HotSector:
    name: str
    change_pct: float = 0.0
    limit_up_count: int = 0
    limit_up_stocks: List[SectorStock] = field(default_factory=list)
    ladder: List[LimitUpLadder] = field(default_factory=list)
    leader: Optional[SectorStock] = None
    leader_correlation: float = 0.0
    score: float = 0.0
    # 新增方法论增强字段
    topic_level: str = "未知"          # 题材级别：国家级/行业级/个股消息
    topic_level_score: int = 0         # 题材级别得分
    lifecycle: str = "未知"            # 生命周期：低位试错/主升期/强势轮动/脉冲
    sentiment_multiplier: float = 1.0  # 情绪乘数 0.7-1.3
    index_resonance: float = 0.0       # 指数共振得分 0-15

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "change_pct": self.change_pct,
            "limit_up_count": self.limit_up_count,
            "limit_up_stocks": [
                {
                    "code": s.code,
                    "name": s.name,
                    "change_pct": s.change_pct,
                    "price": s.price,
                    "is_limit_up": s.is_limit_up,
                    "consecutive_limit_up_days": s.consecutive_limit_up_days,
                }
                for s in self.limit_up_stocks
            ],
            "ladder": [
                {
                    "days": r.days,
                    "stock_code": r.stock_code,
                    "stock_name": r.stock_name,
                }
                for r in self.ladder
            ],
            "leader": {
                "code": self.leader.code,
                "name": self.leader.name,
                "change_pct": self.leader.change_pct,
                "price": self.leader.price,
                "is_limit_up": self.leader.is_limit_up,
                "consecutive_limit_up_days": self.leader.consecutive_limit_up_days,
            } if self.leader else None,
            "leader_correlation": self.leader_correlation,
            "score": self.score,
            "topic_level": self.topic_level,
            "topic_level_score": self.topic_level_score,
            "lifecycle": self.lifecycle,
            "sentiment_multiplier": self.sentiment_multiplier,
            "index_resonance": self.index_resonance,
        }


class SectorAnalyzer:
    def __init__(self, data_manager: Optional[DataFetcherManager] = None):
        self.config = get_config()
        self.data_manager = data_manager or DataFetcherManager()

    def analyze(
        self,
        top_n: int = 20,
        min_limit_up: int = 3,
        date: Optional[str] = None,
        allow_realtime_fetch: bool = True,
        scraper_limit_up_pool: Optional[List[Dict[str, Any]]] = None,
        scraper_sector_rankings: Optional[Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]] = None,
        timeout_budget: float = 120.0,
    ) -> List[HotSector]:
        target_date = date or datetime.now().strftime("%Y-%m-%d")
        logger.info(f"[热点板块分析] 开始分析，日期={target_date}")

        # 爬虫涨停池 → {归一化代码: 连板数}，供梯队计算直接复用（免去逐股拉K线）
        limit_up_days_lookup: Optional[Dict[str, int]] = None
        if scraper_limit_up_pool:
            lookup: Dict[str, int] = {}
            for s in scraper_limit_up_pool:
                code = normalize_stock_code(str(s.get("code", "")))
                try:
                    days = int(s.get("consecutive_days", 0) or 0)
                except (TypeError, ValueError):
                    days = 0
                if code and days > 0:
                    lookup[code] = days
            limit_up_days_lookup = lookup or None
            if limit_up_days_lookup:
                logger.info(f"[热点板块分析] 使用爬虫涨停池连板数 ({len(limit_up_days_lookup)} 只)")

        if scraper_sector_rankings and scraper_sector_rankings[0]:
            top_sectors = scraper_sector_rankings[0]
            logger.info(f"[热点板块分析] 使用爬虫板块数据 ({len(top_sectors)} 个)")
        else:
            rankings = self.data_manager.get_sector_rankings(top_n)
            if not rankings or not rankings[0]:
                logger.warning("[热点板块分析] 未获取到板块涨幅榜")
                return []
            top_sectors = rankings[0]

        # 构建全市场情绪上下文（只算一次，所有板块共享）
        market_context = self._build_market_context()

        # 计算前排平均涨幅，用于指数共振评分
        avg_change = (
            sum(float(s.get("change_pct", 0.0)) for s in top_sectors[:10])
            / max(len([s for s in top_sectors[:10] if s.get("change_pct")]), 1)
        )

        hot_sectors: List[HotSector] = []
        deadline = time.monotonic() + timeout_budget if timeout_budget and timeout_budget > 0 else None

        for sector_info in top_sectors:
            if deadline and time.monotonic() > deadline:
                logger.warning(
                    f"[热点板块分析] 超出时间预算 {timeout_budget:.0f}s，"
                    f"已分析完即止，返回 {len(hot_sectors)} 个板块的部分结果"
                )
                break
            sector_name = sector_info.get("name", "")
            change_pct = float(sector_info.get("change_pct", 0.0))
            if not sector_name:
                continue

            hot = self._analyze_sector(
                sector_name, change_pct, target_date,
                allow_realtime_fetch=allow_realtime_fetch,
                market_context=market_context,
                avg_top_sector_change=avg_change,
                limit_up_days_lookup=limit_up_days_lookup,
            )
            if hot and hot.limit_up_count >= min_limit_up:
                hot_sectors.append(hot)

        hot_sectors.sort(key=lambda x: x.score, reverse=True)

        logger.info(f"[热点板块分析] 完成，共 {len(hot_sectors)} 个热点板块 (情绪乘数={market_context.get('sentiment_multiplier', 1.0):.2f})")
        return hot_sectors

    def _parallel_get_daily_data(
        self,
        codes: List[str],
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        timeout: float = 60.0,
    ) -> Dict[str, Optional[pd.DataFrame]]:
        """批量并行拉取日线，返回 {code: DataFrame|None}。

        仿 StockScreenerService._parallel_fetch_daily_data 的既有范式：
        ThreadPoolExecutor + 周期性 recheck deadline + finally shutdown(wait=False)。
        单只失败记 None，不抛出（调用方按缺失处理）。
        """
        results: Dict[str, Optional[pd.DataFrame]] = {}
        unique_codes = [c for c in dict.fromkeys(codes) if c]
        if not unique_codes:
            return results
        deadline = time.monotonic() + timeout
        with ThreadPoolExecutor(max_workers=min(5, len(unique_codes))) as executor:
            futures = {
                executor.submit(
                    self.data_manager.get_daily_data,
                    code, start_date=start_date, end_date=end_date,
                ): code
                for code in unique_codes
            }
            pending = set(futures)
            while pending:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    logger.warning(f"[并行取数] 超时，{len(pending)} 只未完成")
                    break
                done, pending = wait(pending, timeout=min(5.0, remaining))
                for future in done:
                    code = futures[future]
                    try:
                        df, _ = future.result(timeout=1)
                        results[code] = df
                    except Exception:
                        results[code] = None
            for future in pending:
                future.cancel()
        return results

    def _analyze_sector(
        self,
        name: str,
        change_pct: float,
        date: str,
        allow_realtime_fetch: bool = True,
        market_context: Optional[Dict[str, Any]] = None,
        avg_top_sector_change: float = 0.0,
        limit_up_days_lookup: Optional[Dict[str, int]] = None,
    ) -> Optional[HotSector]:
        logger.debug(f"[板块分析] {name} ({change_pct:+.2f}%)")

        members = None
        try:
            from src.services.sector_cache_service import get_sector_cache
            cache = get_sector_cache()
            members = cache.get_board_members(name, "industry")
            if members is None:
                members = cache.get_board_members(name, "concept")
            if members is not None:
                logger.debug(f"[板块分析] {name} 使用缓存 ({len(members)} 只)")
        except Exception:
            pass

        if members is None and allow_realtime_fetch:
            members = self.data_manager.get_board_members(name, board_type="industry")
            if not members:
                members = self.data_manager.get_board_members(name, board_type="concept")

        if not members:
            return None

        stocks: List[SectorStock] = []
        for m in members:
            code = normalize_stock_code(str(m.get("code", "")))
            stock = SectorStock(
                code=code,
                name=str(m.get("name", "")),
                change_pct=float(m.get("change_pct", 0.0) or 0.0),
                price=float(m.get("price", 0.0) or 0.0),
            )
            pre_close = stock.price / (1 + stock.change_pct / 100) if stock.change_pct != 0 else stock.price
            ratio = _get_limit_up_ratio(code, stock.name)
            limit_up_price = np.floor(pre_close * (1 + ratio) * 100 + 0.5) / 100.0
            tolerance = round(abs(pre_close * (1 + ratio) - limit_up_price), 10)
            stock.is_limit_up = stock.price > 0 and abs(stock.price - limit_up_price) <= tolerance
            stocks.append(stock)

        limit_up_stocks = [s for s in stocks if s.is_limit_up]
        if not limit_up_stocks:
            return None

        ladder = self._calc_limit_up_ladder(limit_up_stocks, date, days_lookup=limit_up_days_lookup)
        for stock in stocks:
            for rung in ladder:
                if rung.stock_code == stock.code:
                    stock.consecutive_limit_up_days = rung.days
                    break

        leader = self._identify_leader(limit_up_stocks, ladder)
        correlation = 0.0
        if leader:
            correlation = self._calc_leader_correlation(leader, stocks)

        # --- 方法论增强评分 ---
        # 基础分（原有四维度）
        base_score = self._calc_score(
            sector_change=change_pct,
            limit_up_count=len(limit_up_stocks),
            ladder_completeness=len(set(rung.days for rung in ladder)),
            leader_correlation=correlation,
        )

        # 情绪乘数：北京炒家"大势判断" + 涅盘重升"水温判断"
        sentiment_mult = (market_context or {}).get("sentiment_multiplier", 1.0)

        # 题材级别：陈小群"题材级别判断"框架
        topic_level, topic_level_score = _calc_topic_level(name)

        # 指数共振：北京炒家"强于指数"
        resonance = 0.0
        if avg_top_sector_change > 0:
            outperf = change_pct - avg_top_sector_change
            if outperf > 3.0:
                resonance = 15.0
            elif outperf > 2.0:
                resonance = 12.0
            elif outperf > 1.0:
                resonance = 8.0
            elif outperf > 0.5:
                resonance = 5.0
            elif outperf > 0:
                resonance = 3.0

        # 生命周期：92科比四阶段框架
        lifecycle = _classify_sector_lifecycle(
            ladder, len(limit_up_stocks), correlation
        )

        # 综合分 = 基础分 × 情绪乘数 + 题材级别加分 + 指数共振加分
        final_score = round(base_score * sentiment_mult + topic_level_score + resonance, 2)

        return HotSector(
            name=name,
            change_pct=change_pct,
            limit_up_count=len(limit_up_stocks),
            limit_up_stocks=limit_up_stocks,
            ladder=ladder,
            leader=leader,
            leader_correlation=correlation,
            score=final_score,
            topic_level=topic_level,
            topic_level_score=topic_level_score,
            lifecycle=lifecycle,
            sentiment_multiplier=round(sentiment_mult, 2),
            index_resonance=round(resonance, 1),
        )

    def _calc_limit_up_ladder(
        self,
        limit_up_stocks: List[SectorStock],
        date: str,
        days_lookup: Optional[Dict[str, int]] = None,
    ) -> List[LimitUpLadder]:
        ladder: List[LimitUpLadder] = []

        # 有爬虫涨停池时直接复用其连板数（全量覆盖），跳过逐股拉K线的老方案
        if days_lookup:
            ladder = [
                LimitUpLadder(days=days_lookup[s.code], stock_code=s.code, stock_name=s.name)
                for s in limit_up_stocks
                if days_lookup.get(s.code)
            ]
            if ladder:
                ladder.sort(key=lambda x: x.days, reverse=True)
                return ladder

        end_date = date
        start_dt = datetime.strptime(date, "%Y-%m-%d") - timedelta(days=30)
        start_date = start_dt.strftime("%Y-%m-%d")

        df_map = self._parallel_get_daily_data(
            [s.code for s in limit_up_stocks[:5]], start_date=start_date, end_date=end_date
        )
        for stock in limit_up_stocks[:5]:
            try:
                df = df_map.get(stock.code)
                if df is None or df.empty:
                    continue
                df = df.sort_values("date", ascending=False).reset_index(drop=True)
                consecutive = 0
                for _, row in df.iterrows():
                    pre_close = row["close"] / (1 + row["pct_chg"] / 100) if row["pct_chg"] != 0 else row["close"]
                    ratio = _get_limit_up_ratio(stock.code, stock.name)
                    limit_up_price = np.floor(pre_close * (1 + ratio) * 100 + 0.5) / 100.0
                    tolerance = round(abs(pre_close * (1 + ratio) - limit_up_price), 10)
                    if abs(row["close"] - limit_up_price) <= tolerance:
                        consecutive += 1
                    else:
                        break
                if consecutive > 0:
                    ladder.append(LimitUpLadder(days=consecutive, stock_code=stock.code, stock_name=stock.name))
            except Exception as e:
                logger.debug(f"[连板计算] {stock.code} 失败: {e}")
                continue
        ladder.sort(key=lambda x: x.days, reverse=True)
        return ladder

    def _identify_leader(
        self, limit_up_stocks: List[SectorStock], ladder: List[LimitUpLadder]
    ) -> Optional[SectorStock]:
        if not ladder:
            return None

        # 为每只涨停股计算筹码质量评分（批量并行预取90日K线，避免逐股串行网络调用）
        chip_scores: Dict[str, int] = {}
        chip_candidates = limit_up_stocks[:10]
        chip_end = datetime.now().strftime("%Y-%m-%d")
        chip_start = (datetime.now() - timedelta(days=90)).strftime("%Y-%m-%d")
        chip_df_map = self._parallel_get_daily_data(
            [s.code for s in chip_candidates], start_date=chip_start, end_date=chip_end
        )
        for stock in chip_candidates:
            score, _ = self._score_chip_quality(stock.code, df=chip_df_map.get(stock.code))
            chip_scores[stock.code] = score

        # 筛掉筹码太差的（<30分），优先选连板高+筹码好的
        def _leader_rank(entry: LimitUpLadder) -> float:
            cs = chip_scores.get(entry.stock_code, 0)
            return entry.days * 0.5 + cs * 0.5 / 100.0 * 10.0

        ranked = sorted(ladder, key=_leader_rank, reverse=True)
        if not ranked:
            return None
        best = ranked[0]
        best_chip = chip_scores.get(best.stock_code, 0)

        # 如果最优候选筹码极差（<20分），降级选第二候选
        if best_chip < 20 and len(ranked) > 1:
            second = ranked[1]
            second_chip = chip_scores.get(second.stock_code, 0)
            if second_chip > best_chip + 10:
                best = second

        leader_code = best.stock_code
        for stock in limit_up_stocks:
            if stock.code == leader_code:
                return stock
        return None

    def _calc_leader_correlation(self, leader: SectorStock, stocks: List[SectorStock]) -> float:
        if len(stocks) < 3:
            return 0.0
        try:
            end_date = datetime.now().strftime("%Y-%m-%d")
            start_dt = datetime.strptime(end_date, "%Y-%m-%d") - timedelta(days=14)
            start_date = start_dt.strftime("%Y-%m-%d")

            # 批量并行预取（龙头 + 前7只成分股），替代逐股串行网络调用
            corr_codes = [leader.code] + [s.code for s in stocks[:8] if s.code != leader.code]
            df_map = self._parallel_get_daily_data(corr_codes, start_date=start_date, end_date=end_date)
            leader_df = df_map.get(leader.code)
            if leader_df is None or len(leader_df) < 5:
                return 0.0
            leader_series = leader_df.set_index("date")["pct_chg"].dropna()

            correlations: List[float] = []
            for stock in stocks[:8]:
                if stock.code == leader.code:
                    continue
                try:
                    df = df_map.get(stock.code)
                    if df is None or len(df) < 5:
                        continue
                    stock_series = df.set_index("date")["pct_chg"].dropna()
                    # 按日期对齐，只取两者共有的交易日
                    common_dates = leader_series.index.intersection(stock_series.index)
                    if len(common_dates) < 5:
                        continue
                    x = leader_series[common_dates].values
                    y = stock_series[common_dates].values
                    # 斯皮尔曼秩相关：抗涨停/跌停留群值
                    from scipy.stats import spearmanr
                    corr, _ = spearmanr(x, y)
                    if not np.isnan(corr):
                        correlations.append(corr)
                except Exception:
                    continue
            if not correlations:
                return 0.0
            return float(np.mean(correlations))
        except Exception as e:
            logger.debug(f"[带动效应] 计算失败: {e}")
            return 0.0

    def _build_market_context(self) -> Dict[str, Any]:
        """构建全市场情绪上下文

        基于北京炒家"大势判断"和涅盘重升"水温判断"理念：
          - 涨停家数多 → 情绪热 → 评分乘数放大
          - 涨停家数少 → 情绪冷 → 评分乘数收缩

        返回 dict 包含 sentiment_multiplier (0.7~1.3)
        """
        context: Dict[str, Any] = {"sentiment_multiplier": 1.0}
        try:
            akshare = self._get_akshare_fetcher()
            if akshare:
                profit = akshare.get_market_profit_effect()
                if profit:
                    limit_up = int(profit.get("limit_up_count", 0) or 0)
                    if limit_up >= 80:
                        context["sentiment_multiplier"] = 1.30
                    elif limit_up >= 50:
                        context["sentiment_multiplier"] = 1.15
                    elif limit_up >= 30:
                        context["sentiment_multiplier"] = 1.00
                    elif limit_up >= 15:
                        context["sentiment_multiplier"] = 0.85
                    else:
                        context["sentiment_multiplier"] = 0.70
        except Exception:
            pass
        return context

    @staticmethod
    def _calc_score(
        sector_change: float,
        limit_up_count: int,
        ladder_completeness: int,
        leader_correlation: float,
    ) -> float:
        score = 0.0
        score += max(0, sector_change) * 2.0
        score += limit_up_count * 5.0
        score += ladder_completeness * 8.0
        score += max(0, leader_correlation) * 15.0
        return round(score, 2)

    def _score_chip_quality(self, code: str, df: Optional[pd.DataFrame] = None) -> Tuple[int, Dict[str, Any]]:
        """筹码结构质量评分 0-100（基于可用日线数据的代理指标）。

        四个维度：
          - 浮筹清洗度 (30分)：近期缩量+窄幅震荡 → 筹码干净
          - 稳定性 (25分)：近期波动率低 → 持股信心强
          - 爆炒风险 (25分)：近60日涨幅小 → 无套牢盘
          - 趋势结构 (20分)：均线多头排列 → 筹码锁定好

        Args:
            df: 预取的90日日线（批量并行场景传入）；为 None 时内部单股拉取

        返回 (score, details_dict)
        """
        details: Dict[str, Any] = {"valid": False, "score": 0, "factors": {}}
        try:
            if df is None:
                end_date = datetime.now().strftime("%Y-%m-%d")
                start_date = (datetime.now() - timedelta(days=90)).strftime("%Y-%m-%d")
                df, _ = self.data_manager.get_daily_data(code, start_date=start_date, end_date=end_date)
            if df is None or len(df) < 10:
                return 0, details
            df = df.sort_values("date").reset_index(drop=True)
            details["valid"] = True

            recent = df.tail(20)
            mid = df.tail(60)

            # --- 浮筹清洗度 (30分) ---
            vol_decline = 0.0
            volume_clean = 15
            if len(recent) >= 10:
                first_half_vol = recent.head(len(recent) // 2)["volume"].mean()
                second_half_vol = recent.tail(len(recent) // 2)["volume"].mean()
                if first_half_vol > 0:
                    vol_decline = max(0, (first_half_vol - second_half_vol) / first_half_vol)
                    volume_clean = int(vol_decline * 15)

            price_range = 0.0
            range_clean = 15
            if len(recent) >= 10:
                price_range = (recent["high"].max() - recent["low"].min()) / recent["close"].iloc[-1]
                if price_range < 0.10:
                    range_clean = 15
                elif price_range < 0.20:
                    range_clean = 10
                elif price_range < 0.30:
                    range_clean = 5
                else:
                    range_clean = 0

            float_clean_score = volume_clean + range_clean
            details["factors"]["float_clean"] = {"score": float_clean_score, "max": 30,
                "vol_decline": f"{vol_decline*100:.0f}%", "price_range": f"{price_range*100:.0f}%"}

            # --- 稳定性 (25分) ---
            volatility = 0.0
            stability = 15
            if len(recent) >= 10:
                recent_pct = recent["pct_chg"].dropna()
                if len(recent_pct) >= 5:
                    volatility = float(np.std(recent_pct))
                    if volatility < 2.0:
                        stability = 15
                    elif volatility < 3.5:
                        stability = 12
                    elif volatility < 5.0:
                        stability = 8
                    else:
                        stability = 4
            trend_stability = 10
            if len(recent) >= 5:
                close_vals = recent["close"].values
                above_ma = sum(1 for i in range(len(close_vals)) if
                    np.mean(close_vals[max(0, i - 4):i + 1]) < close_vals[i])
                trend_stability = int(above_ma / len(close_vals) * 10)

            stability_score = stability + trend_stability
            details["factors"]["stability"] = {"score": stability_score, "max": 25,
                "volatility": f"{volatility:.1f}%"}

            # --- 爆炒风险 (25分) ---
            peak_gain = 0.0
            hype_risk = 25
            if len(mid) >= 20:
                peak_gain = float((mid["high"].max() - mid["low"].min()) / mid["low"].min() * 100)
                if peak_gain > 80:
                    hype_risk = 5
                elif peak_gain > 50:
                    hype_risk = 10
                elif peak_gain > 30:
                    hype_risk = 18
                else:
                    hype_risk = 25
            details["factors"]["hype_risk"] = {"score": hype_risk, "max": 25,
                "peak_gain": f"{peak_gain:.0f}%"}

            # --- 趋势结构 (20分) ---
            trend_score = 10
            if len(df) >= 20:
                try:
                    ma5 = df["close"].rolling(5).mean().iloc[-1]
                    ma10 = df["close"].rolling(10).mean().iloc[-1]
                    ma20 = df["close"].rolling(20).mean().iloc[-1]
                    close = df["close"].iloc[-1]
                    if close > ma5 > ma10 > ma20:
                        trend_score = 20
                    elif close > ma5 and ma5 > ma10:
                        trend_score = 15
                    elif close > ma20:
                        trend_score = 10
                    else:
                        trend_score = 5
                except Exception:
                    pass
            details["factors"]["trend"] = {"score": trend_score, "max": 20}

            total = float_clean_score + stability_score + hype_risk + trend_score
            details["score"] = total
            return max(0, min(100, total)), details
        except Exception as e:
            logger.debug(f"[筹码评分] {code} 计算失败: {e}")
            return 0, details

    # ================================================================
    #  增强：概念板块 + 资金流 + 人气榜 + 涨停板池 综合分析
    # ================================================================

    def fetch_hotspot_data(self) -> Dict[str, Any]:
        """获取完整热点分析原始数据（概念/行业排行、资金流、人气榜、涨停板池、北向资金）

        策略：
        1. 优先用 AkshareFetcher（功能最全）
        2. 若 AkshareFetcher 不可用或全维度失败，回退到 EmHiddenApiFetcher（浏览器模拟直连）
        """
        data: Dict[str, Any] = {
            "timestamp": datetime.now().isoformat(),
        }

        akshare = self._get_akshare_fetcher()
        if akshare is not None:
            data["concept_rankings"] = self._safe_fetch(
                lambda: akshare.get_concept_board_rankings(20), "概念板块排行"
            )
            data["hot_stocks"] = self._safe_fetch(
                lambda: akshare.get_hot_rankings(30), "人气榜"
            )
            data["limit_up_pool"] = self._safe_fetch(
                lambda: akshare.get_limit_up_pool(), "涨停板池"
            )
            data["concept_fund_flow"] = self._safe_fetch(
                lambda: akshare.get_concept_fund_flow_rank("今日"), "概念资金流"
            )
            data["industry_fund_flow"] = self._safe_fetch(
                lambda: akshare.get_industry_fund_flow_rank("今日"), "行业资金流"
            )
            data["north_flow"] = self._safe_fetch(
                lambda: akshare.get_north_flow(), "北向资金"
            )
            data["profit_effect"] = self._safe_fetch(
                lambda: akshare.get_market_profit_effect(), "赚钱效应"
            )

        fetched_count = sum(1 for v in data.values() if v is not None)
        if fetched_count == 0:
            logger.warning("[热点数据] AkshareFetcher 无数据，回退到 EmHiddenApiFetcher（浏览器模拟）")
            em = self._get_em_hidden_fetcher()
            if em is not None:
                if "concept_rankings" not in data or data["concept_rankings"] is None:
                    data["concept_rankings"] = self._safe_fetch(
                        lambda: em.get_concept_board_rankings(20), "概念板块排行(EM)"
                    )
                if "hot_stocks" not in data or data["hot_stocks"] is None:
                    data["hot_stocks"] = self._safe_fetch(
                        lambda: em.get_hot_rankings(30), "人气榜(EM)"
                    )
                if "limit_up_pool" not in data or data["limit_up_pool"] is None:
                    data["limit_up_pool"] = self._safe_fetch(
                        lambda: em.get_limit_up_pool(), "涨停板池(EM)"
                    )
                if "concept_fund_flow" not in data or data["concept_fund_flow"] is None:
                    data["concept_fund_flow"] = self._safe_fetch(
                        lambda: em.get_concept_fund_flow_rank("今日"), "概念资金流(EM)"
                    )
                if "industry_fund_flow" not in data or data["industry_fund_flow"] is None:
                    data["industry_fund_flow"] = self._safe_fetch(
                        lambda: em.get_industry_fund_flow_rank("今日"), "行业资金流(EM)"
                    )
                if "north_flow" not in data or data["north_flow"] is None:
                    data["north_flow"] = self._safe_fetch(
                        lambda: em.get_north_flow(), "北向资金(EM)"
                    )
                if "profit_effect" not in data or data["profit_effect"] is None:
                    data["profit_effect"] = self._safe_fetch(
                        lambda: em.get_market_profit_effect(), "赚钱效应(EM)"
                    )

        fetched_count = sum(1 for v in data.values() if v is not None)
        logger.info(f"[热点数据] 获取完成: {fetched_count}/{len(data) - 1} 个维度有数据")
        return data

    def build_hotspot_summary(self, hotspot_data: Dict[str, Any]) -> Dict[str, Any]:
        """从原始热点数据构建结构化摘要"""
        summary: Dict[str, Any] = {}

        concept_rankings = hotspot_data.get("concept_rankings")
        if concept_rankings:
            top_concepts, bottom_concepts = concept_rankings
            summary["top_concepts"] = top_concepts[:5]
            summary["bottom_concepts"] = bottom_concepts[:5]

        hot_stocks = hotspot_data.get("hot_stocks")
        if hot_stocks:
            summary["hot_stocks_top10"] = hot_stocks[:10]

        limit_up_pool = hotspot_data.get("limit_up_pool")
        if limit_up_pool is not None and not limit_up_pool.empty:
            summary["limit_up_count"] = len(limit_up_pool)
            consecutive_col = next(
                (c for c in ("consecutive_days", "连板数") if c in limit_up_pool.columns),
                None,
            )
            if consecutive_col:
                high_ladder = limit_up_pool[limit_up_pool[consecutive_col] >= 3]
                if not high_ladder.empty:
                    code_col = "code" if "code" in high_ladder.columns else "代码"
                    name_col = "name" if "name" in high_ladder.columns else "名称"
                    summary["high_ladder_stocks"] = [
                        {
                            "code": str(r.get(code_col, "")),
                            "name": str(r.get(name_col, "")),
                            "consecutive_days": int(r.get(consecutive_col, 0)),
                        }
                        for _, r in high_ladder.head(10).iterrows()
                    ]
        else:
            summary["limit_up_count"] = 0

        concept_fund = hotspot_data.get("concept_fund_flow")
        if concept_fund is not None and not concept_fund.empty:
            inflow_col = next(
                (c for c in concept_fund.columns if "净流入" in str(c)), None
            )
            name_col = next(
                (c for c in concept_fund.columns if c in ("名称", "板块名称", "name")), None
            )
            if inflow_col and name_col:
                work = concept_fund[[name_col, inflow_col]].copy()
                work[inflow_col] = pd.to_numeric(work[inflow_col], errors="coerce")
                top_inflow = work.nlargest(5, inflow_col)
                top_outflow = work.nsmallest(5, inflow_col)
                summary["top_inflow_concepts"] = [
                    {"name": str(r[name_col]), "net_inflow": float(r[inflow_col])}
                    for _, r in top_inflow.iterrows()
                ]
                summary["top_outflow_concepts"] = [
                    {"name": str(r[name_col]), "net_inflow": float(r[inflow_col])}
                    for _, r in top_outflow.iterrows()
                ]

        north_flow = hotspot_data.get("north_flow")
        if north_flow:
            summary["north_flow"] = north_flow

        profit_effect = hotspot_data.get("profit_effect")
        if profit_effect:
            summary["profit_effect"] = profit_effect

        return summary

    def build_hotspot_markdown(self, summary: Dict[str, Any], language: str = "zh") -> str:
        """将热点摘要渲染为 Markdown 文本块，供 LLM 或报告使用"""
        is_en = language == "en"
        lines: List[str] = []

        top_concepts = summary.get("top_concepts", [])
        bottom_concepts = summary.get("bottom_concepts", [])
        if top_concepts:
            if is_en:
                lines.append("## 🔥 Hot Concept Boards (Top 5)")
                for s in top_concepts:
                    lines.append(f"- **{s.get('name', '')}** ({s.get('change_pct', 0):+.2f}%)")
            else:
                lines.append("## 🔥 热门概念板块 (Top 5)")
                for s in top_concepts:
                    lines.append(f"- **{s.get('name', '')}** ({s.get('change_pct', 0):+.2f}%)")
            lines.append("")

        if bottom_concepts:
            if is_en:
                lines.append("## 💧 Lagging Concept Boards (Bottom 5)")
                for s in bottom_concepts:
                    lines.append(f"- **{s.get('name', '')}** ({s.get('change_pct', 0):+.2f}%)")
            else:
                lines.append("## 💧 领跌概念板块 (Bottom 5)")
                for s in bottom_concepts:
                    lines.append(f"- **{s.get('name', '')}** ({s.get('change_pct', 0):+.2f}%)")
            lines.append("")

        limit_up_count = summary.get("limit_up_count", 0)
        if limit_up_count > 0:
            if is_en:
                lines.append(f"## 📈 Limit-up Board: {limit_up_count} stocks hit limit-up today")
            else:
                lines.append(f"## 📈 涨停板池: 今日共 {limit_up_count} 只涨停")
            high_ladder = summary.get("high_ladder_stocks", [])
            if high_ladder:
                if is_en:
                    lines.append("**High-consecutive (≥3 boards):**")
                else:
                    lines.append("**高连板（≥3板）：**")
                items = []
                for s in high_ladder:
                    items.append(f"{s['name']}({s['code']}) {s['consecutive_days']}板")
                lines.append("、".join(items))
            lines.append("")

        hot_stocks = summary.get("hot_stocks_top10", [])
        if hot_stocks:
            if is_en:
                lines.append("## 🔥 Popular Stock Rankings (Top 10)")
                for s in hot_stocks:
                    lines.append(
                        f"- #{s.get('rank', '')} **{s.get('name', '')}** "
                        f"({s.get('code', '')}) {s.get('price', 0):.2f} "
                        f"({s.get('change_pct', 0):+.2f}%)"
                    )
            else:
                lines.append("## 🔥 人气榜 Top 10")
                for s in hot_stocks:
                    lines.append(
                        f"- #{s.get('rank', '')} **{s.get('name', '')}** "
                        f"({s.get('code', '')}) {s.get('price', 0):.2f} "
                        f"({s.get('change_pct', 0):+.2f}%)"
                    )
            lines.append("")

        top_inflow = summary.get("top_inflow_concepts", [])
        top_outflow = summary.get("top_outflow_concepts", [])
        if top_inflow or top_outflow:
            if is_en:
                lines.append("## 💰 Concept Board Fund Flow")
            else:
                lines.append("## 💰 概念板块资金流向")
            if top_inflow:
                items = []
                for s in top_inflow:
                    yi = s.get("net_inflow", 0) / 1e8
                    items.append(f"{s['name']}(+{yi:.2f}亿)")
                lines.append(f"净流入 Top: {' | '.join(items)}")
            if top_outflow:
                items = []
                for s in top_outflow:
                    yi = s.get("net_inflow", 0) / 1e8
                    items.append(f"{s['name']}({yi:.2f}亿)")
                lines.append(f"净流出 Top: {' | '.join(items)}")
            lines.append("")

        north_flow = summary.get("north_flow")
        if north_flow:
            direction = "净流入" if not is_en else "net inflow"
            if north_flow.get("net_inflow_yi", 0) < 0:
                direction = "净流出" if not is_en else "net outflow"
            if is_en:
                lines.append(
                    f"## 🌏 North-bound Capital: {direction} {abs(north_flow.get('net_inflow_yi', 0)):.2f} 亿 CNY"
                )
            else:
                lines.append(
                    f"## 🌏 北向资金: {direction} {abs(north_flow.get('net_inflow_yi', 0)):.2f} 亿"
                )
            lines.append("")

        return "\n".join(lines)

    def _get_akshare_fetcher(self):
        fetchers = self.data_manager._get_fetchers_snapshot()
        for f in fetchers:
            if f.name == "AkshareFetcher":
                return f
        return None

    def _get_em_hidden_fetcher(self):
        fetchers = self.data_manager._get_fetchers_snapshot()
        for f in fetchers:
            if f.name == "EmHiddenApiFetcher":
                return f
        return None

    @staticmethod
    def _safe_fetch(fn, label: str) -> Optional[Any]:
        try:
            import time as _time
            start = _time.time()
            result = fn()
            elapsed = _time.time() - start
            if result is not None and (not hasattr(result, 'empty') or not result.empty):
                logger.info(f"[热点数据] {label}: 成功 ({elapsed:.2f}s)")
                return result
            logger.warning(f"[热点数据] {label}: 返回空数据")
            return None
        except Exception as e:
            logger.warning(f"[热点数据] {label}: 异常 {e}")
            return None
