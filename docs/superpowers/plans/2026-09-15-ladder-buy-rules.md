# 梯子买入双规则 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 按已批准 spec（`docs/superpowers/specs/2026-09-15-ladder-buy-rules-design.md`）在信号链日线流程落地两条买入规则（R1 取代旧"回踩完成"、R2 新增"二次放量确认→明日买入"），并提供历史回放胜率对照报告。

**Architecture:** 纯函数状态机 `ladder_rules.py` 作为唯一口径源，被每日筛选脚本 `screen_signal.py`（feed 全量取最后一天）与回放脚本 `replay_rules.py`（feed 全程记录触发日）共用；前端仅扩状态白名单。

**Tech Stack:** Python 3.11 + pandas（外部脚本目录 `/Users/zhangze/stockData/dsa_signal/`，用仓库 `.venv` 跑）；React/TS + vitest（`apps/dsa-web/`）。

**提交约定:** `/Users/zhangze/stockData/dsa_signal/` 在 Task 1 被 `git init`，本计划所有 commit 只发生在该本地新仓库；**主仓库（daily_stock_analysis）一律不 commit**（项目硬规则，前端/文档改动留在工作区）。commit message 英文。

**统一命令别名:** 下文 `$PY` = `/Users/zhangze/Desktop/工具安装包/app/stock/daily_stock_analysis/.venv/bin/python`；回放/测试的工作目录必须是 `/Users/zhangze/stockData`（`dsa_signal` 是其包目录，`mrmc_full` 在此层）。

---

### Task 1: 备份与版本管理基线

**Files:**
- Create: `/Users/zhangze/stockData/dsa_signal/*.bak-20260915`（备份）
- Create: `/Users/zhangze/stockData/dsa_signal/.gitignore`

- [ ] **Step 1: 备份将被修改的脚本**

```bash
cd /Users/zhangze/stockData/dsa_signal
cp screen_signal.py screen_signal.py.bak-20260915
```

- [ ] **Step 2: git init 基线（spec 已批准）**

```bash
cd /Users/zhangze/stockData/dsa_signal
printf '*.bak-*\n__pycache__/\n*.pyc\nlogs/\n' > .gitignore
git init -q && git add -A && git commit -q -m "chore: baseline import of dsa_signal scripts"
```

预期：`git log --oneline` 出现 1 条 commit。若目录已在 git 仓库内（`git rev-parse` 成功指向别处）→ 停下询问用户，不要嵌套 init。

---

### Task 2: ladder_rules.py — 参数 + R1 状态机

**Files:**
- Create: `/Users/zhangze/stockData/dsa_signal/ladder_rules.py`
- Test: `/Users/zhangze/stockData/dsa_signal/tests/test_ladder_rules.py`（新建 tests 目录）

- [ ] **Step 1: 写失败测试（R1 五例）**

创建 `tests/__init__.py`（空文件）与 `tests/test_ladder_rules.py`：

