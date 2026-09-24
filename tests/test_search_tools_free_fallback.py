# -*- coding: utf- -*-
"""B2-lite:search_stock_news 免费源降级 + get_stock_announcements 工具测试(全 mock)。"""

import os
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.agent.tools.search_tools import _handle_search_stock_news, _handle_get_stock_announcements

FREE_NEWS_OK = {
    "status": "ok",
    "items": [
        {"title": "茅台发布中报", "snippet": "净利润 445 亿", "url": "https://e.com/a1",
         "source": "东方财富网", "published_date": "2026-08-15"},
    ],
    "errors": [],
}


def _engine_service(available=True, success=True):
    resp = SimpleNamespace(
        query="q", success=success, error_message=None if success else "引擎失败",
        provider="mock_engine", results=[SimpleNamespace(
            title="t", snippet="s", url="u", source="src", published_date="2026-08-15")],
    )
    return SimpleNamespace(
        is_available=available,
        search_stock_news=Mock(return_value=resp),
    )


class TestSearchStockNewsFallback(unittest.TestCase):
    def test_engine_unavailable_falls_back(self) -> None:
        adapter = Mock()
        adapter.get_stock_news.return_value = FREE_NEWS_OK
        with patch("src.agent.tools.search_tools._get_search_service",
                   return_value=_engine_service(available=False)), \
             patch("data_provider.free_news_adapter.get_free_news_adapter", return_value=adapter):
            out = _handle_search_stock_news("600519", "贵州茅台")
        self.assertTrue(out["success"])
        self.assertTrue(out["fallback"])
        self.assertEqual(out["provider"], "eastmoney_free")
        self.assertEqual(out["results"][0]["title"], "茅台发布中报")

    def test_engine_success_no_fallback(self) -> None:
        adapter = Mock()
        with patch("src.agent.tools.search_tools._get_search_service",
                   return_value=_engine_service(available=True, success=True)), \
             patch("data_provider.free_news_adapter.get_free_news_adapter", return_value=adapter):
            out = _handle_search_stock_news("600519", "贵州茅台")
        self.assertTrue(out["success"])
        self.assertNotIn("fallback", out)
        adapter.get_stock_news.assert_not_called()

    def test_engine_fail_falls_back(self) -> None:
        adapter = Mock()
        adapter.get_stock_news.return_value = FREE_NEWS_OK
        with patch("src.agent.tools.search_tools._get_search_service",
                   return_value=_engine_service(available=True, success=False)), \
             patch("data_provider.free_news_adapter.get_free_news_adapter", return_value=adapter):
            out = _handle_search_stock_news("600519", "贵州茅台")
        self.assertTrue(out["fallback"])

    def test_non_a_share_unsupported(self) -> None:
        adapter = Mock()
        with patch("src.agent.tools.search_tools._get_search_service",
                   return_value=_engine_service(available=False)), \
             patch("data_provider.free_news_adapter.get_free_news_adapter", return_value=adapter):
            out = _handle_search_stock_news("hk00700", "腾讯")
        self.assertFalse(out["success"])
        self.assertIn("A-shares", out["error"])
        adapter.get_stock_news.assert_not_called()

    def test_both_fail_structured_error(self) -> None:
        adapter = Mock()
        adapter.get_stock_news.return_value = {"status": "failed", "items": [], "errors": ["stock_news_em:TimeoutError"]}
        with patch("src.agent.tools.search_tools._get_search_service",
                   return_value=_engine_service(available=False)), \
             patch("data_provider.free_news_adapter.get_free_news_adapter", return_value=adapter):
            out = _handle_search_stock_news("600519", "贵州茅台")
        self.assertFalse(out["success"])
        self.assertIn("fallback_error", out)

    def test_fallback_empty_still_structured_error(self) -> None:
        adapter = Mock()
        adapter.get_stock_news.return_value = {"status": "ok", "items": [], "errors": []}
        with patch("src.agent.tools.search_tools._get_search_service",
                   return_value=_engine_service(available=False)), \
             patch("data_provider.free_news_adapter.get_free_news_adapter", return_value=adapter):
            out = _handle_search_stock_news("600519", "贵州茅台")
        self.assertFalse(out["success"])
        self.assertIn("no items", out["fallback_error"])

    def test_engine_and_fallback_item_schema_consistent(self) -> None:
        required = {"title", "snippet", "url", "source", "published_date"}
        adapter = Mock()
        adapter.get_stock_news.return_value = FREE_NEWS_OK
        with patch("src.agent.tools.search_tools._get_search_service",
                   return_value=_engine_service(available=True, success=True)):
            engine_out = _handle_search_stock_news("600519", "贵州茅台")
        with patch("src.agent.tools.search_tools._get_search_service",
                   return_value=_engine_service(available=False)), \
             patch("data_provider.free_news_adapter.get_free_news_adapter", return_value=adapter):
            fb_out = _handle_search_stock_news("600519", "贵州茅台")
        for out in (engine_out, fb_out):
            self.assertTrue(out["success"])
            for item in out["results"]:
                self.assertTrue(required.issubset(item.keys()), item.keys())


