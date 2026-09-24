# -*- coding: utf-8 -*-
"""B2-lite 免费新闻/公告源 adapter 测试(全 mock,无网络)。"""

import os
import sys
import unittest
from datetime import date
from unittest.mock import patch

import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from data_provider.free_news_adapter import FreeNewsAdapter

ADAPTER = FreeNewsAdapter()

NEWS_DF = pd.DataFrame({
    "关键词": ["600519"] * 2,
    "新闻标题": ["茅台发布中报", "茅台召开业绩说明会"],
    "新闻内容": ["净利润 445 亿。" + "x" * 300, "会议将于下周召开。"],
    "发布时间": ["2026-08-15 10:11:51", "2026-08-14 09:00:00"],
    "文章来源": ["东方财富网", "证券时报"],
    "新闻链接": ["https://e.com/a1", "https://e.com/a2"],
})

NOTICE_DF = pd.DataFrame({
    "代码": ["600519"] * 3,
    "名称": ["贵州茅台"] * 3,
    "公告标题": ["减持计划公告", "回购注销公告", "半年度报告摘要"],
    "公告类型": ["其他", "其他", "半年度报告摘要"],
    "公告日期": [date(2026, 9, 1), date(2026, 8, 20), date(2026, 8, 15)],
    "网址": ["https://d.com/n1", "https://d.com/n2", "https://d.com/n3"],
})


class TestGetStockNews(unittest.TestCase):
    def test_column_mapping_and_snippet_cap(self) -> None:
        with patch("akshare.stock_news_em", return_value=NEWS_DF):
            payload = ADAPTER.get_stock_news("600519")
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(len(payload["items"]), 2)
        first = payload["items"][0]
        self.assertEqual(first["title"], "茅台发布中报")
        self.assertEqual(len(first["snippet"]), 200)
        self.assertEqual(first["source"], "东方财富网")
        self.assertEqual(first["published_date"], "2026-08-15")

    def test_empty_df_is_ok(self) -> None:
        with patch("akshare.stock_news_em", return_value=pd.DataFrame()):
            payload = ADAPTER.get_stock_news("600519")
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["items"], [])

    def test_exception_failed(self) -> None:
        with patch("akshare.stock_news_em", side_effect=TimeoutError("t")):
            payload = ADAPTER.get_stock_news("600519")
        self.assertEqual(payload["status"], "failed")
        self.assertTrue(any("stock_news_em" in e for e in payload["errors"]))

    def test_missing_title_column_failed(self) -> None:
        with patch("akshare.stock_news_em", return_value=pd.DataFrame({"任意": [1]})):
            payload = ADAPTER.get_stock_news("600519")
        self.assertEqual(payload["status"], "failed")


class TestGetStockAnnouncements(unittest.TestCase):
    def test_mapping_and_sort_desc(self) -> None:
        with patch("akshare.stock_individual_notice_report", return_value=NOTICE_DF) as m:
            # 窗口解耦:fixture 为固定日期,避免随 today 滑出窗口
            payload = ADAPTER.get_stock_announcements("600519", days=36500)
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(len(payload["items"]), 3)
        self.assertEqual(payload["items"][0]["title"], "减持计划公告")
        self.assertEqual(payload["items"][0]["notice_type"], "其他")
        self.assertEqual(payload["items"][0]["date"], "2026-09-01")
        kwargs = m.call_args.kwargs
        self.assertIn("begin_date", kwargs)

    def test_keyword_filter(self) -> None:
        with patch("akshare.stock_individual_notice_report", return_value=NOTICE_DF):
            # 窗口解耦:fixture 为固定日期,避免随 today 滑出窗口
            payload = ADAPTER.get_stock_announcements("600519", days=36500, keyword="回购")
        self.assertEqual(payload["status"], "ok")
        self.assertEqual([i["title"] for i in payload["items"]], ["回购注销公告"])

    def test_days_window_filters_old(self) -> None:
        df = pd.DataFrame({
            "代码": ["600519"], "名称": ["贵州茅台"],
            "公告标题": ["三年前的旧公告"], "公告类型": ["其他"],
            "公告日期": [date(2020, 1, 1)], "网址": ["https://d.com/old"],
        })
        with patch("akshare.stock_individual_notice_report", return_value=df):
            payload = ADAPTER.get_stock_announcements("600519", days=90)
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["items"], [])

    def test_date_params_fail_retries_without_dates(self) -> None:
        with patch("akshare.stock_individual_notice_report",
                   side_effect=[TypeError("bad kw"), NOTICE_DF]) as m:
            payload = ADAPTER.get_stock_announcements("600519", days=3650)
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(m.call_count, 2)
        self.assertNotIn("begin_date", m.call_args_list[1].kwargs)

    def test_all_fail_failed(self) -> None:
        with patch("akshare.stock_individual_notice_report", side_effect=TypeError("bad kw")):
            payload = ADAPTER.get_stock_announcements("600519")
        self.assertEqual(payload["status"], "failed")


if __name__ == "__main__":
    unittest.main()