```python
# -*- coding: utf-8 -*-
"""ladder_rules 状态机单元测试：手写小K线夹具，SA=10 SB=9。"""
import pandas as pd

from dsa_signal.ladder_rules import (
    STATUS_R1, STATUS_R1_WAIT, STATUS_SIGNAL_TODAY, eval_daily,
)

WARM = [{'o': 9.5, 'c': 9.5, 'l': 9.4, 'v': 100}] * 6


def mkdf(rows, sa=10.0, sb=9.0):
    data = []
    for i, r in enumerate(rows):
        o, c, l, v = r['o'], r['c'], r['l'], r['v']
        data.append({'date': f'2026-01-{i+1:02d}', 'open': o, 'close': c,
                     'high': max(o, c) + 0.05, 'low': l, 'volume': v,
                     'SA': sa, 'SB': sb, 'DXX': r.get('sig', False), 'DXDX': False})
    return pd.DataFrame(data)


def _sig_then(happy_tail):
    return WARM + [{'o': 9.5, 'c': 9.5, 'l': 9.4, 'v': 100, 'sig': True}] + happy_tail


def test_r1_full_path_triggers():
    rows = _sig_then([
        {'o': 9.6, 'c': 10.2, 'l': 9.5, 'v': 100},   # 突破日 V0=100
        {'o': 9.8, 'c': 9.2, 'l': 8.8, 'v': 50},     # 缩量贴轨(50≤0.6×100, low≤9.09) 收阴
        {'o': 9.1, 'c': 9.6, 'l': 8.95, 'v': 110},   # 确认日1: 温和放量阳线收>SB
        {'o': 9.6, 'c': 9.9, 'l': 9.05, 'v': 115},   # 确认日2 → 触发
    ])
    assert eval_daily(mkdf(rows))['status'] == STATUS_R1


def test_r1_weak_repair_below_band_not_triggered():
    # 西部证券 2026-09-14 形态: 收盘仍在 SB 之下 → 新口径不得触发
    rows = _sig_then([
        {'o': 9.6, 'c': 10.2, 'l': 9.5, 'v': 100},
        {'o': 9.8, 'c': 9.2, 'l': 8.8, 'v': 50},
        {'o': 9.0, 'c': 8.9, 'l': 8.85, 'v': 110},   # 阳线但收盘 8.9 < SB → 非确认日
        {'o': 8.9, 'c': 8.95, 'l': 8.9, 'v': 110},   # 收>SB 不成立
    ])
    st = eval_daily(mkdf(rows))['status']
    assert st != STATUS_R1 and st == STATUS_R1_WAIT


def test_r1_burst_volume_excluded():
    rows = _sig_then([
        {'o': 9.6, 'c': 10.2, 'l': 9.5, 'v': 100},
        {'o': 9.8, 'c': 9.2, 'l': 8.8, 'v': 50},
        {'o': 9.1, 'c': 9.6, 'l': 8.95, 'v': 110},
        {'o': 9.6, 'c': 9.9, 'l': 9.05, 'v': 400},   # 爆量 >2.5×MA5 → 重置连击
    ])
    assert eval_daily(mkdf(rows))['status'] != STATUS_R1


def test_r1_single_confirm_day_not_enough():
    rows = _sig_then([
        {'o': 9.6, 'c': 10.2, 'l': 9.5, 'v': 100},
        {'o': 9.8, 'c': 9.2, 'l': 8.8, 'v': 50},
        {'o': 9.1, 'c': 9.6, 'l': 8.95, 'v': 110},   # 只有 1 个确认日
    ])
    assert eval_daily(mkdf(rows))['status'] == STATUS_R1_WAIT


def test_death_break_resets_track():
    rows = _sig_then([
        {'o': 9.6, 'c': 10.2, 'l': 9.5, 'v': 100},
        {'o': 9.8, 'c': 8.5, 'l': 8.4, 'v': 60},     # 收盘 < SB×0.97=8.73 → 作废
    ])
    assert eval_daily(mkdf(rows)) is None
```

- [ ] **Step 2: 跑测试确认失败**

```bash
cd /Users/zhangze/stockData && $PY -m pytest dsa_signal/tests/test_ladder_rules.py -q
```
预期：`ModuleNotFoundError: No module named 'dsa_signal.ladder_rules'`（collection error）。

- [ ] **Step 3: 实现 ladder_rules.py（本阶段完整文件，含 R1+R2 骨架，R2 在 Task 3 补测试）**