class TestGetStockAnnouncementsTool(unittest.TestCase):
    def test_a_share_ok(self) -> None:
        adapter = Mock()
        adapter.get_stock_announcements.return_value = {
            "status": "ok",
            "items": [{"date": "2026-09-01", "notice_type": "其他",
                       "title": "减持计划公告", "url": "https://d.com/n1"}],
            "errors": [],
        }
        with patch("data_provider.free_news_adapter.get_free_news_adapter", return_value=adapter):
            out = _handle_get_stock_announcements("600519", days=90, keyword="减持")
        self.assertTrue(out["success"])
        self.assertEqual(out["count"], 1)
        adapter.get_stock_announcements.assert_called_once_with("600519", days=90, keyword="减持")

    def test_non_a_share_unsupported(self) -> None:
        adapter = Mock()
        with patch("data_provider.free_news_adapter.get_free_news_adapter", return_value=adapter):
            out = _handle_get_stock_announcements("hk00700")
        self.assertFalse(out["success"])
        adapter.get_stock_announcements.assert_not_called()

    def test_adapter_failed(self) -> None:
        adapter = Mock()
        adapter.get_stock_announcements.return_value = {"status": "failed", "items": [], "errors": ["x:E"]}
        with patch("data_provider.free_news_adapter.get_free_news_adapter", return_value=adapter):
            out = _handle_get_stock_announcements("600519")
        self.assertFalse(out["success"])

    def test_items_capped_at_100_with_truncated_flag(self) -> None:
        adapter = Mock()
        adapter.get_stock_announcements.return_value = {
            "status": "ok",
            "items": [{"date": "2026-09-01", "notice_type": "其他", "title": f"公告{i}", "url": "u"} for i in range(150)],
            "errors": [],
        }
        with patch("data_provider.free_news_adapter.get_free_news_adapter", return_value=adapter):
            out = _handle_get_stock_announcements("600519")
        self.assertEqual(out["count"], 100)
        self.assertTrue(out["truncated"])
        self.assertEqual(len(out["announcements"]), 100)


class TestMarketGateBoundary(unittest.TestCase):
    """门控采用仓库标准市场判定(normalize_stock_code + _market_tag)后的边界契约。"""

    def test_prefixed_and_suffixed_a_share_pass(self) -> None:
        adapter = Mock()
        adapter.get_stock_news.return_value = FREE_NEWS_OK
        with patch("src.agent.tools.search_tools._get_search_service",
                   return_value=_engine_service(available=False)), \
             patch("data_provider.free_news_adapter.get_free_news_adapter", return_value=adapter):
            out = _handle_search_stock_news("SH600519", "贵州茅台")
        self.assertTrue(out.get("fallback"))

    def test_bse_92_prefix_passes(self) -> None:
        adapter = Mock()
        adapter.get_stock_announcements.return_value = {"status": "ok", "items": [], "errors": []}
        with patch("data_provider.free_news_adapter.get_free_news_adapter", return_value=adapter):
            out = _handle_get_stock_announcements("920748")
        self.assertTrue(out["success"])
        adapter.get_stock_announcements.assert_called_once()
        # 传给 adapter 的是归一化后的代码
        self.assertEqual(adapter.get_stock_announcements.call_args.args[0], "920748")

    def test_bare_hk_code_rejected(self) -> None:
        adapter = Mock()
        with patch("src.agent.tools.search_tools._get_search_service",
                   return_value=_engine_service(available=False)), \
             patch("data_provider.free_news_adapter.get_free_news_adapter", return_value=adapter):
            out = _handle_search_stock_news("00700", "腾讯")
        self.assertFalse(out["success"])
        self.assertIn("A-shares", out["error"])
        adapter.get_stock_news.assert_not_called()

    def test_gate_error_not_retriable(self) -> None:
        with patch("src.agent.tools.search_tools._get_search_service",
                   return_value=_engine_service(available=False)):
            out = _handle_search_stock_news("hk00700", "腾讯")
        self.assertFalse(out["success"])
        self.assertIs(out.get("retriable"), False)


if __name__ == "__main__":
    unittest.main()
