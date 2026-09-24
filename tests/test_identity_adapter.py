# -*- coding: utf-8 -*-
"""B1 身份痕迹块 adapter 方法测试(全 mock,无网络)。"""

import os
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from data_provider.base import DataFetcherManager
from data_provider.fundamental_adapter import AkshareFundamentalAdapter

ADAPTER = AkshareFundamentalAdapter()

HOLDER_DF = pd.DataFrame({
    "代码": ["600519"] * 4,
    "股东户数统计截止日": ["2025-12-31", "2026-03-31", "2026-06-30", "2026-08-31"],
    "股东户数-本次": [52000, 55000, 60000, 48000],
    "股东户数-增减比例": [-3.0, 5.77, 9.09, -20.0],
    "户均持股数量": [20833.0, 19700.0, 18000.0, 22500.0],
    "户均持股市值": [2.9e6, 3.1e6, 3.3e6, 3.2e6],
})


class TestHolderCountSeries(unittest.TestCase):
    def _run(self, df):
        with patch.object(ADAPTER, "_call_df_candidates", return_value=(df, "stock_zh_a_gdhs", [])):
            return ADAPTER.get_holder_count_series("600519")

    def test_series_and_trend_concentrating(self) -> None:
        df = HOLDER_DF.copy()
        df["股东户数-增减比例"] = [-3.0, 5.77, -5.0, -20.0]
        result = self._run(df)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["trend"], "concentrating")
        self.assertEqual(result["latest"]["holder_num"], 48000)
        self.assertEqual(len(result["series"]), 4)
        self.assertEqual(result["series"][0]["end_date"], "20251231")

    def test_trend_dispersing(self) -> None:
        df = HOLDER_DF.copy()
        df["股东户数-增减比例"] = [-3.0, 5.0, 9.09, 20.0]
        result = self._run(df)
        self.assertEqual(result["trend"], "dispersing")

    def test_trend_flat_mixed(self) -> None:
        df = HOLDER_DF.copy()
        df["股东户数-增减比例"] = [-3.0, 5.0, -9.09, 20.0]
        result = self._run(df)
        self.assertEqual(result["trend"], "flat")

    def test_none_df_returns_not_supported(self) -> None:
        with patch.object(ADAPTER, "_call_df_candidates", return_value=(None, None, ["x:Err"])):
            result = ADAPTER.get_holder_count_series("600519")
        self.assertNotEqual(result["status"], "ok")
        self.assertEqual(result["series"], [])
        self.assertIn("x:Err", result["errors"])

    def test_series_capped_at_8(self) -> None:
        rows = 12
        df = pd.DataFrame({
            "代码": ["600519"] * rows,
            "股东户数统计截止日": [f"2025-{m:02d}-28" for m in range(1, 13)],
            "股东户数-本次": [50000 + i * 100 for i in range(rows)],
            "股东户数-增减比例": [1.0] * rows,
        })
        result = self._run(df)
        self.assertEqual(len(result["series"]), 8)
        self.assertEqual(result["series"][0]["end_date"], "20250528")

    def test_code_filter_excludes_other_stocks(self) -> None:
        df = HOLDER_DF.copy()
        df["代码"] = "600000"
        result = self._run(df)  # 全部行是他股,过滤后空 → partial
        self.assertEqual(result["status"], "partial")

    def test_missing_columns_partial(self) -> None:
        df = pd.DataFrame({"任意列": [1, 2]})
        result = self._run(df)
        self.assertEqual(result["status"], "partial")

    def test_nat_date_rows_skipped(self) -> None:
        df = HOLDER_DF.copy()
        df.loc[df.index[-1], "股东户数统计截止日"] = None
        result = self._run(df)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(len(result["series"]), 3)


MARGIN_DF_SSE = pd.DataFrame({
    "信用交易日期": ["2026-09-22", "2026-09-22"],
    "标的证券代码": ["600519", "600000"],
    "标的证券简称": ["贵州茅台", "浦发银行"],
    "融资余额": [2.1e9, 1.5e9],
    "融资买入额": [3.0e8, 2.0e8],
})


def _identity_cfg(**over):
    cfg = SimpleNamespace(
        enable_fundamental_pipeline=True,
        fundamental_cache_ttl_seconds=120,
        fundamental_cache_max_entries=256,
        fundamental_stage_timeout_seconds=0.01,
        fundamental_fetch_timeout_seconds=0.01,
        fundamental_retry_max=1,
        enable_holder_count_context=False,
        enable_margin_balance_context=False,
        enable_block_deals_context=False,
        identity_stage_timeout_seconds=5.0,
        identity_fetch_timeout_seconds=2.0,
        identity_cache_ttl_seconds=21600,
    )
    for k, v in over.items():
        setattr(cfg, k, v)
    return cfg