```python
# -*- coding: utf-8 -*-
"""梯子买入规则引擎（纯函数无 IO）。

设计文档: daily_stock_analysis/docs/superpowers/specs/2026-09-15-ladder-buy-rules-design.md
- R1: 战法信号→5日内破SA→缩量贴SB回踩→连续两日温和放量收阳且收盘收复SB（取代旧单日口径）
- R2: 起量突破SA(≥1.5×MA5量)→缩量回梯内→二次起量→次日量能持续
两个入口共用: screen_signal.py（feed 全量取末日）/ replay_rules.py（feed 全程记触发）。
"""
from collections import deque

RULE_PARAMS = {
    'breakout_within_days': 5,
    'r1_pullback_vol_ratio': 0.6,
    'r1_touch_band_pct': 1.01,
    'r1_mild_vol_low': 1.1,
    'r1_mild_vol_high': 2.5,
    'r1_confirm_window': 10,
    'r2_breakout_vol_ratio': 1.5,
    'r2_pullback_vol_ratio': 0.6,
    'r2_pullback_window': 10,
    'r2_reaccel_vol_ratio': 1.2,
    'r2_persist_vol_ratio': 0.8,
    'death_break_pct': 0.97,
}

STATUS_SIGNAL_TODAY = '今日信号'
STATUS_WAIT_BREAK = '信号后等待突破SA'
STATUS_BREAK_TODAY = '今日突破SA'
STATUS_BREAK_NO_TOUCH = '已突破,回踩未到SB'
STATUS_R1_WAIT = '回踩中(等待两日温和放量)'
STATUS_R1 = '今日回踩完成→明日买入'          # 状态字与前端/旧链路保持一致
STATUS_R2_WAIT = '缩量回调中(等待二次起量)'
STATUS_R2 = '二次放量确认→明日买入'
BUY_STATUSES = (STATUS_R1, STATUS_R2)


class LadderMachine:
    """单票日线状态机。逐日 update()，返回当日状态 dict 或 None（无跟踪）。"""

    def __init__(self, params=None):
        self.p = dict(RULE_PARAMS)
        if params:
            self.p.update(params)
        self.track = None
        self._vol_hist = deque(maxlen=5)  # 前5日量（不含当日）→ MA5 量
        self._prev = None                 # 昨日 (close, low)

    def update(self, o, c, h, l, vol, sa, sb, sig, sig_type, date):
        p = self.p
        vma5 = (sum(self._vol_hist) / len(self._vol_hist)) if len(self._vol_hist) >= 5 else None
        out = None
        if sig:
            # 新信号覆盖旧跟踪（与既有状态机一致：最新信号起算）
            self.track = {
                'sig_date': date, 'sig_type': sig_type, 'days': 0,
                'breakout': False, 'b_day': None, 'V0': None, 'r2_armed': False,
                'r1_p': False, 'r1_since_p': 0, 'r1_run': 0, 'r1_run_touched': False,
                'r2_p': False, 'r2_d1': None,
            }
            out = self._emit(STATUS_SIGNAL_TODAY, c, sa, sb)
        elif self.track is not None:
            out = self._step(o, c, l, vol, sa, sb, vma5)
        self._vol_hist.append(vol if vol is not None else 0)
        self._prev = (c, l)
        return out

    def _step(self, o, c, l, vol, sa, sb, vma5):
        p, t = self.p, self.track
        t['days'] += 1
        if sb is not None and c < sb * p['death_break_pct']:
            self.track = None
            return None
        if not t['breakout']:
            if c > sa and t['days'] <= p['breakout_within_days']:
                t['breakout'] = True
                t['b_day'] = t['days']
                t['V0'] = vol
                t['r2_armed'] = bool(vma5 and vol >= p['r2_breakout_vol_ratio'] * vma5)
                return self._emit(STATUS_BREAK_TODAY, c, sa, sb)
            if t['days'] > p['breakout_within_days']:
                self.track = None
                return None
            return self._emit(STATUS_WAIT_BREAK, c, sa, sb)

        # ---- R1 缩量贴轨回踩 ----
        if (not t['r1_p']) and sb is not None and l <= sb * p['r1_touch_band_pct'] \
                and t['V0'] and vol <= p['r1_pullback_vol_ratio'] * t['V0']:
            t['r1_p'] = True
            t['r1_since_p'] = 0
        if t['r1_p']:
            t['r1_since_p'] += 1
            confirm = bool(vma5 and p['r1_mild_vol_low'] * vma5 <= vol <= p['r1_mild_vol_high'] * vma5
                           and c > o and sb is not None and c > sb)
            t['r1_run'] = t['r1_run'] + 1 if confirm else 0
            t['r1_run_touched'] = (t['r1_run_touched'] or l <= sb) if confirm else False
        r1_hit = t['r1_p'] and t['r1_run'] >= 2 and t['r1_run_touched']

        # ---- R2 缩量回梯内 → 二次起量 → 次日持续 ----
        r2_hit = False
        if t['r2_armed'] and not t['r2_p'] and t['V0'] \
                and (t['days'] - t['b_day']) <= p['r2_pullback_window'] \
                and vol <= p['r2_pullback_vol_ratio'] * t['V0'] and c < sa:
            t['r2_p'] = True
            t['r2_d1'] = None
        if t['r2_p']:
            if t['r2_d1'] is None:
                if vma5 and vol >= p['r2_reaccel_vol_ratio'] * vma5 and c > o \
                        and self._prev is not None and c > self._prev[0]:
                    t['r2_d1'] = {'vol': vol, 'low': l}
            else:
                if vol >= p['r2_persist_vol_ratio'] * t['r2_d1']['vol'] \
                        and self._prev is not None and c > self._prev[1]:
                    r2_hit = True
                t['r2_d1'] = None  # 持续检查后即消费：成功出信号/失败等待新起量日

        # ---- 状态裁决（同日双触发 R1 优先；触发后清空轨道）----
        if t['r1_p'] and t['r1_since_p'] > p['r1_confirm_window'] and t['r1_run'] < 2:
            self.track = None
            return None
        if r1_hit:
            out = self._emit(STATUS_R1, c, sa, sb)
        elif r2_hit:
            out = self._emit(STATUS_R2, c, sa, sb)
        elif t['r1_p']:
            out = self._emit(STATUS_R1_WAIT, c, sa, sb)
        elif t['r2_p']:
            out = self._emit(STATUS_R2_WAIT, c, sa, sb)
        else:
            out = self._emit(STATUS_BREAK_NO_TOUCH, c, sa, sb)
        if r1_hit or r2_hit:
            self.track = None
        return out

    def _emit(self, status, c, sa, sb):
        t = self.track
        return {'status': status, 'sig_type': t['sig_type'], 'sig_date': t['sig_date'],
                'close': c, 'sa': sa, 'sb': sb}


def eval_daily(df, params=None):
    """输入日线 DataFrame(date/open/close/high/low/volume/SA/SB/DXX/DXDX)，返回最后一日状态或 None。"""
    m = LadderMachine(params)
    last = None
    for row in df.itertuples(index=False):
        last = m.update(float(row.open), float(row.close), float(row.high), float(row.low),
                        float(row.volume), float(row.SA), float(row.SB),
                        bool(row.DXX or row.DXDX), 'DXDX' if row.DXDX else 'DXX', str(row.date))
    return last
```

