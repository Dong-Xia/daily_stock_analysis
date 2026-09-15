# -*- coding: utf-8 -*-
"""
Market Money Status — 市场资金水位评估

职责：
1. 聚合全市场数据（成交额、涨跌停、板块表现、北向资金、赚钱效应）
2. 输出市场资金状态标签：充沛 / 均衡 / 匮乏 / 抱团
3. 提供格式化 Markdown 文本用于报告注入

使用方式：
    status = assess_market_money_status(fetcher_manager)
    markdown_block = format_money_status_block(status, language="zh")
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from src.report_language import normalize_report_language

logger = logging.getLogger(__name__)

# ── 资金水位阈值（可调）──────────────────────────────────────
# 两市成交额（亿元）
_TURNOVER_ABUNDANT = 10000  # >1万亿 → 资金充沛
_TURNOVER_BALANCED_HIGH = 7000  # 7000-10000亿 → 均衡偏暖
_TURNOVER_BALANCED_LOW = 5000  # 5000-7000亿 → 均衡偏冷
# 涨停家数
_LIMIT_UP_HOT = 80  # >80 → 情绪亢奋
_LIMIT_UP_WARM = 40  # 40-80 → 温和
# 涨跌比阈值
_BREADTH_HOT = 2.0  # 涨/跌 >2.0 → 普涨
_BREADTH_COLD = 0.5  # 涨/跌 <0.5 → 普跌


@dataclass
class MoneyStatus:
    """市场资金水位评估结果"""
    level: str = "unknown"  # abundant / balanced / scarce / clustering
    level_cn: str = "未知"
    total_amount: float = 0.0  # 两市成交额（亿元）
    limit_up_count: int = 0
    limit_down_count: int = 0
    up_count: int = 0
    down_count: int = 0
    breadth_ratio: float = 0.0  # 涨跌比
    north_flow: Optional[float] = None  # 北向资金净流入（亿元）
    profit_effect: Optional[Dict[str, Any]] = None  # 赚钱效应
    top_sectors: List[Dict] = field(default_factory=list)
    bottom_sectors: List[Dict] = field(default_factory=list)
    clustering_detected: bool = False  # 是否检测到资金抱团迹象
    evidence: List[str] = field(default_factory=list)  # 判定依据


def assess_market_money_status(
    fetcher_manager: Any,
    region: str = "cn",
) -> MoneyStatus:
    """
    评估市场资金水位。

    Args:
        fetcher_manager: DataFetcherManager 实例
        region: 市场区域（cn/us）

    Returns:
        MoneyStatus — 资金状态评估结果
    """
    status = MoneyStatus()

    try:
        market_stats = fetcher_manager.get_market_stats()
        if market_stats:
            status.total_amount = float(market_stats.get("total_amount", 0))
            status.up_count = int(market_stats.get("up_count", 0))
            status.down_count = int(market_stats.get("down_count", 0))
            status.limit_up_count = int(market_stats.get("limit_up_count", 0))
            status.limit_down_count = int(market_stats.get("limit_down_count", 0))
    except Exception as e:
        logger.warning("获取市场统计数据失败: %s", e)

    if status.down_count > 0:
        status.breadth_ratio = round(status.up_count / max(status.down_count, 1), 2)

    try:
        top, bottom = fetcher_manager.get_sector_rankings(5)
        status.top_sectors = top or []
        status.bottom_sectors = bottom or []
    except Exception as e:
        logger.warning("获取板块涨跌榜失败: %s", e)

    try:
        hotspot = _fetch_hotspot_data(fetcher_manager)
        if hotspot:
            status.north_flow = hotspot.get("north_flow")
            status.profit_effect = hotspot.get("profit_effect")
    except Exception as e:
        logger.warning("获取热点数据失败: %s", e)

    _classify_money_status(status)

    return status


def _fetch_hotspot_data(fetcher_manager: Any) -> Dict[str, Any]:
    """尝试从多个数据源获取热点增强数据。"""
    result: Dict[str, Any] = {}

    # 尝试 AkshareFetcher（最全）
    akshare = getattr(fetcher_manager, "_fetchers", None)
    if akshare:
        for f in akshare:
            fetcher_name = type(f).__name__

            # 北向资金
            if hasattr(f, "get_north_flow") and result.get("north_flow") is None:
                try:
                    nf = f.get_north_flow()
                    if nf and isinstance(nf, dict):
                        # 取当日净流入
                        result["north_flow"] = nf.get("net_inflow") or nf.get("value")
                except Exception:
                    pass

            # 赚钱效应
            if hasattr(f, "get_market_profit_effect") and result.get("profit_effect") is None:
                try:
                    pe = f.get_market_profit_effect()
                    if pe:
                        result["profit_effect"] = pe
                except Exception:
                    pass

            # 短线只要找到一个能用的 fetcher 就行
            if result.get("north_flow") is not None and result.get("profit_effect") is not None:
                break

    return result


def _classify_money_status(status: MoneyStatus) -> None:
    """
    基于聚合数据判定资金水位级别。

    逻辑（A 股）：
    - 成交额 >1万亿 + 涨停 >80 → 充沛 + 情绪亢奋 → 资金充沛
    - 成交额 >1万亿 + 涨停 正常 → 资金充沛但理性
    - 成交额 5000-10000亿 + 涨跌比正常 → 资金均衡
    - 成交额 <5000亿 → 资金匮乏
    - 涨停 >80 + 高连板票多 → 资金抱团（妖股行情）
    """
    evidence = []
    amount = status.total_amount
    limit_up = status.limit_up_count
    breadth = status.breadth_ratio

    # 成交额判断
    if amount >= _TURNOVER_ABUNDANT:
        evidence.append(f"两市成交额 {amount:.0f}亿，资金充沛")
    elif amount >= _TURNOVER_BALANCED_LOW:
        evidence.append(f"两市成交额 {amount:.0f}亿，资金相对均衡")
    else:
        evidence.append(f"两市成交额 {amount:.0f}亿，资金偏紧")

    # 涨跌比判断
    if breadth >= _BREADTH_HOT:
        evidence.append(f"涨跌比 {breadth}，市场普涨")
    elif breadth <= _BREADTH_COLD:
        evidence.append(f"涨跌比 {breadth}，市场普跌")

    # 涨停热度判断
    if limit_up >= _LIMIT_UP_HOT:
        evidence.append(f"涨停 {limit_up}家，短线情绪亢奋")
    elif limit_up >= _LIMIT_UP_WARM:
        evidence.append(f"涨停 {limit_up}家，短线情绪温和")
    else:
        evidence.append(f"涨停 {limit_up}家，短线情绪偏冷")

    # 资金抱团检测：高成交额 + 涨停多 + 涨跌比一般（结构性行情）
    status.clustering_detected = (
        amount >= _TURNOVER_BALANCED_HIGH
        and limit_up >= _LIMIT_UP_HOT
        and breadth < _BREADTH_HOT
    )
    if status.clustering_detected:
        evidence.append("资金抱团迹象明显，结构性行情特征")

    # 级别判定
    if amount >= _TURNOVER_ABUNDANT and limit_up >= _LIMIT_UP_HOT:
        status.level = "abundant"
        status.level_cn = "资金充沛"
        evidence.insert(0, "市场资金充沛，做多情绪旺盛")
    elif amount >= _TURNOVER_ABUNDANT:
        status.level = "abundant_rational"
        status.level_cn = "资金充沛（理性）"
        evidence.insert(0, "市场资金充沛，但情绪相对理性")
    elif status.clustering_detected:
        status.level = "clustering"
        status.level_cn = "资金抱团"
        evidence.insert(0, "资金集中抱团，结构性行情为主")
    elif amount >= _TURNOVER_BALANCED_LOW:
        status.level = "balanced"
        status.level_cn = "资金均衡"
        evidence.insert(0, "市场资金面相对均衡，结构性机会为主")
    else:
        status.level = "scarce"
        status.level_cn = "资金匮乏"
        evidence.insert(0, "市场资金偏紧，需控制仓位、精选个股")

    status.evidence = evidence


def format_money_status_block(
    status: MoneyStatus,
    language: str = "zh",
) -> str:
    """
    将资金水位评估格式化为 Markdown 报告块。

    Args:
        status: 资金水位评估结果
        language: 报告语言（zh/en）

    Returns:
        Markdown 格式的文本块，如无可用的资金数据则返回空字符串
    """
    if status.level == "unknown":
        return ""

    lang = normalize_report_language(language)
    emoji_map = {
        "abundant": "🟢",
        "abundant_rational": "🟢",
        "balanced": "🟡",
        "scarce": "🔴",
        "clustering": "🟠",
        "unknown": "⚪",
    }

    label_map = {
        "zh": {
            "title": "市场资金状态",
            "amount_label": "两市成交额",
            "limit_up_label": "涨停",
            "limit_down_label": "跌停",
            "breadth_label": "涨跌比",
            "north_flow_label": "北向资金",
            "sector_label": "领涨板块",
            "advice_abundant": "逻辑驱动行情，可积极操作",
            "advice_balanced": "结构性行情，精选个股为主",
            "advice_scarce": "资金偏紧，注意仓位控制",
            "advice_clustering": "资金抱团行情，跟随主力方向",
            "clustering_hint": "（资金抱团，妖股轮番上涨）",
            "data_unavailable": "数据获取暂不可用",
        },
        "en": {
            "title": "Market Money Status",
            "amount_label": "Total Turnover",
            "limit_up_label": "Limit Up",
            "limit_down_label": "Limit Down",
            "breadth_label": "Breadth Ratio",
            "north_flow_label": "North-bound Flow",
            "sector_label": "Leading Sectors",
            "advice_abundant": "Capital-driven market, active trading favorable",
            "advice_balanced": "Structural market, selective stock picking",
            "advice_scarce": "Tight capital, control position sizing",
            "advice_clustering": "Capital clustering, follow dominant direction",
            "clustering_hint": "(capital clustering, speculative stocks rotate)",
            "data_unavailable": "Market data temporarily unavailable",
        },
    }

    labels = label_map.get(lang, label_map["zh"])
    emoji = emoji_map.get(status.level, "⚪")

    lines = [f"### 💰 {emoji} {labels['title']}：{status.level_cn}"]
    lines.append("")

    # 核心数据
    data_line = f"{labels['amount_label']}：{status.total_amount:.0f}亿"
    if status.up_count > 0:
        data_line += (
            f" ｜{labels['breadth_label']}：{status.up_count}/{status.down_count}"
            f"({status.breadth_ratio})"
        )
    data_line += f" ｜{labels['limit_up_label']}：{status.limit_up_count}"
    if status.limit_down_count > 0:
        data_line += f" ｜{labels['limit_down_label']}：{status.limit_down_count}"
    if status.north_flow is not None:
        nf_emoji = "🟢" if status.north_flow > 0 else "🔴"
        data_line += f" ｜{labels['north_flow_label']}：{nf_emoji}{status.north_flow:.1f}亿"

    lines.append(data_line)
    lines.append("")

    # 领涨板块
    if status.top_sectors:
        sector_names = [s.get("name", "") for s in status.top_sectors[:3] if s.get("name")]
        if sector_names:
            lines.append(f"🔥 {labels['sector_label']}：{'、'.join(sector_names)}")
            lines.append("")

    # 判定依据 / 建议
    advice_map = {
        "abundant": labels["advice_abundant"],
        "abundant_rational": labels["advice_abundant"],
        "balanced": labels["advice_balanced"],
        "scarce": labels["advice_scarce"],
        "clustering": labels["advice_clustering"],
    }
    advice = advice_map.get(status.level, "")
    if status.clustering_detected and status.level != "clustering":
        advice += " " + labels["clustering_hint"]

    if advice:
        lines.append(f"💡 *{advice}*")
        lines.append("")

    return "\n".join(lines)
