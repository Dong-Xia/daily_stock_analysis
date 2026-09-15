# -*- coding: utf-8 -*-
"""
Stop-Loss Manager - 三层止损自动化

  硬止损(Hard): ATR/MA/结构锚点 → 入场前确定
  移动止损(Trailing): 随价格上涨上移
  时间止损(Time): N日未验证入场逻辑 → 退出
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class StopType(str, Enum):
    HARD = "hard"
    TRAILING = "trailing"
    TIME = "time"


class StopMethod(str, Enum):
    ATR = "atr"
    MA = "ma"
    STRUCTURE = "structure"
    PERCENT = "percent"


@dataclass
class StopConfig:
    """Stop-loss configuration per position."""
    stock_code: str = ""
    stock_name: str = ""
    entry_price: float = 0.0
    entry_date: str = ""
    stop_type: StopType = StopType.HARD
    stop_method: StopMethod = StopMethod.ATR
    stop_price: float = 0.0
    atr_multiplier: float = 2.0
    atr_period: int = 14
    trailing_pct: float = 10.0
    time_limit_days: int = 20
    highest_price: float = 0.0
    ma_period: int = 20
    notes: str = ""


@dataclass
class StopEvent:
    """A triggered stop-loss event."""
    stock_code: str = ""
    stock_name: str = ""
    stop_type: StopType = StopType.HARD
    stop_price: float = 0.0
    current_price: float = 0.0
    triggered: bool = False
    distance_pct: float = 0.0
    pnl_pct: float = 0.0
    reason: str = ""


@dataclass
class InitialStops:
    """All initial stop levels computed at entry."""
    hard_stop: float = 0.0
    trailing_start: float = 0.0
    hard_stop_pct: float = 0.0
    method: StopMethod = StopMethod.ATR
    rationale: str = ""


class StopLossManager:
    """Multi-layer stop-loss computation and trigger evaluation."""

    ATR_MULTIPLIER = 2.0
    DEFAULT_TRAILING_PCT = 8.0
    DEFAULT_TIME_LIMIT = 20

    def __init__(
        self,
        default_atr_multiplier: float = 2.0,
        default_trailing_pct: float = 8.0,
        default_time_limit_days: int = 20,
        default_ma_period: int = 20,
    ):
        self.default_atr_multiplier = default_atr_multiplier
        self.default_trailing_pct = default_trailing_pct
        self.default_time_limit_days = default_time_limit_days
        self.default_ma_period = default_ma_period

    def compute_initial_stops(
        self,
        entry_price: float,
        df: Optional[pd.DataFrame] = None,
        preferred_method: StopMethod = StopMethod.ATR,
    ) -> InitialStops:
        rationale_parts: List[str] = []

        if preferred_method == StopMethod.ATR and df is not None and not df.empty and len(df) >= 14:
            atr = self._compute_atr(df, 14)
            if atr > 0:
                hard_stop = round(entry_price - atr * self.default_atr_multiplier, 2)
                trailing_start = round(entry_price + atr * self.default_atr_multiplier, 2)
                pct = (entry_price - hard_stop) / entry_price * 100
                rationale_parts.append(f"ATR({atr:.2f})×{self.default_atr_multiplier} → 止损={hard_stop:.2f} (-{pct:.1f}%)")
                return InitialStops(
                    hard_stop=hard_stop, trailing_start=trailing_start,
                    hard_stop_pct=round(pct, 1), method=StopMethod.ATR,
                    rationale="; ".join(rationale_parts),
                )

        if preferred_method == StopMethod.MA and df is not None and not df.empty:
            ma = self._compute_ma(df, self.default_ma_period)
            if ma > 0 and ma < entry_price:
                pct = (entry_price - ma) / entry_price * 100
                rationale_parts.append(f"MA{self.default_ma_period}={ma:.2f} → 止损={ma:.2f} (-{pct:.1f}%)")
                return InitialStops(
                    hard_stop=round(ma, 2), trailing_start=entry_price * 1.05,
                    hard_stop_pct=round(pct, 1), method=StopMethod.MA,
                    rationale="; ".join(rationale_parts),
                )

        if preferred_method == StopMethod.STRUCTURE and df is not None and not df.empty and len(df) >= 60:
            low = df["low"].tail(60).min()
            if low > 0 and low < entry_price:
                pct = (entry_price - low) / entry_price * 100
                rationale_parts.append(f"60日低点={low:.2f} → 止损={low:.2f} (-{pct:.1f}%)")
                return InitialStops(
                    hard_stop=round(low, 2), trailing_start=entry_price * 1.05,
                    hard_stop_pct=round(pct, 1), method=StopMethod.STRUCTURE,
                    rationale="; ".join(rationale_parts),
                )

        pct = self.default_trailing_pct / 2
        hard_stop = round(entry_price * (1 - pct / 100), 2)
        rationale_parts.append(f"百分比默认: -{pct:.1f}% → 止损={hard_stop:.2f}")
        return InitialStops(
            hard_stop=hard_stop, trailing_start=entry_price * 1.03,
            hard_stop_pct=round(pct, 1), method=StopMethod.PERCENT,
            rationale="; ".join(rationale_parts),
        )

    def compute_hard_stop(
        self, entry_price: float, df: Optional[pd.DataFrame] = None,
        method: StopMethod = StopMethod.ATR,
    ) -> float:
        stops = self.compute_initial_stops(entry_price, df, method)
        return stops.hard_stop

    def compute_trailing_stop(
        self, highest_price: float, atr_value: Optional[float] = None,
        multiplier: Optional[float] = None,
    ) -> float:
        mult = multiplier or self.default_atr_multiplier
        if atr_value and atr_value > 0:
            return round(highest_price - atr_value * mult, 2)
        return round(highest_price * (1 - self.default_trailing_pct / 100), 2)

    def check_time_stop(
        self, entry_date: str, current_date: Optional[str] = None,
        max_days: Optional[int] = None,
    ) -> StopEvent:
        limit = max_days or self.default_time_limit_days
        try:
            entry_dt = datetime.strptime(entry_date, "%Y-%m-%d").date()
        except ValueError:
            return StopEvent(stop_type=StopType.TIME, reason="日期格式错误")

        now = date.today()
        if current_date:
            try:
                now = datetime.strptime(current_date, "%Y-%m-%d").date()
            except ValueError:
                pass

        days_held = (now - entry_dt).days
        triggered = days_held >= limit

        return StopEvent(
            stop_type=StopType.TIME,
            triggered=triggered,
            reason=f"持仓{days_held}天 > 时间止损{limit}天" if triggered else f"持仓{days_held}天 (还剩{limit-days_held}天)",
            distance_pct=round(days_held / limit * 100, 1) if limit > 0 else 0,
        )

    def evaluate(
        self, config: StopConfig, current_price: float,
        current_date: Optional[str] = None,
    ) -> List[StopEvent]:
        events: List[StopEvent] = []

        distance_pct = (current_price - config.stop_price) / config.stop_price * 100 if config.stop_price > 0 else 0
        pnl_pct = (current_price - config.entry_price) / config.entry_price * 100 if config.entry_price > 0 else 0

        hard_triggered = current_price <= config.stop_price
        events.append(StopEvent(
            stock_code=config.stock_code,
            stock_name=config.stock_name,
            stop_type=StopType.HARD,
            stop_price=config.stop_price,
            current_price=current_price,
            triggered=hard_triggered,
            distance_pct=round(distance_pct, 1),
            pnl_pct=round(pnl_pct, 1),
            reason="跌破硬止损价" if hard_triggered else f"距止损{distance_pct:+.1f}%",
        ))

        if config.entry_date:
            time_event = self.check_time_stop(config.entry_date, current_date, config.time_limit_days)
            time_event.stock_code = config.stock_code
            time_event.stock_name = config.stock_name
            time_event.current_price = current_price
            time_event.pnl_pct = round(pnl_pct, 1)
            events.append(time_event)

        active_events = [e for e in events if e.triggered]
        if active_events:
            logger.info("[止损] %s: %d个止损触发", config.stock_code, len(active_events))
        else:
            logger.debug("[止损] %s: 全部止损未触发", config.stock_code)

        return events

    def batch_evaluate(
        self, positions: List[StopConfig], prices: Dict[str, float],
        current_date: Optional[str] = None,
    ) -> List[StopEvent]:
        triggered: List[StopEvent] = []
        for pos in positions:
            price = prices.get(pos.stock_code, pos.entry_price)
            events = self.evaluate(pos, price, current_date)
            for e in events:
                if e.triggered:
                    triggered.append(e)
        return triggered

    @staticmethod
    def _compute_atr(df: pd.DataFrame, period: int = 14) -> float:
        if df.empty or len(df) < period:
            return 0.0
        high = df["high"].tail(period + 1)
        low = df["low"].tail(period + 1)
        close = df["close"].tail(period + 1)
        prev_close = close.shift(1).fillna(close.iloc[0])
        tr = np.maximum(
            high - low,
            np.maximum(
                np.abs(high - prev_close),
                np.abs(low - prev_close),
            ),
        )
        return float(tr.tail(period).mean())

    @staticmethod
    def _compute_ma(df: pd.DataFrame, period: int = 20) -> float:
        if df.empty or len(df) < period:
            return 0.0
        return float(df["close"].tail(period).mean())

    @staticmethod
    def format_events(events: List[StopEvent]) -> str:
        if not events:
            return "✅ 所有止损未触发"
        lines = ["🚨 止损触发:"]
        for e in events:
            marker = "🔴" if e.triggered else "🟢"
            lines.append(f"  {marker} {e.stock_name}({e.stock_code}) "
                        f"[{e.stop_type.value}] 止损价={e.stop_price:.2f} "
                        f"现价={e.current_price:.2f} 盈亏={e.pnl_pct:+.1f}%"
                        f"{' ← ' + e.reason if e.triggered else ''}")
        return "\n".join(lines)