- [ ] **Step 4: 跑测试确认通过**

```bash
cd /Users/zhangze/stockData && $PY -m pytest dsa_signal/tests/test_ladder_rules.py -q
```
预期：`5 passed`。若 `test_r1_full_path_triggers` 因 MA5 窗口均值未覆盖 110/115 而失败，把该两根 v 上调至 130/135（语义不变：落进 1.1–2.5×MA5 区间即可）。

- [ ] **Step 5: Commit**

```bash
cd /Users/zhangze/stockData/dsa_signal && git add ladder_rules.py tests && git commit -q -m "feat: ladder rules state machine with pullback-completion (R1) strict variant"
```

---

### Task 3: R2 路径与优先级测试

**Files:**
- Modify: `/Users/zhangze/stockData/dsa_signal/tests/test_ladder_rules.py`（追加）

- [ ] **Step 1: 追加 4 个失败/通过测试**

文件末尾追加：

```python
from dsa_signal.ladder_rules import STATUS_R2, STATUS_R2_WAIT  # noqa: E402


def _r2_tail(brk_vol=200, d1_vol=160, d2_vol=140):
    return _sig_then([
        {'o': 9.6, 'c': 10.2, 'l': 9.5, 'v': brk_vol},   # 起量突破(vma5=100, ≥1.5×)
        {'o': 10.1, 'c': 9.8, 'l': 9.7, 'v': 110},       # 缩量回梯内: 110≤0.6×200, c<SA
        {'o': 9.9, 'c': 10.3, 'l': 9.85, 'v': d1_vol},   # 二次起量: ≥1.2×MA5(≈122), 阳线过前收
        {'o': 10.3, 'c': 10.5, 'l': 10.0, 'v': d2_vol},  # 次日持续: ≥0.8×d1量, 收盘>d1低点
    ])


def test_r2_full_path_triggers():
    assert eval_daily(mkdf(_r2_tail()))['status'] == STATUS_R2


def test_r2_not_armed_without_breakout_volume():
    st = eval_daily(mkdf(_r2_tail(brk_vol=100)))['status']
    assert st != STATUS_R2  # 突破非起量 → R2 永不武装


def test_r2_persist_fail_not_triggered():
    st = eval_daily(mkdf(_r2_tail(d2_vol=100)))['status']
    assert st != STATUS_R2 and st == STATUS_R2_WAIT


def test_r1_wins_over_r2_same_day():
    # 回踩贴轨后, d1 恰好也是 R1 确认日, d2 同时满足 R1 第2确认日与 R2 持续日
    rows = _sig_then([
        {'o': 9.6, 'c': 10.2, 'l': 9.5, 'v': 200},       # 起量突破 V0=200
        {'o': 9.8, 'c': 9.2, 'l': 8.8, 'v': 110},        # 缩量贴轨(≤120) 收阴
        {'o': 9.1, 'c': 9.7, 'l': 8.9, 'v': 160},        # R1确认1(≥1.1×MA5≈105,阳,>SB) / R2回调? c<SA✗ → 不成R2回调
        {'o': 9.7, 'c': 10.0, 'l': 9.65, 'v': 150},      # R1确认2触发 → 优先 R1
    ])
    assert eval_daily(mkdf(rows))['status'] == STATUS_R1
```

- [ ] **Step 2: 跑测试**

```bash
cd /Users/zhangze/stockData && $PY -m pytest dsa_signal/tests/test_ladder_rules.py -q
```
预期：`9 passed`（Task 2 实现已含 R2；若 `test_r2_full_path_triggers` 因 MA5 数值未落区间失败，将 `d1_vol/d2_vol` 分别调为 170/140，保持"≥1.2×MA5 / ≥0.8×d1"语义）。

- [ ] **Step 3: Commit**

```bash
cd /Users/zhangze/stockData/dsa_signal && git add tests && git commit -q -m "test: R2 second-wave path, arming and R1-priority coverage"
```

---

### Task 4: 历史回放脚本 replay_rules.py（含旧口径对照）

