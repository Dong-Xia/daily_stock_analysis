# -*- coding: utf-8 -*-
"""
东方财富隐藏 JSON 接口数据获取

基于 push2.eastmoney.com 的轻量 JSON API，避开复杂网页解析。
内置强制降频：每次请求后随机休眠 2-5 秒，连续失败后指数退避。

扩展支持：概念板块排行、涨停板池、人气榜、资金流、北向资金、赚钱效应。
所有数据均通过浏览器模拟（Session + User-Agent + Referer）获取，
分页查询 + 低频访问，避免触发反爬。
"""

import logging
import random
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import requests

from .base import BaseFetcher, DataFetchError

logger = logging.getLogger(__name__)

_BASE_URL = "https://push2.eastmoney.com/api/qt/clist/get"
_BASE_URL_V2 = "https://push2his.eastmoney.com/api/qt/clist/get"
_MIN_SLEEP = 2.0
_MAX_SLEEP = 5.0
_FAILURE_BACKOFF_BASE = 5.0

_FS_INDUSTRY = "m:90+t:2"
_FS_CONCEPT = "m:90+t:3"
_FS_LIMIT_UP = "m:93+t:1"
_FS_HOT_STOCK = "m:1+t:2+f:!50"

_COMMON_FIELDS = "f2,f3,f4,f5,f6,f7,f8,f10,f12,f14,f15,f16,f17,f18,f20,f21"
_LIMIT_UP_EXTRA = "f184,f152"
_FUND_FLOW_FIELDS = "f12,f14,f3,f62,f64,f66,f69,f70,f184"


