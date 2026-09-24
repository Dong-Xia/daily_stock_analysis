# -*- coding: utf-8 -*-
"""信号链端点测试:CSV 加载回归 + 信号×基本面交集过滤。"""
import pandas as pd
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.v1.endpoints import signal_pipeline
from api.v1.endpoints.signal_pipeline import router
from src.services.fundamental_screener import FundamentalScreener


def _write_csv(tmp_path, name, rows):
    pd.DataFrame(rows).to_csv(tmp_path / name, index=False)


def _make_client(monkeypatch, tmp_path):
    monkeypatch.setattr(signal_pipeline, "STOCK_DATA_DIR", str(tmp_path))
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_results_reads_chain_csv(monkeypatch, tmp_path):
    _write_csv(tmp_path, "signal_chain_20260924.csv", [
        {"股票代码": "600519", "股票名称": "贵州茅台", "信号状态": "突破"},
        {"股票代码": "000429", "股票名称": "粤高速A", "信号状态": "回踩中"},
    ])
    client = _make_client(monkeypatch, tmp_path)

    r = client.get("/results", params={"date": "2026-09-24", "timeframe": "daily"})

    assert r.status_code == 200
    data = r.json()
    assert data["count"] == 2
    assert data["rows"][0]["股票代码"] == "600519"


def test_results_prefers_fundflow_csv(monkeypatch, tmp_path):
    _write_csv(tmp_path, "signal_chain_20260924.csv", [
        {"股票代码": "600519", "股票名称": "贵州茅台", "信号状态": "突破"},
    ])
    _write_csv(tmp_path, "signal_chain_20260924_fundflow.csv", [
        {"股票代码": "000429", "股票名称": "粤高速A", "信号状态": "回踩中", "当日主力占比%": "5.2"},
    ])
    client = _make_client(monkeypatch, tmp_path)

    r = client.get("/results", params={"date": "2026-09-24", "timeframe": "daily"})

    assert r.status_code == 200
    assert r.json()["count"] == 1
    assert r.json()["rows"][0]["股票代码"] == "000429"
    assert "当日主力占比" in r.json()["rows"][0]  # 列重命名仍生效


def test_results_intraday_suffix(monkeypatch, tmp_path):
    _write_csv(tmp_path, "signal_chain_20260924_5min.csv", [
        {"股票代码": "600519", "股票名称": "贵州茅台", "信号状态": "突破"},
    ])
    client = _make_client(monkeypatch, tmp_path)

    r = client.get("/results", params={"date": "2026-09-24", "timeframe": "5min"})

    assert r.status_code == 200
    assert r.json()["count"] == 1
    assert r.json()["timeframe_label"] == "5分钟"


def test_results_404_when_missing(monkeypatch, tmp_path):
    client = _make_client(monkeypatch, tmp_path)

    r = client.get("/results", params={"date": "2026-09-24", "timeframe": "daily"})

    assert r.status_code == 404


def _fund(code, rev=30.0, profit=80.0, net_yi=1.0, score=6.0):
    """get_pass_map 单项结构。"""
    return {
        "name": f"股票{code}",
        "revenue_yoy": rev,
        "profit_yoy": profit,
        "net_profit": net_yi * 1e8,
        "industry": "白酒",
        "composite_score": score,
    }


def test_fundamental_filter_intersection(monkeypatch, tmp_path):
    _write_csv(tmp_path, "signal_chain_20260924.csv", [
        {"股票代码": "600519", "股票名称": "贵州茅台", "信号状态": "突破"},
        {"股票代码": "000429", "股票名称": "粤高速A", "信号状态": "回踩中"},
        {"股票代码": "300750", "股票名称": "宁德时代", "信号状态": "等待"},
    ])
    monkeypatch.setattr(
        FundamentalScreener, "get_pass_map",
        lambda self, quarter_date=None: {
            "600519": _fund("600519"),
            "300750": _fund("300750", score=9.0),
        },
    )
    client = _make_client(monkeypatch, tmp_path)

    r = client.get("/fundamental-filter", params={"date": "2026-09-24", "timeframe": "daily"})

    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 3
    assert data["matched"] == 2
    assert [row["股票代码"] for row in data["rows"]] == ["600519", "300750"]  # 保持 CSV 原顺序
    row = data["rows"][0]
    assert row["股票名称"] == "贵州茅台"      # 原字段保留
    assert row["信号状态"] == "突破"
    assert row["营收同比%"] == "30.0"        # 增补字段为格式化字符串
    assert row["利润同比%"] == "80.0"
    assert row["净利润(亿)"] == "1.00"
    assert row["基本面评分"] == "6.0"
    assert data["quarter"] == FundamentalScreener._resolve_latest_quarter()


def test_fundamental_filter_no_match(monkeypatch, tmp_path):
    _write_csv(tmp_path, "signal_chain_20260924.csv", [
        {"股票代码": "600519", "股票名称": "贵州茅台", "信号状态": "突破"},
    ])
    monkeypatch.setattr(FundamentalScreener, "get_pass_map", lambda self, quarter_date=None: {})
    client = _make_client(monkeypatch, tmp_path)

    r = client.get("/fundamental-filter", params={"date": "2026-09-24", "timeframe": "daily"})

    assert r.status_code == 200
    assert r.json()["matched"] == 0
    assert r.json()["rows"] == []


def test_fundamental_filter_404_when_csv_missing(monkeypatch, tmp_path):
    client = _make_client(monkeypatch, tmp_path)

    r = client.get("/fundamental-filter", params={"date": "2026-09-24", "timeframe": "daily"})

    assert r.status_code == 404


def test_fundamental_filter_502_when_fetch_fails(monkeypatch, tmp_path):
    _write_csv(tmp_path, "signal_chain_20260924.csv", [
        {"股票代码": "600519", "股票名称": "贵州茅台", "信号状态": "突破"},
    ])

    def boom(self, quarter_date=None):
        raise RuntimeError("akshare down")

    monkeypatch.setattr(FundamentalScreener, "get_pass_map", boom)
    client = _make_client(monkeypatch, tmp_path)

    r = client.get("/fundamental-filter", params={"date": "2026-09-24", "timeframe": "daily"})

    assert r.status_code == 502
    assert "财报数据获取失败" in r.json()["detail"]


def test_fundamental_filter_invalid_timeframe(monkeypatch, tmp_path):
    client = _make_client(monkeypatch, tmp_path)

    r = client.get("/fundamental-filter", params={"date": "2026-09-24", "timeframe": "1h"})

    assert r.status_code == 400