**Files:**
- Create: `/Users/zhangze/stockData/dsa_signal/replay_rules.py`

- [ ] **Step 1: 实现回放（完整文件）**

```python
# -*- coding: utf-8 -*-
"""梯子规则历史回放：mrmc_cache_3y.pkl 全市场 3 年日线 → 买点事件 → 次日开盘买入 1/3/5 日胜率。

对照组 = 旧口径（单日触SB收阳，无收盘收复/量能要求），回答"收紧淘汰了哪些信号、它们表现如何"。
用法: python3 -m dsa_signal.replay_rules [--limit 50] [--codes 002673,600519] [--out DIR]
"""
import argparse
import csv
import os
import pickle
from datetime import datetime

from dsa_signal.config import DATA_DIR
from dsa_signal.ladder_rules import LadderMachine, RULE_PARAMS, STATUS_R1, STATUS_R2

CACHE_FILE = os.path.join(DATA_DIR, 'mrmc_cache_3y.pkl')
HORIZONS = (1, 3, 5)


def old_rule_machine(df):
    """复刻被取代前的日线旧口径（screen_signal.py.bak 的 breakout+单日 low<=SB+阳线 逻辑）。"""
    import numpy as np
    sig = (df['DXX'] | df['DXDX']).values
    sa = df['SA'].values
    sb = df['SB'].values
    c = df['close'].values.astype(float)
    o = df['open'].values.astype(float)
    l = df['low'].values.astype(float)
    dates = df['date'].values
    hits = []
    sig_idx, days, breakout = -1, 0, False
    for i in range(len(df)):
        if sig[i]:
            sig_idx, days, breakout = i, 0, False
            continue
        if sig_idx < 0:
            continue
        days += 1
        if not breakout and c[i] > sa[i] and days <= 5:
            breakout = True
        elif not breakout and days > 5:
            sig_idx = -1
            continue
        if breakout and l[i] <= sb[i] and c[i] > o[i]:
            hits.append(str(dates[i]))
            sig_idx, days, breakout = -1, 0, False
    return hits


def forward_returns(df, i):
    """信号日 i → 次日开盘买入；返回 {horizon: 收益率 或 None(数据不足)}"""
    if i + 1 >= len(df):
        return None
    entry = float(df['open'].iloc[i + 1])
    if entry <= 0:
        return None
    out = {}
    for k in HORIZONS:
        j = i + k
        out[k] = (float(df['close'].iloc[j]) / entry - 1) if j < len(df) else None
    return out


def scan(df, params=None):
    """feed 整段日线，收集触发日: [(date, status), ...]"""
    m = LadderMachine(params)
    hits = []
    for row in df.itertuples(index=False):
        st = m.update(float(row.open), float(row.close), float(row.high), float(row.low),
                      float(row.volume), float(row.SA), float(row.SB),
                      bool(row.DXX or row.DXDX), 'DXDX' if row.DXDX else 'DXX', str(row.date))
        if st and st['status'] in (STATUS_R1, STATUS_R2):
            hits.append((str(row.date), st['status']))
    return hits


def summarize(events, name):
    if not events:
        return f"{name}: 0 次触发"
    lines = [f"{name}: 共 {len(events)} 次触发"]
    for k in HORIZONS:
        rets = [e['ret'][k] for e in events if e['ret'] and e['ret'].get(k) is not None]
        if rets:
            win = sum(1 for r in rets if r > 0) / len(rets) * 100
            avg = sum(rets) / len(rets) * 100
            lines.append(f"  T+{k}日: 样本{len(rets)} 胜率{win:.1f}% 平均{avg:+.2f}%")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--limit', type=int, default=0, help='仅回放前N只（冒烟）')
    ap.add_argument('--codes', type=str, default='', help='逗号分隔指定代码')
    ap.add_argument('--out', type=str, default='')
    args = ap.parse_args()

    with open(CACHE_FILE, 'rb') as f:
        all_data = pickle.load(f)
    if args.codes:
        want = {c.strip() for c in args.codes.split(',')}
        all_data = {k: v for k, v in all_data.items() if k in want}
    if args.limit:
        all_data = dict(list(all_data.items())[:args.limit])
    out_dir = args.out or os.path.join(DATA_DIR, f"replay_{datetime.now():%Y%m%d_%H%M}")
    os.makedirs(out_dir, exist_ok=True)

    new_events, old_events = [], []
    for code, df in all_data.items():
        try:
            date_list = [str(x) for x in df['date'].values]
            for d, status in scan(df):
                i = date_list.index(d)
                new_events.append({'code': code, 'date': d, 'status': status,
                                   'ret': forward_returns(df, i)})
            for d in old_rule_machine(df):
                i = date_list.index(d)
                old_events.append({'code': code, 'date': d, 'ret': forward_returns(df, i)})
        except Exception:
            continue  # 单票数据异常不阻断回放

    new_keys = {(e['code'], e['date']) for e in new_events}
    old_keys = {(e['code'], e['date']) for e in old_events}
    eliminated = [e for e in old_events if (e['code'], e['date']) not in new_keys]

    print("=" * 62)
    print(f"回放: {len(all_data)} 只 | {datetime.now():%Y-%m-%d %H:%M}")
    print(summarize([e for e in new_events if e['status'] == STATUS_R1], "规则1 回踩完成(新口径)"))
    print(summarize([e for e in new_events if e['status'] == STATUS_R2], "规则2 二次放量确认"))
    print(summarize(old_events, "旧口径对照(单日触轨收阳)"))
    print(summarize(eliminated, "被新口径淘汰的旧信号"))
    print("=" * 62)
    for fn, rows in [('events_new.csv', new_events), ('events_old.csv', old_events)]:
        with open(os.path.join(out_dir, fn), 'w', newline='', encoding='utf-8-sig') as f:
            w = csv.writer(f)
            w.writerow(['code', 'date', 'status', 'ret1', 'ret3', 'ret5'])
            for e in rows:
                r = e.get('ret') or {}
                w.writerow([e['code'], e['date'], e.get('status', ''),
                            *(round(r[k], 4) if r.get(k) is not None else '' for k in HORIZONS)])
    print(f"明细已写入 {out_dir}")


if __name__ == '__main__':
    main()
```

