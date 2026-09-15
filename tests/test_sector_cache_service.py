# -*- coding: utf-8 -*-
"""SectorCacheService 回归测试：连接必须关闭（fd 泄漏）+ 读写往返（commit 语义）。"""
import sqlite3

import pytest

from src.services.sector_cache_service import SectorCacheService


def _make_service(tmp_path) -> SectorCacheService:
    return SectorCacheService(db_path=str(tmp_path / "sector_cache_test.db"))


def test_get_conn_closes_connection(tmp_path, monkeypatch):
    """每次 with self._get_conn() 之后底层连接必须被关闭，防止长驻进程 fd 泄漏。"""
    captured = []
    real_connect = sqlite3.connect

    def spy_connect(*args, **kwargs):
        conn = real_connect(*args, **kwargs)
        captured.append(conn)
        return conn

    monkeypatch.setattr(sqlite3, "connect", spy_connect)
    svc = _make_service(tmp_path)  # __init__ 里的 _init_db 也走 _get_conn
    assert captured
    for conn in captured:
        with pytest.raises(sqlite3.ProgrammingError):
            conn.cursor()  # 已关闭的连接上调用会抛 ProgrammingError

    captured.clear()
    svc.get_meta("missing_key")
    assert captured
    with pytest.raises(sqlite3.ProgrammingError):
        captured[-1].cursor()


def test_board_members_roundtrip(tmp_path):
    svc = _make_service(tmp_path)
    svc.set_board_members(
        "半导体", "industry",
        [{"code": "600519", "name": "测试股", "price": 10.5, "change_pct": 1.2}],
    )
    rows = svc.get_board_members("半导体", "industry")
    assert rows and rows[0]["code"] == "600519"
    assert svc.is_cache_fresh("半导体", "industry")
    assert svc.get_board_members("不存在板块", "industry") is None


def test_sector_rankings_roundtrip(tmp_path):
    svc = _make_service(tmp_path)
    assert svc.get_sector_rankings() is None
    svc.set_sector_rankings([{"name": "半导体", "change_pct": 3.1}], [{"name": "银行", "change_pct": -1.0}])
    result = svc.get_sector_rankings()
    assert result is not None
    top, bottom = result
    assert top[0]["name"] == "半导体"
    assert bottom[0]["name"] == "银行"
    age = svc.get_sector_rankings_age_hours()
    assert age is not None and age < 1


def test_meta_roundtrip_and_clear(tmp_path):
    svc = _make_service(tmp_path)
    svc.set_meta("k1", "v1")
    assert svc.get_meta("k1") == "v1"
    assert svc.get_meta("missing", default="d") == "d"
    svc.clear_cache()
    assert svc.get_meta("k1") is None