class EmHiddenApiFetcher(BaseFetcher):
    name = "EmHiddenApiFetcher"
    priority = 1

    def __init__(self) -> None:
        self._session = requests.Session()
        self._session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                ),
                "Accept": "application/json, text/javascript, */*; q=0.01",
                "Accept-Language": "zh-CN,zh;q=0.9",
                "Referer": "https://quote.eastmoney.com/center/gridlist.html",
            }
        )
        self._consecutive_failures = 0

    def _sleep(self) -> None:
        base = random.uniform(_MIN_SLEEP, _MAX_SLEEP)
        if self._consecutive_failures > 0:
            base += _FAILURE_BACKOFF_BASE * (2 ** (self._consecutive_failures - 1))
        sleep_sec = min(base, 60.0)
        logger.debug(f"[EmHiddenApi] 休眠 {sleep_sec:.1f}s")
        time.sleep(sleep_sec)

    def _request(self, params: Dict[str, Any], base_url: str = _BASE_URL) -> Optional[Dict[str, Any]]:
        self._sleep()
        try:
            resp = self._session.get(base_url, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            if data.get("data") is None:
                self._consecutive_failures += 1
                logger.warning(f"[EmHiddenApi] 返回空数据: {params.get('fs')}")
                return None
            self._consecutive_failures = 0
            return data
        except Exception as e:
            self._consecutive_failures += 1
            logger.warning(f"[EmHiddenApi] 请求失败: {e}")
            return None

    def _paginated_request(self, params: Dict[str, Any], max_pages: int = 5,
                           base_url: str = _BASE_URL) -> List[Dict]:
        """分页查询，控制频率，逐页拉取"""
        all_items: List[Dict] = []
        for page in range(1, max_pages + 1):
            params["pn"] = page
            data = self._request(dict(params), base_url=base_url)
            if not data:
                break
            diff = data.get("data", {}).get("diff", [])
            if not diff:
                break
            all_items.extend(diff)
            total = data.get("data", {}).get("total", 0)
            fetched = page * params.get("pz", 200)
            if fetched >= total:
                break
        return all_items

    def get_sector_rankings(self, n: int = 5) -> Optional[Tuple[List[Dict], List[Dict]]]:
        params = {
            "pn": 1,
            "pz": 200,
            "po": 1,
            "np": 1,
            "fltt": 2,
            "invt": 2,
            "fid": "f3",
            "fs": "m:90+t:2",
            "fields": "f12,f14,f2,f3,f4,f5,f6,f7,f8,f9,f10,f18,f20,f21",
        }
        data = self._request(params)
        if not data:
            return None

        diff = data.get("data", {}).get("diff", [])
        sectors = []
        for item in diff:
            sectors.append(
                {
                    "code": item.get("f12", ""),
                    "name": item.get("f14", ""),
                    "price": item.get("f2", 0),
                    "change_pct": item.get("f3", 0),
                    "change_amount": item.get("f4", 0),
                    "volume": item.get("f5", 0),
                    "amount": item.get("f6", 0),
                    "amplitude": item.get("f7", 0),
                    "turnover_rate": item.get("f8", 0),
                }
            )

        sectors_sorted = sorted(sectors, key=lambda x: x["change_pct"] or 0, reverse=True)
        top = sectors_sorted[:n]
        bottom = sectors_sorted[-n:][::-1]
        return top, bottom

    def get_board_members(self, board_name: str, board_type: str = "industry") -> Optional[pd.DataFrame]:
        board_code = self._resolve_board_code(board_name, board_type)
        if not board_code:
            return None

        params = {
            "pn": 1,
            "pz": 500,
            "po": 1,
            "np": 1,
            "fltt": 2,
            "invt": 2,
            "fid": "f12",
            "fs": f"b:{board_code}",
            "fields": "f12,f14,f2,f3,f4,f5,f6,f7,f8,f9,f10,f18,f20,f21",
        }
        data = self._request(params)
        if not data:
            return None

        diff = data.get("data", {}).get("diff", [])
        if not diff:
            return None

        records = []
        for item in diff:
            code = item.get("f12", "")
            if code and str(code).strip():
                records.append(
                    {
                        "code": str(code).strip(),
                        "name": item.get("f14", ""),
                        "price": item.get("f2", 0) or 0,
                        "change_pct": item.get("f3", 0) or 0,
                        "volume": item.get("f5", 0) or 0,
                        "amount": item.get("f6", 0) or 0,
                    }
                )

        if not records:
            return None

        df = pd.DataFrame(records)
        logger.info(f"[EmHiddenApi] 板块 {board_name}({board_code}) 成分股: {len(df)} 只")
        return df

    def _resolve_board_code(self, board_name: str, board_type: str) -> Optional[str]:
        cache_key = f"_em_board_codes_{board_type}"
        if not hasattr(self, cache_key):
            fs_param = "m:90+t:2" if board_type == "industry" else "m:90+t:3"
            params = {
                "pn": 1,
                "pz": 500,
                "po": 1,
                "np": 1,
                "fltt": 2,
                "invt": 2,
                "fid": "f12",
                "fs": fs_param,
                "fields": "f12,f14",
            }
            data = self._request(params)
            mapping = {}
            if data:
                for item in data.get("data", {}).get("diff", []):
                    code = item.get("f12", "")
                    name = item.get("f14", "")
                    if code and name:
                        mapping[name] = code
            setattr(self, cache_key, mapping)
            logger.info(f"[EmHiddenApi] 缓存 {board_type} 板块代码映射: {len(mapping)} 个")

        mapping = getattr(self, cache_key, {})
        target = board_name.strip()

        if target in mapping:
            return mapping[target]

        for name, code in mapping.items():
            if target in name or name in target:
                return code

        logger.warning(f"[EmHiddenApi] 未找到板块 '{target}' 的代码映射")
        return None

    def _fetch_raw_data(self, stock_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        raise NotImplementedError("EmHiddenApiFetcher 不支持日线数据获取")

    def _normalize_data(self, df: pd.DataFrame, stock_code: str) -> pd.DataFrame:
        return df

    def is_available(self) -> bool:
        return True

    # ================================================================
    #  热点板块扩展方法（浏览器模拟 + 分页 + 低频访问）
    # ================================================================

    def get_concept_board_rankings(self, n: int = 20) -> Optional[Tuple[List[Dict], List[Dict]]]:
        """
        获取概念板块涨跌榜（浏览器模拟）

        数据源：push2.eastmoney.com → fs=m:90+t:3
        """
        params = {
            "pn": 1, "pz": 200, "po": 1, "np": 1, "fltt": 2, "invt": 2,
            "fid": "f3", "fs": _FS_CONCEPT,
            "fields": f"{_COMMON_FIELDS},{_FUND_FLOW_FIELDS}",
        }
        data = self._request(params)
        if not data:
            return None

        diff = data.get("data", {}).get("diff", [])
        sectors = []
        for item in diff:
            sectors.append({
                "code": item.get("f12", ""),
                "name": item.get("f14", ""),
                "change_pct": item.get("f3", 0) or 0,
                "price": item.get("f2", 0) or 0,
            })

        sectors_sorted = sorted(sectors, key=lambda x: x["change_pct"], reverse=True)
        logger.info(f"[EmHiddenApi] 概念板块排行: {len(sectors_sorted)} 个板块")
        return sectors_sorted[:n], sectors_sorted[-n:][::-1]

    def get_hot_rankings(self, n: int = 30) -> Optional[List[Dict]]:
        """
        获取人气榜 Top N（浏览器模拟）

        数据源：push2.eastmoney.com → A 股人气排行
        """
        params = {
            "pn": 1, "pz": n, "po": 1, "np": 1, "fltt": 2, "invt": 2,
            "fid": "f3", "fs": _FS_HOT_STOCK,
            "fields": _COMMON_FIELDS,
        }
        data = self._request(params)
        if not data:
            return None

        diff = data.get("data", {}).get("diff", [])
        result = []
        for rank, item in enumerate(diff, 1):
            result.append({
                "rank": rank,
                "code": str(item.get("f12", "")),
                "name": str(item.get("f14", "")),
                "price": float(item.get("f2", 0) or 0),
                "change_pct": float(item.get("f3", 0) or 0),
            })
        logger.info(f"[EmHiddenApi] 人气榜: {len(result)} 条")
        return result

    def get_limit_up_pool(self, date: Optional[str] = None) -> Optional[pd.DataFrame]:
        """
        获取涨停板池（浏览器模拟 + 分页）

        数据源优先级：
        1. push2ex.eastmoney.com/getTopicZTPool（涨停股池专用接口）
        2. push2.eastmoney.com → fs=m:93+t:1（clist通用接口）
        单页最多 200 条，支持分页获取全量。
        """
        if date is None:
            date = datetime.now().strftime("%Y%m%d")

        # 方式1: 使用涨停板池专用接口
        import random as _random
        try:
            self._sleep()
            zt_params = {
                "ut": "7eea3edcaed734bea9cbfc24409ed989",
                "dpt": "wz.ztzt",
                "Pageindex": 0,
                "pagesize": 200,
                "sort": "fbt:asc",
                "date": date,
                "_": int(time.time() * 1000),
            }
            resp = self._session.get(
                "https://push2ex.eastmoney.com/getTopicZTPool",
                params=zt_params,
                timeout=15,
            )
            resp.raise_for_status()
            zt_data = resp.json()
            pool = zt_data.get("data", {}).get("pool", [])
            if pool:
                records = []
                for item in pool:
                    records.append({
                        "code": str(item.get("c", "")),
                        "name": str(item.get("n", "")),
                        "change_pct": float(item.get("zdp", 0) or 0),
                        "price": float(item.get("p", 0) or 0) / 1000,
                        "amount": float(item.get("amount", 0) or 0),
                        "circ_mv": float(item.get("ltsz", 0) or 0),
                        "total_mv": float(item.get("tsz", 0) or 0),
                        "turnover_rate": float(item.get("hs", 0) or 0),
                        "consecutive_days": int(item.get("lbc", 0) or 0),
                        "industry": str(item.get("hybk", "")),
                        "first_seal_time": str(item.get("fbt", "")),
                        "last_seal_time": str(item.get("lbt", "")),
                        "break_count": int(item.get("zbc", 0) or 0),
                        "seal_amount": float(item.get("fdje", 0) or 0),
                    })
                df = pd.DataFrame(records)
                logger.info(f"[EmHiddenApi] 涨停板池(ZT专用接口): {len(df)} 只")
                return df
        except Exception as e:
            logger.debug(f"[EmHiddenApi] ZT专用接口失败: {e}，回退到clist通用接口")

        # 方式2: 回退到 clist 通用接口（A股全量 + 涨幅筛选）
        # fs: 所有A股 (沪深京), f184=主力净流入占比非连板数
        params = {
            "pn": 1, "pz": 100, "po": 1, "np": 1, "fltt": 2, "invt": 2,
            "fid": "f3", "fs": "m:0+t:6,m:0+t:13,m:0+t:80,m:1+t:2,m:1+t:23,m:0+t:81+s:2048",
            "fields": f"{_COMMON_FIELDS},f184,f124,f152,f177,f111",
        }
        items = self._paginated_request(params, max_pages=3)
        if not items:
            logger.warning(f"[EmHiddenApi] 涨停板池 {date} 返回空数据")
            return None

        records = []
        for item in items:
            change_pct = float(item.get("f3", 0) or 0)
            if change_pct < 9.5:  # 非涨停/接近涨停
                continue
            records.append({
                "code": str(item.get("f12", "")),
                "name": str(item.get("f14", "")),
                "change_pct": change_pct,
                "price": float(item.get("f2", 0) or 0),
                "amount": float(item.get("f6", 0) or 0),
                "circ_mv": float(item.get("f21", 0) or 0),
                "total_mv": float(item.get("f20", 0) or 0),
                "turnover_rate": float(item.get("f8", 0) or 0),
                "consecutive_days": 0,
                "limit_up_price": float(item.get("f2", 0) or 0),
            })
        df = pd.DataFrame(records) if records else pd.DataFrame()
        logger.info(f"[EmHiddenApi] 涨停板池(clist): {len(df)} 只")
        return df if not df.empty else None

    def get_concept_fund_flow_rank(self, indicator: str = "今日") -> Optional[pd.DataFrame]:
        """
        获取概念板块资金流向排名（浏览器模拟）

        数据源：push2.eastmoney.com → fs=m:90+t:3, fid=f62 (主力净流入)
        """
        params = {
            "pn": 1, "pz": 200, "po": 1, "np": 1, "fltt": 2, "invt": 2,
            "fid": "f62", "fs": _FS_CONCEPT,
            "fields": f"f12,f14,f3,f62,f64,f66,f69,f70,f184",
        }
        data = self._request(params)
        if not data:
            return None

        diff = data.get("data", {}).get("diff", [])
        if not diff:
            logger.warning("[EmHiddenApi] 概念板块资金流返回空数据")
            return None

        records = []
        for item in diff:
            name = str(item.get("f14", ""))
            if not name:
                continue
            super_large = float(item.get("f64", 0) or 0)
            large = float(item.get("f66", 0) or 0)
            records.append({
                "名称": name,
                "板块名称": name,
                "name": name,
                "涨跌幅": float(item.get("f3", 0) or 0),
                "主力净流入": float(item.get("f62", 0) or 0),
                "超大单净流入": super_large,
                "大单净流入": large,
                "中单净流入": float(item.get("f70", 0) or 0),
                "小单净流入": float(item.get("f69", 0) or 0),
            })
        df = pd.DataFrame(records)
        logger.info(f"[EmHiddenApi] 概念板块资金流: {len(df)} 条")
        return df

    def get_industry_fund_flow_rank(self, indicator: str = "今日") -> Optional[pd.DataFrame]:
        """
        获取行业板块资金流向排名（浏览器模拟）

        数据源：push2.eastmoney.com → fs=m:90+t:2, fid=f62 (主力净流入)
        """
        params = {
            "pn": 1, "pz": 200, "po": 1, "np": 1, "fltt": 2, "invt": 2,
            "fid": "f62", "fs": _FS_INDUSTRY,
            "fields": f"f12,f14,f3,f62,f64,f66,f69,f70,f184",
        }
        data = self._request(params)
        if not data:
            return None

        diff = data.get("data", {}).get("diff", [])
        if not diff:
            logger.warning("[EmHiddenApi] 行业板块资金流返回空数据")
            return None

        records = []
        for item in diff:
            name = str(item.get("f14", ""))
            if not name:
                continue
            super_large = float(item.get("f64", 0) or 0)
            large = float(item.get("f66", 0) or 0)
            records.append({
                "名称": name,
                "板块名称": name,
                "name": name,
                "涨跌幅": float(item.get("f3", 0) or 0),
                "主力净流入": float(item.get("f62", 0) or 0),
                "超大单净流入": super_large,
                "大单净流入": large,
                "中单净流入": float(item.get("f70", 0) or 0),
                "小单净流入": float(item.get("f69", 0) or 0),
            })
        df = pd.DataFrame(records)
        logger.info(f"[EmHiddenApi] 行业板块资金流: {len(df)} 条")
        return df

    def get_north_flow(self) -> Optional[Dict[str, Any]]:
        """
        获取北向资金数据（浏览器模拟）

        数据源：push2his.eastmoney.com → 沪深港通历史资金
        """
        north_params = {
            "pn": 1, "pz": 5, "po": 1, "np": 1, "fltt": 2, "invt": 2,
            "fid": "f3", "fs": "m:130+t:5",
            "fields": "f12,f14,f2,f3,f62,f184,f66,f69,f70",
        }
        data = self._request(north_params, base_url=_BASE_URL_V2)
        if not data:
            return None

        diff = data.get("data", {}).get("diff", [])
        if not diff:
            logger.warning("[EmHiddenApi] 北向资金返回空数据")
            return None

        latest = diff[-1] if len(diff) > 1 else diff[0]
        try:
            net_inflow = float(latest.get("f62", 0) or 0)
        except (ValueError, TypeError):
            net_inflow = 0.0
        result = {
            "date": str(latest.get("f12", "")),
            "net_inflow_yi": round(net_inflow / 1e8, 2),
            "accumulated_yi": 0.0,
            "direction": "inflow" if net_inflow > 0 else "outflow" if net_inflow < 0 else "flat",
        }
        logger.info(f"[EmHiddenApi] 北向资金: {result['net_inflow_yi']}亿")
        return result

    def get_market_profit_effect(self) -> Optional[Dict[str, Any]]:
        """
        获取赚钱效应（浏览器模拟）

        数据源：push2.eastmoney.com → fs=m:93+t:1 limit-up stats
        通过涨停板统计推断赚钱效应
        """
        limit_up = self.get_limit_up_pool()
        if limit_up is None or limit_up.empty:
            return None

        total_limit_up = len(limit_up)
        high_consecutive = len(limit_up[limit_up.get("consecutive_days", 0) >= 3])
        return {
            "全部涨停": float(total_limit_up),
            "涨停股数": float(total_limit_up),
            "连板股数": float(high_consecutive),
            "炸板率": 0.0,
        }