- [ ] **Step 2: 冒烟回放（50 票）**

```bash
cd /Users/zhangze/stockData && $PY -m dsa_signal.replay_rules --limit 50 --out /tmp/replay_smoke
```
预期：打印统计表且无 traceback；`/tmp/replay_smoke/events_new.csv` 存在（触发数可为 0，属小样本正常）。

- [ ] **Step 3: Commit**

```bash
cd /Users/zhangze/stockData/dsa_signal && git add replay_rules.py && git commit -q -m "feat: historical replay with old-rule comparison and forward-return stats"
```

---

### Task 5: 全市场回放，人工评审报告（调参检查点）

- [ ] **Step 1: 全量回放（约数分钟，纯内存计算）**

```bash
cd /Users/zhangze/stockData && $PY -m dsa_signal.replay_rules
```
预期：打印"规则1 / 规则2 / 旧口径对照 / 被淘汰信号"四段胜率。

- [ ] **Step 1.5: 参数敏感性一行表（±20%）**

```bash
cd /Users/zhangze/stockData && $PY - <<'EOF'
import pickle
from dsa_signal.replay_rules import CACHE_FILE, scan, forward_returns
from dsa_signal.ladder_rules import RULE_PARAMS, STATUS_R1
base = {
 'r1_mild_low': dict(RULE_PARAMS, r1_mild_vol_low=RULE_PARAMS['r1_mild_vol_low']*0.8),
 'r1_mild_high': dict(RULE_PARAMS, r1_mild_vol_high=RULE_PARAMS['r1_mild_vol_high']*1.2),
 'r1_pull_vol': dict(RULE_PARAMS, r1_pullback_vol_ratio=RULE_PARAMS['r1_pullback_vol_ratio']*1.2),
 'r2_reaccel': dict(RULE_PARAMS, r2_reaccel_vol_ratio=RULE_PARAMS['r2_reaccel_vol_ratio']*0.8),
}
d = pickle.load(open(CACHE_FILE, 'rb'))
for name, params in [('基准', RULE_PARAMS)] + sorted(base.items()):
    n = r1 = w = tot = 0
    for code, df in d.items():
        dates = [str(x) for x in df['date'].values]
        hits = scan(df, params)
        r1 += sum(1 for _, s in hits if s == STATUS_R1)
        for dt, s in hits:
            fr = forward_returns(df, dates.index(dt))
            if fr and fr.get(5) is not None:
                tot += 1; w += fr[5] > 0
    print(f"{name:14s} R1触发{r1:5d}  T+5胜率{(w/tot*100 if tot else 0):5.1f}%  样本{tot}")
EOF
```
预期：5 行表（基准 + 4 个 ±20% 变体），触发数与胜率的走向关系供 Step 2 评审。

- [ ] **Step 2: 人工检查点（STOP，把报告+敏感性表原样转给用户）**

判定并交给用户决策：
- 新口径（R1）胜率是否 ≥ 旧口径；被淘汰信号胜率是否明显更差 → 是：参数定稿
- R1 3 年触发次数 < 20 → 提示用户考虑放宽 `r1_mild_vol_low`→1.0 或 `r1_pullback_vol_ratio`→0.7（改 `RULE_PARAMS` 后重跑本 Task，不改逻辑）
- 用户确认后才进入 Task 6