class TestMarginBalanceContext(unittest.TestCase):
    def setUp(self) -> None:
        self.manager = DataFetcherManager(fetchers=[])

    def test_sse_routing_and_two_days(self) -> None:
        fetch = Mock(return_value=MARGIN_DF_SSE)
        with patch.object(self.manager._fundamental_adapter, "fetch_margin_df", side_effect=fetch), \
                patch("src.config.get_config", return_value=_identity_cfg()):
            block = self.manager.get_margin_balance_context("600519")
        self.assertEqual(block["status"], "ok")
        self.assertAlmostEqual(block["data"]["latest"]["rzye_yi"], 21.0)
        self.assertIsNotNone(block["data"]["latest"]["change_pct_1d"])
        self.assertEqual(fetch.call_count, 2)

    def test_market_level_cache_shared_across_stocks(self) -> None:
        fetch = Mock(return_value=MARGIN_DF_SSE)
        with patch.object(self.manager._fundamental_adapter, "fetch_margin_df", side_effect=fetch), \
                patch("src.config.get_config", return_value=_identity_cfg()):
            self.manager.get_margin_balance_context("600519")
            self.manager.get_margin_balance_context("600519")
            block = self.manager.get_margin_balance_context("600000")
        self.assertEqual(block["status"], "ok")
        self.assertEqual(fetch.call_count, 2)  # 同日市场级缓存命中,不再发请求

    def test_non_trading_fallback_partial(self) -> None:
        fetch = Mock(side_effect=[None, MARGIN_DF_SSE] + [None] * 5)
        with patch.object(self.manager._fundamental_adapter, "fetch_margin_df", side_effect=fetch), \
                patch("src.config.get_config", return_value=_identity_cfg()):
            block = self.manager.get_margin_balance_context("600519")
        self.assertEqual(block["status"], "partial")
        self.assertIsNone(block["data"]["latest"]["change_pct_1d"])

    def test_bse_not_supported(self) -> None:
        fetch = Mock()
        with patch.object(self.manager._fundamental_adapter, "fetch_margin_df", side_effect=fetch), \
                patch("src.config.get_config", return_value=_identity_cfg()):
            block = self.manager.get_margin_balance_context("830799")
        self.assertEqual(block["status"], "not_supported")
        fetch.assert_not_called()

    def test_all_days_failed(self) -> None:
        fetch = Mock(return_value=None)
        with patch.object(self.manager._fundamental_adapter, "fetch_margin_df", side_effect=fetch), \
                patch("src.config.get_config", return_value=_identity_cfg()):
            block = self.manager.get_margin_balance_context("600519")
        self.assertEqual(block["status"], "failed")


def _dzjy_df(rates, code="600519"):
    # rates 语义与 ak.stock_dzjy_mrmx 真机一致:折溢率为小数(-0.095 = -9.5%)
    return pd.DataFrame({
        "交易日期": ["2026-09-18"] * len(rates),
        "证券代码": [code] * len(rates),
        "证券简称": ["贵州茅台"] * len(rates),
        "成交价": [1500.0] * len(rates),
        "成交量": [100000] * len(rates),
        "成交额": [1.5e8] * len(rates),
        "折溢率": rates,
    })


