# -*- coding: utf-8 -*-
"""
持仓筹码体检服务（本地三年日线离线筹码引擎）

与 ENABLE_CHIP_DISTRIBUTION（在线筹码分布快照，供单股分析上下文）不同，
本模块基于本地 3 年日线数据库（stockData/mrmc_cache_3y.pkl）自行重建筹码分布，
按回测验证的规则输出减仓判定：
  🔴 底筹连降7日且累计流失>18% | 🟠 连降5日>15% | 🟡 连降3日>8%
  ⚪ 3日流失>8%但非逐日(量化做T假象, 勿卖) | 🟢 稳定/增加
规则依据: stockData/筹码策略回测报告.md (v2, 2023-2026, 5.7万涨停事件+374万交易日)。

筹码引擎逻辑来自 stockData/chip_health_check.py（已验证版本），本文件为程序内独立实现，
数据目录通过 CHIP_STOCK_DATA_DIR 环境变量配置。

命令行: python3 -m src.services.chip_health_service --holdings-file <csv> --json
  stdout 仅输出结果 JSON，日志走 stderr（供服务层 subprocess 解析）。
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# ---------------- 配置 ----------------
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
HOLDINGS_FILE = DATA_DIR / "chip_holdings.csv"

STOCK_DATA_DIR = os.getenv("CHIP_STOCK_DATA_DIR", "/Users/zhangze/stockData")
RUN_TIMEOUT_SEC = int(os.getenv("CHIP_HEALTH_TIMEOUT", "600"))

N_BINS = 240
CLEAN_CUTOFF = "2026-08-01"
WINDOWS = {"7天确认": (7, 0.18), "5天确认": (5, 0.15), "3天确认": (3, 0.08)}


class ChipHealthError(Exception):
    """体检业务错误（数据缺失/超时/解析失败等），endpoint 映射为 4xx/5xx。"""


# ---------------- 持仓清单持久化 ----------------
def load_saved_holdings() -> List[Dict[str, Any]]:
    if not HOLDINGS_FILE.exists():
        return []
    h = pd.read_csv(HOLDINGS_FILE, dtype={"code": str})
    h["code"] = h["code"].astype(str).str.strip().str.zfill(6)
    for col in ("name", "cost"):
        if col not in h.columns:
            h[col] = ""
    return [
        {"code": r["code"], "name": "" if pd.isna(r["name"]) else str(r["name"]),
         "cost": None if pd.isna(r["cost"]) else float(r["cost"])}
        for _, r in h.iterrows()
    ]


def save_holdings(rows: List[Dict[str, Any]]) -> int:
    DATA_DIR.mkdir(exist_ok=True)
    df = pd.DataFrame(
        [{"code": str(r.get("code", "")).strip().zfill(6),
          "name": str(r.get("name") or ""),
          "cost": r.get("cost") if r.get("cost") not in ("", None) else np.nan}
         for r in rows if str(r.get("code", "")).strip()]
    )
    df.to_csv(HOLDINGS_FILE, index=False, encoding="utf-8-sig")
    return len(df)


# ---------------- 筹码引擎（与回测同口径） ----------------
def _fix_volume(sub: pd.DataFrame) -> pd.Series:
    """成交量单位自校正：历史库为"手"，个别采集路径曾写成"股"(×100)。
    以本票干净期(2026-08-01前)中位量为基准，窗口内>25倍判为单位错误÷100。"""
    vol = sub["volume"].astype(float).copy()
    clean = vol[sub["date"] < CLEAN_CUTOFF]
    if len(clean) < 20:
        return vol
    ref_med = clean.median()
    if ref_med > 0:
        infl = vol > 25 * ref_med
        vol[infl] = vol[infl] / 100.0
    return vol


def _chip_series(sub: pd.DataFrame, shares: Optional[float]) -> pd.DataFrame:
    """三角分布+换手衰减，返回每日 (date, profit获利比例, bottom底部筹码占比)。"""
    close = sub["close"].to_numpy(float)
    opn = sub["open"].to_numpy(float)
    high = sub["high"].to_numpy(float)
    low = sub["low"].to_numpy(float)
    vol = sub["volume"].fillna(0).to_numpy(float)
    dates = sub["date"].to_numpy()
    n = len(sub)
    to = np.clip(vol * 100 / shares, 0, 1) if shares and shares > 0 else np.zeros(n)
    low60 = pd.Series(low).rolling(60, min_periods=20).min().to_numpy()

    pmin, pmax = low.min() * 0.98, high.max() * 1.02
    if pmax <= pmin:
        return pd.DataFrame()
    edges = np.linspace(pmin, pmax, N_BINS + 1)
    centers = 0.5 * (edges[:-1] + edges[1:])
    binw = edges[1] - edges[0]
    chips = np.zeros(N_BINS)

    rows = []
    for i in range(n):
        h = to[i]
        if h > 0:
            chips *= (1.0 - h)
        if vol[i] > 0 and high[i] >= low[i]:
            lo, hi_, av = low[i], high[i], (opn[i] + close[i] + high[i] + low[i]) / 4.0
            mass = h
            if mass > 0:
                if hi_ - lo < binw * 0.5:
                    b = min(max(int((lo - pmin) / binw), 0), N_BINS - 1)
                    chips[b] += mass
                else:
                    b_lo = max(int((lo - pmin) / binw), 0)
                    b_hi = min(int((hi_ - pmin) / binw), N_BINS - 1)
                    if b_hi <= b_lo:
                        chips[b_lo] += mass
                    else:
                        bs = np.arange(b_lo, b_hi + 1)
                        w = np.where(centers[bs] <= av,
                                     (centers[bs] - lo) / max(av - lo, 1e-9),
                                     (hi_ - centers[bs]) / max(hi_ - av, 1e-9))
                        w = np.clip(w, 0, None)
                        s = w.sum()
                        if s > 0:
                            chips[bs] += mass * w / s
        tot = chips.sum()
        if tot > 1e-9 and close[i] > 0:
            # 获利比例: 档中心<=现价才计为获利(对齐通达信口径; 现价压在筹码峰上时边界档不计入)
            profit = chips[centers <= close[i]].sum() / tot
            if np.isfinite(low60[i]):
                bottom = chips[centers < low60[i] * 1.15].sum() / tot
            else:
                bottom = np.nan
            rows.append((dates[i], profit, bottom))
    return pd.DataFrame(rows, columns=["date", "profit", "bottom"])


def _diagnose(cs: pd.DataFrame):
    """返回 (级别emoji, 结论, 数值明细)。级别: 🔴/🟠/🟡/⚪/🟢/—"""
    if len(cs) < 60:
        return ("—", "历史数据不足60天，无法判断", {})
    b = cs["bottom"].to_numpy()
    profit = float(cs["profit"].iloc[-1])

    def mono(k):
        seg = b[-k:]
        return all(seg[j] < seg[j - 1] for j in range(1, k))

    def loss(k):
        return float(b[-k] - b[-1]) if len(b) >= k else np.nan

    hit = None
    for name, (k, th) in WINDOWS.items():
        if len(b) >= k and mono(k) and loss(k) > th:
            hit = (name, loss(k))
            break

    detail = {
        "profit": round(profit, 4),
        "bottom": round(float(b[-1]), 4),
        "loss3": round(loss(3), 4) if np.isfinite(loss(3)) else None,
        "loss5": round(loss(5), 4) if np.isfinite(loss(5)) else None,
        "loss7": round(loss(7), 4) if np.isfinite(loss(7)) else None,
    }
    if hit:
        name, lv = hit
        msg = {"7天确认": "底筹连降7日，主力大概率派发，强烈建议减仓",
               "5天确认": "底筹连降5日，建议减仓",
               "3天确认": "底筹连降3日，警惕观察"}[name]
        return ({"7天确认": "🔴", "5天确认": "🟠", "3天确认": "🟡"}[name],
                f"{msg}（累计流失{lv:.0%}）", detail)
    if np.isfinite(loss(3)) and loss(3) > 0.08:
        return ("⚪", f"单日骤减后回补（3日净流失{loss(3):.0%}），疑似量化做T假象，不必恐慌卖出", detail)
    if np.isfinite(loss(3)) and loss(3) < -0.03:
        return ("🟢", f"底筹近3日反而增加{-loss(3):.0%}，资金吸筹，可继续持有", detail)
    return ("🟢", "底筹稳定，无明显派发，可继续持有", detail)


# ---------------- 批量计算 ----------------
def compute(holdings: List[Dict[str, Any]]) -> Dict[str, Any]:
    cache_file = Path(STOCK_DATA_DIR) / "mrmc_cache_3y.pkl"
    mc_file = Path(STOCK_DATA_DIR) / "market_cap_latest.csv"
    if not cache_file.exists():
        raise ChipHealthError(f"指标缓存不存在: {cache_file}（请先在数据目录跑收盘流水线）")
    if not mc_file.exists():
        raise ChipHealthError(f"市值快照不存在: {mc_file}")

    logger.info("筹码体检: 载入缓存 %s", cache_file)
    cache = pd.read_pickle(cache_file)
    mc = pd.read_csv(mc_file, dtype={"code": str})
    mc["code"] = mc["code"].str.zfill(6)
    mc_map = mc.set_index("code")["market_cap"].to_dict()
    mc_date = str(mc["date"].iloc[0])

    results, skipped = [], []
    data_cutoff = ""
    for r in holdings:
        code = str(r.get("code", "")).strip().zfill(6)
        if not code or code == "000000":
            continue
        v = cache.get(code)
        if v is None or len(v) < 60:
            skipped.append({"code": code, "name": str(r.get("name") or ""),
                            "reason": "缓存无数据或上市历史太短"})
            continue
        v = v.sort_values("date").copy()
        v["volume"] = _fix_volume(v)
        name = str(r.get("name") or (v["name"].iloc[-1] if "name" in v.columns else ""))

        shares = None
        mcap = mc_map.get(code)
        mc_close = v.loc[v["date"].astype(str) == mc_date, "close"]
        if mcap and not pd.isna(mcap) and len(mc_close):
            shares = float(mcap) * 1e8 / float(mc_close.iloc[0])

        cs = _chip_series(v, shares)
        if cs.empty:
            skipped.append({"code": code, "name": name, "reason": "筹码计算失败"})
            continue
        lvl, verdict, det = _diagnose(cs)
        last_close = float(v["close"].iloc[-1])
        cost = r.get("cost")
        pnl = last_close / float(cost) - 1 if cost not in (None, "",) and float(cost) > 0 else None
        ret5 = last_close / float(v["close"].iloc[-6]) - 1 if len(v) >= 6 else None
        ddate = str(v["date"].iloc[-1])
        data_cutoff = max(data_cutoff, ddate)
        results.append({
            "code": code, "name": name, "data_date": ddate,
            "close": round(last_close, 3),
            "cost": float(cost) if cost not in (None, "") else None,
            "pnl": round(pnl, 4) if pnl is not None else None,
            "ret5": round(ret5, 4) if ret5 is not None else None,
            "level": lvl, "verdict": verdict, **det,
            "high_profit_risk": bool(det.get("profit", 0) > 0.90),
        })
    return {"data_cutoff": data_cutoff, "results": results, "skipped": skipped}


# ---------------- 服务入口（subprocess隔离1GB缓存内存） ----------------
def run_check(holdings: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    rows = holdings if holdings is not None else load_saved_holdings()
    if not rows:
        raise ChipHealthError("持仓清单为空，请先在页面填写并保存持仓")

    DATA_DIR.mkdir(exist_ok=True)
    tmp = DATA_DIR / ".chip_holdings_run.csv"
    pd.DataFrame([{"code": str(x.get("code", "")).zfill(6),
                   "name": x.get("name") or "", "cost": x.get("cost") or np.nan}
                  for x in rows]).to_csv(tmp, index=False, encoding="utf-8-sig")
    try:
        cmd = [sys.executable, "-m", "src.services.chip_health_service",
               "--holdings-file", str(tmp), "--json"]
        logger.info("筹码体检子进程: %s", " ".join(cmd))
        proc = subprocess.run(cmd, cwd=str(PROJECT_ROOT), capture_output=True,
                              text=True, timeout=RUN_TIMEOUT_SEC)
    finally:
        tmp.unlink(missing_ok=True)

    if proc.returncode != 0:
        raise ChipHealthError(f"体检进程失败(exit={proc.returncode}): {proc.stderr[-500:]}")
    line = [l for l in proc.stdout.splitlines() if l.strip().startswith("{")]
    if not line:
        raise ChipHealthError(f"未解析到结果JSON: {proc.stdout[:200]}")
    out = json.loads(line[-1])
    out["generated_at"] = pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S")
    return out


def status() -> Dict[str, Any]:
    from datetime import datetime as _dt
    cache_file = Path(STOCK_DATA_DIR) / "mrmc_cache_3y.pkl"
    info = {
        "data_dir": STOCK_DATA_DIR,
        "cache_exists": cache_file.exists(),
        # 本地时区(fromtimestamp), 勿用 Timestamp(unit='s')——那是UTC会差8小时
        "cache_mtime": (_dt.fromtimestamp(cache_file.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
                        if cache_file.exists() else None),
        "holdings_count": len(load_saved_holdings()),
        "holdings_file": str(HOLDINGS_FILE),
    }
    return info


# ---------------- 模块CLI（subprocess入口） ----------------
def cli_main() -> int:
    import argparse
    ap = argparse.ArgumentParser(description="筹码体检引擎(CLI, 供服务层subprocess调用)")
    ap.add_argument("--holdings-file", required=True)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    h = pd.read_csv(args.holdings_file, dtype={"code": str})
    h["code"] = h["code"].astype(str).str.strip().str.zfill(6)
    if "cost" not in h.columns:
        h["cost"] = None
    holdings = [{"code": r["code"], "name": "" if pd.isna(r.get("name")) else str(r.get("name")),
                 "cost": None if pd.isna(r["cost"]) else float(r["cost"])} for _, r in h.iterrows()]
    out = compute(holdings)
    print(json.dumps(out, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(cli_main())