- [ ] **Step 3: Commit（如调过参数）**

```bash
cd /Users/zhangze/stockData/dsa_signal && git add ladder_rules.py && git commit -q -m "tune: ladder rule thresholds per replay win-rate report"
```

---

### Task 6: 接入 screen_signal.py（日线状态机替换）

**Files:**
- Modify: `/Users/zhangze/stockData/dsa_signal/screen_signal.py`（日线 `screen_daily` 内 ~113-190 行状态机段）
- 参照: `screen_signal.py.bak-20260915`

- [ ] **Step 1: 定位待替换段与输出窗口字面量**

```bash
cd /Users/zhangze/stockData/dsa_signal
grep -n "signal_idx\|dates\[signal_idx\]\|'今日信号'\|>= '" screen_signal.py | head -20
```
记下：日线循环体起止行（`for code, df_ in all_data.items():` 到该循环的 rows.append 结束）、输出过滤字面量（现为 `dates[signal_idx] >= '2026-07-29'`，若实际是动态表达式则原样搬运）。

- [ ] **Step 2: 替换日线循环体**

`for code, df_ in all_data.items():` 内、`dates[-1] != LAST` / ST / 市值过滤保持不变；从 `if sig[-1]:`（原 ~136 行）起到该循环输出 rows.append 的 else 分支结束（原 ~185 行）整段替换为：

```python
        from dsa_signal.ladder_rules import eval_daily, STATUS_SIGNAL_TODAY  # 保持本脚本就地延迟导入惯例
        res = eval_daily(df_)
        if res is None:
            continue
        name = df_['name'].values[-1]
        # 与旧行为一致: 今日信号无条件输出；其余状态要求信号日起在输出窗口内（窗口字面量沿用 Step 1 记录值）
        if res['status'] != STATUS_SIGNAL_TODAY and res['sig_date'] < '2026-07-29':
            continue
        rows.append({
            '股票代码': code, '股票名称': name, '信号状态': res['status'],
            '信号类型': res['sig_type'], '信号日期': res['sig_date'],
            '最新收盘价': round(float(df_['close'].values[-1]), 3),
            'NX_A上轨': round(float(df_['SA'].values[-1]), 3),
            'NX_B下轨': round(float(df_['SB'].values[-1]), 3),
        })
```
删除循环体中原 `open_/close/low/sa/sb/dxdx/dxx/sig = ...` 局部取数行（仅被已删除的旧状态机使用；若文件其它函数（如 `hot` 统计）仍引用这些变量则保留其定义）。`if sig[-1]` 分支不再需要——`eval_daily` 已返回"今日信号"。

- [ ] **Step 3: 单票离线验证（不发网络）**

```bash
cd /Users/zhangze/stockData && $PY -c "
import pickle
from dsa_signal.ladder_rules import eval_daily
d = pickle.load(open('mrmc_cache_3y.pkl','rb'))
for code in ('002673',):
    print(code, eval_daily(d[code]))
"
```
预期：西部证券输出状态**不再是**"今日回踩完成→明日买入"（其收盘 6.71 < SB 的新口径下最可能是 `回踩中(等待两日温和放量)` 或 None，取决于末日是否贴轨——只要不等于旧触发即为收紧生效）。

- [ ] **Step 4: 冒烟跑 screen（跳过网络步骤，直接调用函数）**

```bash
cd /Users/zhangze/stockData && $PY -c "
from dsa_signal.screen_signal import screen_daily
res = screen_daily('2026-09-15', set(), {}, None, None, True)   # 签名 (LAST, blacklist, caps, min_cap, max_cap, no_st_filter)
print(res[['股票代码','股票名称','信号状态']].head(10))
"
```
预期：正常返回 DataFrame，可含新状态字样（`screen_daily` 从本地 pickle 缓存读数，不发网络）。

- [ ] **Step 5: Commit**

```bash
cd /Users/zhangze/stockData/dsa_signal && git add screen_signal.py && git commit -q -m "feat: wire ladder_rules into daily screening, replacing legacy pullback-completion rule"
```

---

### Task 7: 前端买入态白名单 + 配色

**Files:**
- Modify: `apps/dsa-web/src/api/signalPipeline.ts`（5-19 行）
- Modify: `apps/dsa-web/src/pages/SignalPipelinePage.tsx`（~458 行配色）
- Test: `apps/dsa-web/src/api/__tests__/signalPipeline.test.ts`（新建）

- [ ] **Step 1: 写失败测试**