class TestBlockDealsContext(unittest.TestCase):
    def setUp(self) -> None:
        self.manager = DataFetcherManager(fetchers=[])

    def _block(self, frames_by_probe):
        # 探测从最近一天开始依次调用;frames_by_probe 为按调用序的 frame 列表(None=该日无数据)
        with patch.object(
            self.manager._fundamental_adapter, "fetch_block_deals_df", side_effect=frames_by_probe
        ), patch("src.config.get_config", return_value=_identity_cfg()):
            return self.manager.get_block_deals_context("600519")

    def test_signal_narrowing(self) -> None:
        # 探测序 d0..d4;d0/d1(最近 2 日)收窄,d2/d3/d4(最早 3 日)深折价(阈值 -8/-5 作用于 ×100 后的百分数)
        frames = [_dzjy_df([-0.01]), _dzjy_df([-0.01]), _dzjy_df([-0.095]), _dzjy_df([-0.095]), _dzjy_df([-0.095])]
        block = self._block(frames)
        self.assertEqual(block["data"]["signal_note"], "narrowing")

    def test_signal_deep_discount(self) -> None:
        frames = [_dzjy_df([-0.095])] * 5
        block = self._block(frames)
        self.assertEqual(block["data"]["signal_note"], "deep_discount")

    def test_signal_premium(self) -> None:
        frames = [_dzjy_df([0.005])] * 5
        block = self._block(frames)
        self.assertEqual(block["data"]["signal_note"], "premium")

    def test_signal_normal(self) -> None:
        frames = [_dzjy_df([-0.01])] * 5
        block = self._block(frames)
        self.assertEqual(block["data"]["signal_note"], "normal")

    def test_signal_none_when_stock_absent(self) -> None:
        frames = [_dzjy_df([-0.095], code="600000")] * 5
        block = self._block(frames)
        self.assertEqual(block["data"]["signal_note"], "none")
        self.assertEqual(block["data"]["recent_5d"]["deal_count"], 0)

    def test_multi_deal_aggregation(self) -> None:
        # 首日两笔 + 后 4 日各一笔 = 6 笔;每笔 1.5e8 元 = 1.5 亿,总 6 笔 = 9.0 亿
        frames = [_dzjy_df([-0.095, -0.005])] + [_dzjy_df([-0.01])] * 4
        block = self._block(frames)
        d = block["data"]
        self.assertEqual(d["recent_5d"]["deal_count"], 6)
        self.assertAlmostEqual(d["recent_5d"]["total_amount_yi"], 9.0, places=2)
        self.assertEqual(d["latest"]["premium_rate"], -9.5)
        self.assertEqual(d["signal_note"], "deep_discount")

    def test_missing_premium_column_normal(self) -> None:
        df = _dzjy_df([-0.01]).drop(columns=["折溢率"])
        frames = [df] * 5
        block = self._block(frames)
        self.assertEqual(block["data"]["signal_note"], "normal")
        self.assertIsNone(block["data"]["recent_5d"]["avg_premium_rate"])
        self.assertEqual(block["data"]["recent_5d"]["deal_count"], 5)

    def test_failed_when_no_frame(self) -> None:
        block = self._block([None] * 10)
        self.assertEqual(block["status"], "failed")
        # 可观测性:failed 块 errors 非空
        self.assertTrue(block["errors"])


class TestMarginObservability(unittest.TestCase):
    def setUp(self) -> None:
        self.manager = DataFetcherManager(fetchers=[])

    def test_budget_zero_failed_fast(self) -> None:
        fetch = Mock()
        with patch.object(self.manager._fundamental_adapter, "fetch_margin_df", side_effect=fetch), \
                patch("src.config.get_config", return_value=_identity_cfg()):
            block = self.manager.get_margin_balance_context("600519", budget_seconds=0)
        self.assertEqual(block["status"], "failed")
        fetch.assert_not_called()

    def test_szse_routing(self) -> None:
        df = MARGIN_DF_SSE.copy()
        df.loc[df.index[0], "标的证券代码"] = "000001"  # fixture 含本股,status 才可为 ok
        fetch = Mock(return_value=df)
        with patch.object(self.manager._fundamental_adapter, "fetch_margin_df", side_effect=fetch), \
                patch("src.config.get_config", return_value=_identity_cfg()):
            block = self.manager.get_margin_balance_context("000001")
        self.assertEqual(block["status"], "ok")
        # 探测的日期参数里 market 由调用方传入 fetch_margin_df 的第一个参数决定
        markets = {call.args[0] for call in fetch.call_args_list}
        self.assertEqual(markets, {"szse"})


