# -*- coding: utf-8 -*-
"""Unit tests for AkshareFetcher.get_realtime_quotes_batch_tencent (腾讯批量实时行情)."""
import logging

import pytest
import requests

from data_provider.akshare_fetcher import AkshareFetcher, TENCENT_REALTIME_ENDPOINT


class _DummyCircuitBreaker:
    def __init__(self):
        self.failures = []
        self.successes = []

    def is_available(self, source: str) -> bool:
        return True

    def record_success(self, source: str) -> None:
        self.successes.append(source)

    def record_failure(self, source: str, error=None) -> None:
        self.failures.append((source, error))


class _DummyResponse:
    def __init__(self, status_code: int, text: str):
        self.status_code = status_code
        self.text = text
        self.encoding = None


def _tencent_line(symbol: str, name: str, price: str, change_pct: str, turnover: str) -> str:
    fields = ["0"] * 50
    fields[1] = name
    fields[3] = price
    fields[4] = "5.00"
    fields[31] = "0.19"
    fields[32] = change_pct
    fields[38] = turnover
    return f'v_{symbol}="{"~".join(fields)}";'


@pytest.fixture
def akshare_fetcher(monkeypatch):
    fetcher = AkshareFetcher()
    monkeypatch.setattr(fetcher, "_enforce_rate_limit", lambda: None)
    return fetcher


def test_batch_parses_multiple_symbols(monkeypatch, akshare_fetcher):
    """一次响应含多标的时应全部解析，字段映射与单只口径一致。"""
    breaker = _DummyCircuitBreaker()
    monkeypatch.setattr("data_provider.akshare_fetcher.get_realtime_circuit_breaker", lambda: breaker)
    payload = (
        _tencent_line("sz300080", "易成新能", "3.66", "0.27", "0.23")
        + _tencent_line("sh601126", "四方股份", "38.89", "-1.54", "0.56")
        + 'v_sz000000="";'  # 无效标的：空载荷应被跳过
    )
    monkeypatch.setattr(
        "data_provider.akshare_fetcher.requests.get",
        lambda *args, **kwargs: _DummyResponse(200, payload),
    )

    result = akshare_fetcher.get_realtime_quotes_batch_tencent(["300080", "601126", "000000"])

    assert set(result.keys()) == {"300080", "601126"}
    assert result["300080"].name == "易成新能"
    assert result["300080"].price == 3.66
    assert result["300080"].change_pct == 0.27
    assert result["300080"].turnover_rate == 0.23
    assert result["300080"].source.value == "tencent"
    assert result["601126"].price == 38.89
    assert result["601126"].change_pct == -1.54
    assert breaker.successes == ["akshare_tencent"]


def test_batch_http_error_keeps_going_and_reports_failure(monkeypatch, akshare_fetcher):
    """HTTP 非 200 的分块应记录熔断失败且不产出结果。"""
    breaker = _DummyCircuitBreaker()
    monkeypatch.setattr("data_provider.akshare_fetcher.get_realtime_circuit_breaker", lambda: breaker)
    monkeypatch.setattr(
        "data_provider.akshare_fetcher.requests.get",
        lambda *args, **kwargs: _DummyResponse(502, ""),
    )

    result = akshare_fetcher.get_realtime_quotes_batch_tencent(["300080", "601126"])

    assert result == {}
    assert breaker.failures
    source_key, message = breaker.failures[0]
    assert source_key == "akshare_tencent"
    assert "HTTP 502" in message


def test_batch_exception_records_failure(monkeypatch, akshare_fetcher):
    breaker = _DummyCircuitBreaker()
    monkeypatch.setattr("data_provider.akshare_fetcher.get_realtime_circuit_breaker", lambda: breaker)

    def _raise_disconnect(*args, **kwargs):
        raise requests.exceptions.ConnectionError("Remote end closed connection without response")

    monkeypatch.setattr("data_provider.akshare_fetcher.requests.get", _raise_disconnect)

    result = akshare_fetcher.get_realtime_quotes_batch_tencent(["300080"])

    assert result == {}
    source_key, message = breaker.failures[0]
    assert "category=remote_disconnect" in message


def test_batch_chunks_requests(monkeypatch, akshare_fetcher):
    """超过 chunk_size 的代码列表应拆分为多次请求。"""
    monkeypatch.setattr("data_provider.akshare_fetcher.get_realtime_circuit_breaker", lambda: _DummyCircuitBreaker())
    calls = []

    def _fake_get(url, *args, **kwargs):
        calls.append(url)
        return _DummyResponse(200, "")

    monkeypatch.setattr("data_provider.akshare_fetcher.requests.get", _fake_get)

    codes = [f"3000{i:02d}" for i in range(7)]
    akshare_fetcher.get_realtime_quotes_batch_tencent(codes, chunk_size=3)

    assert len(calls) == 3  # 7 只按 3/批拆为 3 次