```ts
import { describe, expect, it } from 'vitest';
import { pickBuyTomorrow, BUY_TOMORROW_STATUSES } from '../signalPipeline';

const row = (status: string) => ({ '股票代码': '002673', '股票名称': 'X', '信号状态': status } as never);

describe('pickBuyTomorrow', () => {
  it('纳入回踩完成与二次放量两类买入态', () => {
    expect(BUY_TOMORROW_STATUSES).toEqual([
      '今日回踩完成→明日买入',
      '二次放量确认→明日买入',
    ]);
    const got = pickBuyTomorrow([
      row('今日回踩完成→明日买入'), row('二次放量确认→明日买入'), row('回踩中(等待两日温和放量)'),
    ]);
    expect(got).toHaveLength(2);
  });
});
```

```bash
cd apps/dsa-web && npm run test -- src/api/__tests__/signalPipeline.test.ts
```
预期：FAIL（`BUY_TOMORROW_STATUSES` 未导出）。

- [ ] **Step 2: 实现**

`signalPipeline.ts`：

```ts
export const BUY_TOMORROW_STATUS = '今日回踩完成→明日买入';
export const BUY_TOMORROW_STATUS_R2 = '二次放量确认→明日买入';
export const BUY_TOMORROW_STATUSES: string[] = [BUY_TOMORROW_STATUS, BUY_TOMORROW_STATUS_R2];
```
`pickBuyTomorrow` 中 `r['信号状态'] === BUY_TOMORROW_STATUS` → `BUY_TOMORROW_STATUSES.includes(r['信号状态'])`（保留旧导出名避免破坏其他引用）。

`SignalPipelinePage.tsx` 状态配色：

```ts
if (status.includes('回踩完成') || status.includes('二次放量')) return 'success';
```
（插在现有 `回踩完成` 判断行处，其余分支不动；`回踩中(` 前缀新文案已被现有 `includes('回踩中')→warning` 覆盖。）

- [ ] **Step 3: 验证**

```bash
cd apps/dsa-web && npm run test -- src/api/__tests__/signalPipeline.test.ts && npm run lint && npm run build
```
预期：新测试 PASS；lint 不新增 error（工作区遗留的 6 个既有 error 不属于本任务）；build 成功。

- [ ] **Step 4: CHANGELOG（主仓库工作区，不 commit）**

`docs/CHANGELOG.md` `[Unreleased]` 追加：

```markdown
- [新功能] 信号链日线新增"二次放量确认→明日买入"状态（起量破SA→缩量回梯→再放量→次日量能持续）
- [改进] "今日回踩完成→明日买入"收紧为两日温和放量收阳且收盘收复下轨的确认口径（参数见 dsa_signal/ladder_rules.py RULE_PARAMS，历史回放对照见 replay_rules）
- [新功能] 信号链买入候选横幅/筹码体检入口同时覆盖两类"明日买入"状态
```

---

### Task 8: 实跑流水线与端到端核对

- [ ] **Step 1: 收盘后实跑当日链（发真实网络，用户机器正常）**

```bash
cd /Users/zhangze/stockData && $PY -m dsa_signal.run_pipeline $(date +%Y%m%d)
```
预期：5 步全部 done，无 traceback；`signal_chain_YYYYMMDD.csv` 生成。

- [ ] **Step 2: 核对输出**

```bash
cd /Users/zhangze/stockData
grep -c "回踩完成" signal_chain_$(date +%Y%m%d).csv || true
grep -c "二次放量确认" signal_chain_$(date +%Y%m%d).csv || true
grep "002673" signal_chain_$(date +%Y%m%d).csv || echo "西部证券未出现/或状态非买入态"
```
预期：若出现 002673，其状态**不得**为"今日回踩完成→明日买入"（除非 09-15 当天真的两日温和放量收复下轨——人工对一眼 K 线再下结论）。

- [ ] **Step 3: 前端确认**

浏览器强刷 `http://127.0.0.1:8000/signal-pipeline`：新状态行正常渲染、横幅计数覆盖两类买入态、点击"开始体检"正常。

- [ ] **Step 4: 收尾提交（仅 dsa_signal 仓库）**

```bash
cd /Users/zhangze/stockData/dsa_signal && git status --short
```
无未提交改动即完成；主仓库改动（spec/plan/前端/CHANGELOG）保持工作区状态，由用户自行决定提交时机。

---

## 验收对照（spec → task）

| spec 条目 | Task |
|---|---|
| R1 状态机与失效 | 2 |
| R2 状态机/武装/优先级 | 3 |
| 回放报告含旧口径对照 | 4 |
| 参数评审检查点 | 5 |
| 日线接入（分钟链不动） | 6 |
| 前端白名单/配色/CHANGELOG | 7 |
| 实跑+西部证券锚点 | 6/8 |
| 备份与 git 基线 | 1 |
