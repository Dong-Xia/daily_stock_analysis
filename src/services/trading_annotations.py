# -*- coding: utf-8 -*-
"""
Trading Annotations — 交易原则注解层

从现有分析数据派生交易原则标注，无需额外数据源：
- P4 三周期结构：长/中/短同频/背离判断
- P1 热门/冷门：基于量价的热度标签
- P2 趋势确认：趋势状态明确标注
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


def compute_cycle_structure(
    trend_analysis: Optional[Dict[str, Any]],
) -> Dict[str, str]:
    """
    计算三周期结构标注。

    利用现有技术面数据推断长/中/短三个周期的状态和一致性：
      - 长线: trend_strength + MA60 方向
      - 中线: MA5/MA10/MA20 排列 + macd_status
      - 短线: bias_ma5 + volume_status + RSI

    Returns:
        dict with keys: long_term, medium_term, short_term, alignment
    """
    result: Dict[str, str] = {
        "long_term": "未知",
        "medium_term": "未知",
        "short_term": "未知",
        "alignment": "unknown",
    }

    if not trend_analysis:
        return result

    trend_strength = trend_analysis.get("trend_strength", 0) or 0
    ma_alignment = trend_analysis.get("ma_alignment", "") or ""
    bias_ma5 = trend_analysis.get("bias_ma5", 0) or 0
    volume_status = trend_analysis.get("volume_status", "") or ""
    macd_status = trend_analysis.get("macd_status", "") or ""
    signal_score = trend_analysis.get("signal_score", 50) or 50

    # 长线趋势：trend_strength + signal_score 作为长周期方向
    if trend_strength >= 65 and signal_score >= 60:
        result["long_term"] = "多头"
    elif trend_strength <= 35 and signal_score <= 40:
        result["long_term"] = "空头"
    else:
        result["long_term"] = "震荡"

    # 中线趋势：MA 排列 + MACD
    is_bullish_ma = "多头" in ma_alignment
    is_bearish_ma = "空头" in ma_alignment
    is_macd_bullish = macd_status in ("bullish", "golden_cross", "金叉")

    if is_bullish_ma and is_macd_bullish:
        result["medium_term"] = "走强"
    elif is_bullish_ma:
        result["medium_term"] = "偏强"
    elif is_bearish_ma:
        result["medium_term"] = "走弱"
    else:
        result["medium_term"] = "震荡"

    # 短线情绪：乖离率 + 量能
    if bias_ma5 > 3:
        result["short_term"] = "过热"
    elif bias_ma5 > 1:
        result["short_term"] = "偏强"
    elif bias_ma5 < -3:
        result["short_term"] = "超跌"
    elif bias_ma5 < -1:
        result["short_term"] = "偏弱"
    else:
        result["short_term"] = "中性"

    # 同频/背离判定
    long_bullish = result["long_term"] == "多头"
    med_bullish = result["medium_term"] in ("走强", "偏强")
    short_bullish = result["short_term"] in ("偏强", "过热")
    long_bearish = result["long_term"] == "空头"
    med_bearish = result["medium_term"] == "走弱"
    short_bearish = result["short_term"] in ("偏弱", "超跌")

    if long_bullish and med_bullish and short_bullish:
        result["alignment"] = "all_bullish"
    elif long_bearish and med_bearish and short_bearish:
        result["alignment"] = "all_bearish"
    elif long_bullish and med_bullish and not short_bullish:
        result["alignment"] = "long_med_bullish_short_diverge"
    elif long_bullish and not med_bullish:
        result["alignment"] = "long_bullish_med_diverge"
    elif long_bearish and med_bearish and not short_bearish:
        result["alignment"] = "bearish_with_short_rebound"
    else:
        result["alignment"] = "mixed"

    return result


def compute_heat_label(
    realtime: Optional[Dict[str, Any]],
    trend_analysis: Optional[Dict[str, Any]],
    sector_names: Optional[list] = None,
    stock_sector: Optional[str] = None,
) -> Dict[str, str]:
    """
    计算热门/冷门标签。

    基于量比、换手率、涨跌幅综合判断。

    Returns:
        dict with keys: label, turnover_desc, momentum_desc
    """
    result: Dict[str, str] = {
        "label": "中性",
        "label_en": "Neutral",
        "turnover_desc": "",
        "momentum_desc": "",
    }

    if not realtime:
        return result

    volume_ratio = realtime.get("volume_ratio")
    turnover_rate = realtime.get("turnover_rate")
    change_pct = realtime.get("change_pct")

    # 热度得分 (0-10)
    heat_score = 0
    factors: list[str] = []

    if volume_ratio is not None:
        if volume_ratio >= 3.0:
            heat_score += 4
            factors.append(f"量比{volume_ratio:.1f}（巨量）")
            result["turnover_desc"] = "巨量"
        elif volume_ratio >= 2.0:
            heat_score += 3
            factors.append(f"量比{volume_ratio:.1f}（明显放量）")
            result["turnover_desc"] = "明显放量"
        elif volume_ratio >= 1.2:
            heat_score += 1
            factors.append(f"量比{volume_ratio:.1f}（温和放量）")
            result["turnover_desc"] = "温和放量"
        elif volume_ratio < 0.5:
            heat_score -= 1
            factors.append(f"量比{volume_ratio:.1f}（极度萎缩）")
            result["turnover_desc"] = "极度萎缩"
        else:
            result["turnover_desc"] = "正常"

    if turnover_rate is not None:
        if turnover_rate >= 10:
            heat_score += 3
            factors.append(f"换手率{turnover_rate:.1f}%（非常高）")
        elif turnover_rate >= 5:
            heat_score += 2
            factors.append(f"换手率{turnover_rate:.1f}%（较高）")
        elif turnover_rate >= 1:
            heat_score += 0  # normal
        else:
            heat_score -= 1

    if change_pct is not None:
        if change_pct >= 5:
            heat_score += 2
            result["momentum_desc"] = "强势上攻"
        elif change_pct >= 2:
            heat_score += 1
            result["momentum_desc"] = "温和上涨"
        elif change_pct <= -5:
            heat_score -= 2
            result["momentum_desc"] = "大幅下跌"
        elif change_pct <= -2:
            heat_score -= 1
            result["momentum_desc"] = "弱势下跌"
        else:
            result["momentum_desc"] = "窄幅震荡"

    # 综合判定
    if heat_score >= 6:
        result["label"] = "热门"
        result["label_en"] = "Hot"
    elif heat_score >= 3:
        result["label"] = "活跃"
        result["label_en"] = "Active"
    elif heat_score <= -2:
        result["label"] = "冷门"
        result["label_en"] = "Cold"
    else:
        result["label"] = "中性"
        result["label_en"] = "Neutral"

    return result


def compute_trend_confirmation(
    trend_analysis: Optional[Dict[str, Any]],
) -> Dict[str, str]:
    """
    计算趋势确认状态。

    Returns:
        dict with keys: status, signal_strength, bias_warning
    """
    result: Dict[str, str] = {
        "status": "未确认",
        "status_en": "Unconfirmed",
        "signal_strength": "中性",
        "bias_warning": "",
    }

    if not trend_analysis:
        return result

    ma_alignment = trend_analysis.get("ma_alignment", "") or ""
    trend_strength = trend_analysis.get("trend_strength", 0) or 0
    bias_ma5 = trend_analysis.get("bias_ma5", 0) or 0
    buy_signal = trend_analysis.get("buy_signal", "") or ""
    macd_status = trend_analysis.get("macd_status", "") or ""

    # 趋势确认
    is_bullish_alignment = "多头" in ma_alignment
    is_bearish_alignment = "空头" in ma_alignment
    is_macd_bullish = macd_status in ("bullish", "golden_cross", "金叉")

    if is_bullish_alignment and is_macd_bullish and trend_strength >= 60:
        result["status"] = "上升趋势确认"
        result["status_en"] = "Up Trend Confirmed"
    elif is_bullish_alignment and trend_strength >= 50:
        result["status"] = "上升趋势（待确认）"
        result["status_en"] = "Up Trend (Pending)"
    elif is_bearish_alignment:
        result["status"] = "下降趋势"
        result["status_en"] = "Down Trend"
    elif trend_strength >= 50:
        result["status"] = "偏强震荡"
        result["status_en"] = "Bullish Consolidation"
    else:
        result["status"] = "偏弱震荡"
        result["status_en"] = "Bearish Consolidation"

    # 信号强度
    if buy_signal in ("strong_buy", "buy", "买入"):
        result["signal_strength"] = "强" if trend_strength >= 60 else "中"
    elif buy_signal in ("sell", "strong_sell", "卖出"):
        result["signal_strength"] = "弱"

    # 乖离率预警
    if bias_ma5 > 5:
        result["bias_warning"] = "偏高（注意追高风险）"
    elif bias_ma5 > 3:
        result["bias_warning"] = "偏高"
    elif bias_ma5 < -5:
        result["bias_warning"] = "偏低（注意超跌反弹）"
    elif bias_ma5 < -3:
        result["bias_warning"] = "偏低"

    return result