class TestHolderCountContextBlock(unittest.TestCase):
    def setUp(self) -> None:
        self.manager = DataFetcherManager(fetchers=[])

    def test_block_maps_payload(self) -> None:
        payload = {
            "status": "ok",
            "latest": {"end_date": "20260831", "holder_num": 48000, "holder_num_change_pct": -20.0},
            "series": [{"end_date": "20260831", "holder_num": 48000, "holder_num_change_pct": -20.0}],
            "trend": "concentrating",
            "source_chain": ["holder_count:stock_zh_a_gdhs_detail_em"],
            "errors": [],
        }
        with patch.object(self.manager._fundamental_adapter, "get_holder_count_series", return_value=payload), \
                patch("src.config.get_config", return_value=_identity_cfg()):
            block = self.manager.get_holder_count_context("600519")
        self.assertEqual(block["status"], "ok")
        self.assertEqual(block["data"]["trend"], "concentrating")
        self.assertIn("reading_note", block["data"])

    def test_adapter_failure_failed_block(self) -> None:
        with patch.object(self.manager._fundamental_adapter, "get_holder_count_series", return_value=None), \
                patch("src.config.get_config", return_value=_identity_cfg()):
            block = self.manager.get_holder_count_context("600519")
        self.assertEqual(block["status"], "failed")

    def test_holder_block_cached_per_stock(self) -> None:
        payload = {"status": "ok", "latest": {}, "series": [], "trend": "flat", "source_chain": [], "errors": []}
        call = Mock(return_value=payload)
        with patch.object(self.manager._fundamental_adapter, "get_holder_count_series", side_effect=call), \
                patch("src.config.get_config", return_value=_identity_cfg()):
            b1 = self.manager.get_holder_count_context("600519")
            b2 = self.manager.get_holder_count_context("600519")
        self.assertEqual(b1, b2)
        self.assertEqual(call.call_count, 1)  # 个股级 TTL 缓存命中,第二次不发请求


class TestIdentityWiring(unittest.TestCase):
    def setUp(self) -> None:
        self.manager = DataFetcherManager(fetchers=[])

    def test_switches_off_no_requests(self) -> None:
        holder = Mock()
        margin = Mock()
        dzjy = Mock()
        with patch.object(self.manager._fundamental_adapter, "get_holder_count_series", side_effect=holder), \
                patch.object(self.manager._fundamental_adapter, "fetch_margin_df", side_effect=margin), \
                patch.object(self.manager._fundamental_adapter, "fetch_block_deals_df", side_effect=dzjy), \
                patch("src.config.get_config", return_value=_identity_cfg()):
            ctx = self.manager.get_fundamental_context("600519")
        holder.assert_not_called()
        margin.assert_not_called()
        dzjy.assert_not_called()
        self.assertEqual(ctx["coverage"].get("holder_count"), "not_supported")
        self.assertEqual(ctx["coverage"].get("margin_balance"), "not_supported")
        self.assertEqual(ctx["coverage"].get("block_deals"), "not_supported")

    def test_switch_on_blocks_injected(self) -> None:
        payload = {
            "status": "ok",
            "latest": {"end_date": "20260831", "holder_num": 48000},
            "series": [],
            "trend": "concentrating",
            "source_chain": [],
            "errors": [],
        }
        cfg = _identity_cfg(enable_holder_count_context=True)
        with patch.object(self.manager._fundamental_adapter, "get_holder_count_series", return_value=payload), \
                patch("src.config.get_config", return_value=cfg):
            ctx = self.manager.get_fundamental_context("600519")
        self.assertEqual(ctx["coverage"].get("holder_count"), "ok")
        self.assertEqual(ctx["holder_count"]["data"]["trend"], "concentrating")

    def test_all_three_switches_on(self) -> None:
        holder_payload = {"status": "ok", "latest": {}, "series": [], "trend": "flat",
                          "source_chain": [], "errors": []}
        cfg = _identity_cfg(
            enable_holder_count_context=True,
            enable_margin_balance_context=True,
            enable_block_deals_context=True,
        )
        margin_df = MARGIN_DF_SSE.copy()
        dzjy_frame = _dzjy_df([-0.01])
        with patch.object(self.manager._fundamental_adapter, "get_holder_count_series", return_value=holder_payload), \
                patch.object(self.manager._fundamental_adapter, "fetch_margin_df", return_value=margin_df), \
                patch.object(self.manager._fundamental_adapter, "fetch_block_deals_df", return_value=dzjy_frame), \
                patch("src.config.get_config", return_value=cfg):
            ctx = self.manager.get_fundamental_context("600519")
        self.assertEqual(ctx["coverage"].get("holder_count"), "ok")
        self.assertEqual(ctx["coverage"].get("margin_balance"), "ok")
        self.assertEqual(ctx["coverage"].get("block_deals"), "ok")

    def test_etf_identity_blocks_not_supported(self) -> None:
        holder = Mock()
        with patch.object(self.manager._fundamental_adapter, "get_holder_count_series", side_effect=holder), \
                patch("src.config.get_config", return_value=_identity_cfg(enable_holder_count_context=True)):
            ctx = self.manager.get_fundamental_context("563230")
        self.assertEqual(ctx["coverage"].get("holder_count"), "not_supported")
        holder.assert_not_called()


if __name__ == "__main__":
    unittest.main()
