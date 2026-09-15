"""
Playwright-based board/sector data scraper.

Uses Playwright browser as anti-detection infrastructure to call
东方财富 internal JSON APIs, extracting structured sector rankings,
limit-up pool data, consecutive board ladders, and leader stocks.

Strategy:
1. Playwright browser provides real browser fingerprint, cookies, headers
2. Data is fetched via the same page context using page.evaluate + fetch()
3. API responses are parsed as structured JSON
4. Falls back to direct API calls with requests if browser fails

This is more reliable than DOM scraping because:
- API format is stable (push2.eastmoney.com)
- Data is already structured
- No dependency on DOM rendering timing
"""

import json
import logging
import random
import re
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlencode

import pandas as pd

logger = logging.getLogger(__name__)

# ---------- API endpoints ----------

PUSH2_BASE = "https://push2.eastmoney.com/api/qt/clist/get"


def _get_limit_up_ratio(code: str, name: str = "") -> float:
    c = (code or "").strip().split(".")[0]
    n = (name or "").upper()
    if "ST" in n:
        return 0.05
    if c.startswith(("688", "30")):
        return 0.20
    if c.startswith(("92", "43", "81", "82", "83", "87", "88")):
        return 0.30
    return 0.10


def _is_limit_up(code: str, change_pct: float, name: str = "") -> bool:
    ratio = _get_limit_up_ratio(code, name)
    return change_pct >= (ratio * 100 - 1.5)
# Limit-up pool: dedicated API from push2ex
LIMITUP_URL = "https://push2ex.eastmoney.com/getTopicZTPool"
# Fallback: clist with all A-shares (filtered by change_pct >= 9.5)
LIMITUP_FALLBACK_URL = (
    "https://push2.eastmoney.com/api/qt/clist/get"
    "?cb=&fid=f3&po=1&pz=200&pn=1&np=1&fltt=2&invt=2"
    "&fs=m:0+t:6,m:0+t:13,m:0+t:80,m:1+t:2,m:1+t:23,m:0+t:81+s:2048"
    "&fields=f12,f14,f2,f3,f4,f8,f100"
)
SECTOR_BOARD_URL = (
    "https://push2.eastmoney.com/api/qt/clist/get"
    "?cb=&fid=f3&po=1&pz=200&pn=1&np=1&fltt=2&invt=2"
    "&fs=m:90+t:2&fields=f12,f14,f2,f3,f128,f104,f152"
)
CONCEPT_BOARD_URL = (
    "https://push2.eastmoney.com/api/qt/clist/get"
    "?cb=&fid=f3&po=1&pz=200&pn=1&np=1&fltt=2&invt=2"
    "&fs=m:90+t:3&fields=f12,f14,f2,f3,f4,f8,f20,f15,f17"
)

# ---------- Browser fingerprint ----------

USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
]

VIEWPORTS = [
    {"width": 1920, "height": 1080},
    {"width": 1440, "height": 900},
    {"width": 1366, "height": 768},
]


def random_sleep(min_s: float = 1.0, max_s: float = 3.0) -> None:
    time.sleep(random.uniform(min_s, max_s))


def _url_params(**kwargs) -> str:
    return urlencode({k: v for k, v in kwargs.items() if v is not None})


class BoardScraperFetcher:
    """
    Board/sector data scraper using Playwright.

    Uses browser-based anti-detection to access EastMoney hidden JSON APIs,
    extracting structured board rankings, limit-up pools, and ladder data.

    Usage:
        fetcher = BoardScraperFetcher(headless=True)
        sectors = fetcher.get_sector_rankings(n=10)
        pool = fetcher.get_limit_up_pool()
        fetcher.close()
    """

    name = "BoardScraperFetcher"

    def __init__(
        self,
        headless: bool = True,
        browser_type: str = "chromium",
        timeout_ms: int = 30000,
    ):
        self._headless = headless
        self._browser_type = browser_type
        self._timeout_ms = timeout_ms
        self._playwright = None
        self._browser = None
        self._context = None
        self._page = None

    # ---------- Browser lifecycle ----------

    def _ensure_page(self):
        if self._page is not None:
            return self._page
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            logger.error("[%s] playwright not installed", self.name)
            return None

        try:
            self._playwright = sync_playwright().start()
            launcher = getattr(self._playwright, self._browser_type)

            ua = random.choice(USER_AGENTS)
            vp = random.choice(VIEWPORTS)

            self._browser = launcher.launch(
                headless=self._headless,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--disable-dev-shm-usage",
                    "--no-sandbox",
                ],
            )
            self._context = self._browser.new_context(
                user_agent=ua,
                viewport=vp,
                locale="zh-CN",
                timezone_id="Asia/Shanghai",
                extra_http_headers={
                    "Accept-Language": "zh-CN,zh;q=0.9",
                    "Referer": "https://quote.eastmoney.com/",
                },
            )
            self._context.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                Object.defineProperty(navigator, 'plugins', {get: () => [1,2,3,4,5]});
            """)
            self._page = self._context.new_page()
            self._page.set_default_timeout(self._timeout_ms)

            # Warm up: visit board page to set cookies and session
            self._page.goto(
                "https://quote.eastmoney.com/center/gridlist.html#industry_board",
                wait_until="domcontentloaded",
                timeout=self._timeout_ms,
            )
            random_sleep(2.0, 3.0)
            logger.info("[%s] browser ready", self.name)
            return self._page
        except Exception as e:
            logger.error("[%s] browser init failed: %s", self.name, e)
            self.close()
            return None

    def close(self):
        try:
            for obj in [self._page, self._context, self._browser]:
                if obj:
                    try:
                        obj.close()
                    except Exception:
                        pass
            if self._playwright:
                self._playwright.stop()
        except Exception:
            pass
        self._page = self._context = self._browser = self._playwright = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    # ---------- API caller ----------

    def _api_fetch(self, url: str) -> Optional[Dict[str, Any]]:
        """Fetch JSON from an EastMoney API endpoint.

        push2ex.eastmoney.com requires specific cookies → use direct HTTP.
        push2.eastmoney.com works via browser page context (same origin).
        """
        page = self._ensure_page()
        if page is None:
            return self._api_fetch_direct(url)

        # push2ex 是独立域名，浏览器有跨域限制，直接走 HTTP
        if "push2ex.eastmoney.com" in url and self._context:
            return self._api_fetch_direct(url)

        try:
            # Use XHR (more compatible with headless Chrome) instead of fetch
            result = page.evaluate("""
                (url) => {
                    return new Promise((resolve) => {
                        const xhr = new XMLHttpRequest();
                        xhr.open('GET', url, true);
                        xhr.withCredentials = true;
                        xhr.setRequestHeader('Accept', 'application/json, text/plain, */*');
                        xhr.setRequestHeader('Referer', 'https://quote.eastmoney.com/');
                        xhr.onload = () => {
                            try {
                                let text = xhr.responseText || '';
                                // API returns JSONP-like with leading cb(...)
                                const cleaned = text.replace(/^cb\(/, '').replace(/\)\s*$/, '').trim();
                                resolve(JSON.parse(cleaned));
                            } catch(e) {
                                resolve({error: 'parse: ' + e.message, text: xhr.responseText.substring(0, 100)});
                            }
                        };
                        xhr.onerror = () => resolve({error: 'xhr error'});
                        xhr.ontimeout = () => resolve({error: 'xhr timeout'});
                        xhr.timeout = 15000;
                        xhr.send();
                    });
                }
            """, url)
            if isinstance(result, dict) and "error" in result:
                logger.warning("[%s] API via page failed: %s", self.name, result.get("error"))
                return self._api_fetch_direct(url)
            return result
        except Exception as e:
            logger.warning("[%s] API via page exception: %s", self.name, e)
            return self._api_fetch_direct(url)

    def _api_fetch_direct(self, url: str) -> Optional[Dict[str, Any]]:
        """Fallback: direct HTTP request using cookies from the browser context."""
        try:
            import requests as req

            headers = {
                "User-Agent": random.choice(USER_AGENTS),
                "Accept": "application/json, text/plain, */*",
                "Accept-Language": "zh-CN,zh;q=0.9",
                "Referer": "https://quote.eastmoney.com/",
            }

            # Use cookies from the Playwright browser context for auth
            cookies = {}
            if self._context:
                for c in self._context.cookies():
                    cookies[c.get("name", "")] = c.get("value", "")

            resp = req.get(url, headers=headers, cookies=cookies, timeout=15)
            text = resp.text
            text = re.sub(r'^cb\(|\)\s*$', '', text.strip())
            return json.loads(text)
        except Exception as e:
            logger.error("[%s] direct HTTP fallback failed: %s", self.name, e)
            return None

    def _parse_clist(self, resp_data: Optional[Dict]) -> List[Dict[str, Any]]:
        """Parse push2 API response into list of dicts.

        The API returns {data: {diff: [{f12:code, f14:name, f2:price, f3:change%, ...}]}}
        Field mapping:
          f12: code, f14: name, f2: price, f3: change%, f4: change_amount,
          f8: turnover_rate, f15: high, f17: low, f20: total_mv
        """
        if not resp_data:
            return []
        try:
            items = resp_data.get("data", {}).get("diff", [])
            return items if isinstance(items, list) else []
        except Exception:
            return []

    # ---------- Data methods ----------

    def get_sector_rankings(
        self, n: int = 10
    ) -> Optional[Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]]:
        """Fetch industry board rankings.

        优先级：
        1. 东财 push2 API
        2. akshare 新浪接口 (当东财被阻断时)

        Returns (top_sectors, bottom_sectors) where each dict has:
          name, change_pct, code, up_count, limit_up_count, leader, price
        """
        # 优先东财接口
        try:
            raw = self._api_fetch(SECTOR_BOARD_URL)
            items = self._parse_clist(raw)
            if items:
                rows = []
                for item in items:
                    code = str(item.get("f12") or "")
                    name = str(item.get("f14") or "").strip()
                    change_pct = float(item.get("f3") or 0)
                    price = float(item.get("f2") or 0)
                    leader = str(item.get("f128") or "").strip()
                    up_count = int(item.get("f104", 0) or 0)
                    limit_up_count = int(item.get("f152", 0) or 0)
                    rows.append({
                        "code": code,
                        "name": name,
                        "change_pct": change_pct,
                        "price": price,
                        "leader": leader,
                        "up_count": up_count,
                        "limit_up_count": limit_up_count,
                    })

                rows.sort(key=lambda x: x["change_pct"], reverse=True)
                top = rows[:n]
                bottom = list(reversed(rows[-n:])) if len(rows) >= n else list(reversed(rows))

                logger.info(
                    "[%s] sector rankings (东财): top=%d bottom=%d",
                    self.name, len(top), len(bottom),
                )
                return top, bottom
            else:
                logger.warning("[%s] 东财接口返回空数据，尝试新浪回退", self.name)
        except Exception as e:
            logger.warning("[%s] 东财接口失败: %s，尝试新浪回退", self.name, e)

        # 东财失败，回退到 akshare 新浪接口
        try:
            import akshare as ak
            import pandas as pd

            logger.info("[API调用] ak.stock_sector_spot(indicator='行业') 新浪回退...")
            df = ak.stock_sector_spot(indicator='行业')
            if df is None or df.empty:
                logger.warning("[%s] 新浪接口返回空数据", self.name)
                return None

            change_col = '涨跌幅'
            name_col = '板块'
            df[change_col] = pd.to_numeric(df[change_col], errors='coerce')
            df = df.dropna(subset=[change_col])

            rows = []
            for _, row in df.iterrows():
                rows.append({
                    "code": "",
                    "name": str(row.get(name_col, "")),
                    "change_pct": float(row.get(change_col, 0)),
                    "price": 0,
                    "leader": "",
                    "up_count": 0,
                    "limit_up_count": 0,
                })

            rows.sort(key=lambda x: x["change_pct"], reverse=True)
            top = rows[:n]
            bottom = list(reversed(rows[-n:])) if len(rows) >= n else list(reversed(rows))

            logger.info(
                "[%s] sector rankings (新浪): top=%d bottom=%d",
                self.name, len(top), len(bottom),
            )
            return top, bottom

        except Exception as e:
            logger.error("[%s] 新浪回退也失败: %s", self.name, e)
            return None

    def get_concept_rankings(
        self, n: int = 10
    ) -> Optional[Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]]:
        """Fetch concept board rankings.

        优先级：
        1. 东财 push2 API
        2. akshare 新浪接口 (当东财被阻断时)
        """
        # 优先东财接口
        try:
            raw = self._api_fetch(CONCEPT_BOARD_URL)
            items = self._parse_clist(raw)
            if items:
                rows = []
                for item in items:
                    code = str(item.get("f12") or "")
                    name = str(item.get("f14") or "").strip()
                    change_pct = float(item.get("f3") or 0)
                    rows.append({
                        "code": code,
                        "name": name,
                        "change_pct": change_pct,
                    })

                rows.sort(key=lambda x: x["change_pct"], reverse=True)
                top = rows[:n]
                bottom = list(reversed(rows[-n:])) if len(rows) >= n else list(reversed(rows))
                return top, bottom
            else:
                logger.warning("[%s] 东财概念板块返回空数据，尝试新浪回退", self.name)
        except Exception as e:
            logger.warning("[%s] 东财概念板块失败: %s，尝试新浪回退", self.name, e)

        # 东财失败，回退到 akshare 新浪接口
        try:
            import akshare as ak
            import pandas as pd

            logger.info("[API调用] ak.stock_sector_spot(indicator='概念') 新浪回退...")
            df = ak.stock_sector_spot(indicator='概念')
            if df is None or df.empty:
                return None

            change_col = '涨跌幅'
            name_col = '板块'
            df[change_col] = pd.to_numeric(df[change_col], errors='coerce')
            df = df.dropna(subset=[change_col])

            rows = []
            for _, row in df.iterrows():
                rows.append({
                    "code": "",
                    "name": str(row.get(name_col, "")),
                    "change_pct": float(row.get(change_col, 0)),
                })

            rows.sort(key=lambda x: x["change_pct"], reverse=True)
            top = rows[:n]
            bottom = list(reversed(rows[-n:])) if len(rows) >= n else list(reversed(rows))

            logger.info(
                "[%s] concept rankings (新浪): top=%d bottom=%d",
                self.name, len(top), len(bottom),
            )
            return top, bottom

        except Exception as e:
            logger.error("[%s] 新浪概念板块回退也失败: %s", self.name, e)
            return None

    def get_limit_up_pool(self, date: Optional[str] = None) -> Optional[List[Dict[str, Any]]]:
        """Fetch limit-up stocks from EastMoney APIs.

        Uses dedicated ZT pool API (push2ex) with fallback to clist + filter.
        """
        if date is None:
            date = datetime.now().strftime("%Y%m%d")

        # Primary: dedicated ZT pool API
        try:
            raw = self._api_fetch(
                f"{LIMITUP_URL}?ut=7eea3edcaed734bea9cbfc24409ed989"
                f"&dpt=wz.ztzt&Pageindex=0&pagesize=200&sort=fbt:asc"
                f"&date={date}"
            )
            pool_data = (raw.get("data") or {}).get("pool", []) if raw else []
            if pool_data:
                pool = []
                for item in pool_data:
                    code = str(item.get("c", ""))
                    name = str(item.get("n", ""))
                    change_pct = float(item.get("zdp", 0) or 0)
                    if not _is_limit_up(code, change_pct, name):
                        continue
                    pool.append({
                        "code": code,
                        "name": name,
                        "price": float(item.get("p", 0) or 0) / 1000,
                        "change_pct": change_pct,
                        "consecutive_days": int(item.get("lbc", 0) or 0),
                        "industry": str(item.get("hybk", "")),
                        "seal_amount": float(item.get("fdje", 0) or 0),
                        "break_count": int(item.get("zbc", 0) or 0),
                    })
                logger.info("[%s] limit-up pool (ZT API): %d stocks", self.name, len(pool))
                pool.sort(key=lambda x: x["change_pct"], reverse=True)
                return pool
        except Exception as e:
            logger.debug("[%s] ZT API failed, using fallback: %s", self.name, e)

        # Fallback: clist + filter against stock-specific limit
        try:
            raw = self._api_fetch(LIMITUP_FALLBACK_URL)
            items = self._parse_clist(raw)
            if not items:
                logger.warning("[%s] no limit-up data from fallback", self.name)
                return None
            pool = []
            for item in items:
                code = str(item.get("f12") or "")
                name = str(item.get("f14") or "").strip()
                change_pct = float(item.get("f3") or 0)
                if not _is_limit_up(code, change_pct, name):
                    continue
                pool.append({
                    "code": code,
                    "name": name,
                    "price": float(item.get("f2") or 0),
                    "change_pct": change_pct,
                    "turnover_rate": float(item.get("f8", 0) or 0),
                    "industry": str(item.get("f100") or "").strip(),
                })
            pool.sort(key=lambda x: x["change_pct"], reverse=True)
            logger.info("[%s] limit-up pool (fallback): %d stocks", self.name, len(pool))
            return pool
        except Exception as e:
            logger.error("[%s] get_limit_up_pool failed: %s", self.name, e)
            return None

    def get_limit_down_pool(self) -> Optional[List[Dict[str, Any]]]:
        """Get limit-down stocks (change_pct near or below limit-down threshold)."""
        try:
            url = (
                "https://push2.eastmoney.com/api/qt/clist/get"
                "?cb=&fid=f3&po=0&pz=200&pn=1&np=1&fltt=2&invt=2"
                "&fs=m:0+t:6,m:0+t:13,m:0+t:80,m:1+t:2,m:1+t:23,m:0+t:81+s:2048"
                "&fields=f12,f14,f2,f3,f4,f8,f100"
            )
            raw = self._api_fetch(url)
            items = self._parse_clist(raw)
            if not items:
                return None
            pool = []
            for item in items:
                code = str(item.get("f12") or "")
                name = str(item.get("f14") or "").strip()
                change_pct = float(item.get("f3") or 0)
                # Limit-down: change_pct near the negative limit
                if change_pct > -9.0:
                    continue
                pool.append({
                    "code": code,
                    "name": name,
                    "price": float(item.get("f2") or 0),
                    "change_pct": change_pct,
                    "turnover_rate": float(item.get("f8", 0) or 0),
                    "industry": str(item.get("f100") or "").strip(),
                })
            pool.sort(key=lambda x: x["change_pct"])
            logger.info("[%s] limit-down pool: %d stocks", self.name, len(pool))
            return pool
        except Exception as e:
            logger.error("[%s] get_limit_down_pool failed: %s", self.name, e)
            return None

    def get_sector_stocks(
        self, sectors: List[Dict[str, Any]], max_sectors: int = 10
    ) -> List[Dict[str, Any]]:
        """For each sector, get board members and flag limit-up/down stocks.

        Returns list of sector dicts with their limit_up_stocks and limit_down_stocks.
        """
        result = []
        for sector in sectors[:max_sectors]:
            code = sector.get("code", "")
            if not code:
                continue
            members = self.get_board_members(code, top_n=30)
            if not members:
                continue

            limit_ups = []
            limit_downs = []
            for m in members:
                chg = m.get("change_pct", 0)
                if _is_limit_up(str(m.get("code", "")), chg, str(m.get("name", ""))):
                    limit_ups.append({
                        "code": m.get("code", ""),
                        "name": m.get("name", ""),
                        "change_pct": chg,
                        "price": m.get("price", 0),
                    })
                if chg <= -9.0:
                    limit_downs.append({
                        "code": m.get("code", ""),
                        "name": m.get("name", ""),
                        "change_pct": chg,
                        "price": m.get("price", 0),
                    })

            result.append({
                "sector_code": code,
                "sector_name": sector.get("name", ""),
                "sector_change_pct": sector.get("change_pct", 0),
                "limit_up_count": len(limit_ups),
                "limit_down_count": len(limit_downs),
                "limit_up_stocks": limit_ups,
                "limit_down_stocks": limit_downs,
            })

        logger.info("[%s] sector stocks: %d sectors analyzed", self.name, len(result))
        return result

    def get_board_members(
        self, board_code: str, top_n: int = 50
    ) -> Optional[List[Dict[str, Any]]]:
        """Fetch member stocks of a specific board.

        Args:
            board_code: e.g. 'BK0889' (without BK prefix also works)
            top_n: max number of stocks to return
        """
        bc = board_code.strip().upper()
        if not bc.startswith("BK"):
            bc = f"BK{bc}"

        url = (
            f"https://push2.eastmoney.com/api/qt/clist/get"
            f"?cb=&fid=f3&po=1&pz={top_n}&pn=1&np=1&fltt=2&invt=2"
            f"&fs=b:{bc}+f:!50&fields=f12,f14,f2,f3,f4,f8,f15,f17"
        )
        try:
            raw = self._api_fetch(url)
            items = self._parse_clist(raw)
            if not items:
                return None

            members = []
            for item in items:
                code = str(item.get("f12") or "")
                name = str(item.get("f14") or "").strip()
                price = float(item.get("f2") or 0)
                change_pct = float(item.get("f3") or 0)
                members.append({
                    "code": code,
                    "name": name,
                    "price": price,
                    "change_pct": change_pct,
                })

            return members

        except Exception as e:
            logger.error("[%s] get_board_members failed for %s: %s", self.name, bc, e)
            return None

    def get_stock_kline_data(self, code: str, days: int = 60) -> Optional[pd.DataFrame]:
        """Fetch daily K-line data for a single stock via EastMoney push2 API.

        Uses the existing browser context (reuse browser, fast).
        """
        try:
            secid = f"1.{code}"
            url = (
                f"https://push2.eastmoney.com/api/qt/stock/kline/get"
                f"?secid={secid}&fields1=f1,f2,f3&fields2=f51,f52,f53,f54,f55,f56,f57"
                f"&klt=101&fqt=1&end=20500101&lmt={days}"
            )
            raw = self._api_fetch(url)
            if raw is None:
                return None
            data = raw.get("data")
            if data is None:
                return None
            klines = data.get("klines", [])
            if not klines:
                return None
            rows = []
            for line in klines:
                parts = str(line).split(",")
                if len(parts) >= 7:
                    rows.append({
                        "date": parts[0], "open": float(parts[1]),
                        "close": float(parts[2]), "high": float(parts[3]),
                        "low": float(parts[4]), "volume": float(parts[5]),
                        "amount": float(parts[6]),
                    })
            df = pd.DataFrame(rows)
            df["pct_chg"] = df["close"].pct_change() * 100
            return df
        except Exception as e:
            logger.debug("[%s] get_stock_kline failed for %s: %s", self.name, code, e)
            return None

    @staticmethod
    def get_stock_kline_data(code: str, days: int = 60) -> Optional[pd.DataFrame]:
        """Fetch daily K-line data for a single stock via EastMoney push2 API."""
        fetcher = BoardScraperFetcher(headless=True)
        try:
            secid = f"1.{code}"
            url = (
                f"https://push2.eastmoney.com/api/qt/stock/kline/get"
                f"?secid={secid}&fields1=f1,f2,f3&fields2=f51,f52,f53,f54,f55,f56,f57"
                f"&klt=101&fqt=1&end=20500101&lmt={days}"
            )
            raw = fetcher._api_fetch(url)
            if not raw:
                return None
            klines = raw.get("data", {}).get("klines", [])
            if not klines:
                return None
            rows = []
            for line in klines:
                parts = str(line).split(",")
                if len(parts) >= 7:
                    rows.append({
                        "date": parts[0], "open": float(parts[1]),
                        "close": float(parts[2]), "high": float(parts[3]),
                        "low": float(parts[4]), "volume": float(parts[5]),
                        "amount": float(parts[6]),
                    })
            df = pd.DataFrame(rows)
            df["pct_chg"] = df["close"].pct_change() * 100
            return df
        except Exception as e:
            logger.error("[%s] get_stock_kline failed for %s: %s", fetcher.name, code, e)
            return None
        finally:
            fetcher.close()

    def get_consecutive_board_ladder(self) -> Optional[Dict[int, List[Dict]]]:
        """Group limit-up stocks by consecutive limit-up days into ladder tiers.

        Returns: {1: [{code, name, price, change_pct}, ...], 2: [...], ...}
        """
        pool = self.get_limit_up_pool()
        if not pool:
            return None

        ladder: Dict[int, List[Dict]] = {}
        for s in pool:
            days = int(s.get("consecutive_days", 0) or 0)
            if days < 1:
                days = 1
            if days not in ladder:
                ladder[days] = []
            ladder[days].append({
                "code": s.get("code", ""),
                "name": s.get("name", ""),
                "price": s.get("price", 0),
                "change_pct": s.get("change_pct", 0),
            })

        ladder_sorted = dict(sorted(ladder.items(), reverse=True))
        for days, stocks in ladder_sorted.items():
            logger.info("[%s] ladder: day%d=%d", self.name, days, len(stocks))
        return ladder_sorted

    def scrape_all(self) -> Dict[str, Any]:
        result: Dict[str, Any] = {
            "date": datetime.now().strftime("%Y-%m-%d"),
            "sector_rankings": None,
            "limit_up_pool": None,
            "board_ladder": None,
            "concept_rankings": None,
            "sector_stocks": None,
            "errors": [],
        }

        try:
            sr = self.get_sector_rankings()
            if sr:
                result["sector_rankings"] = sr
                top_sectors = sr[0]
                # Get per-sector limit-up/down stocks for top sectors
                if top_sectors:
                    sector_detail = self.get_sector_stocks(top_sectors, max_sectors=10)
                    if sector_detail:
                        result["sector_stocks"] = sector_detail
            else:
                result["errors"].append("sector_rankings: None")
        except Exception as e:
            result["errors"].append(f"sector_rankings: {e}")

        try:
            cr = self.get_concept_rankings()
            if cr:
                result["concept_rankings"] = cr
        except Exception as e:
            result["errors"].append(f"concept_rankings: {e}")

        try:
            pool = self.get_limit_up_pool()
            if pool:
                result["limit_up_pool"] = pool
                ladder = self.get_consecutive_board_ladder()
                if ladder:
                    result["board_ladder"] = ladder
            else:
                result["errors"].append("limit_up_pool: None")
        except Exception as e:
            result["errors"].append(f"limit_up_pool: {e}")

        logger.info(
            "[%s] scrape done: sectors=%s concepts=%s pool=%d err=%d",
            self.name,
            "OK" if result["sector_rankings"] else "FAIL",
            "OK" if result["concept_rankings"] else "FAIL",
            len(result["limit_up_pool"]) if result["limit_up_pool"] else 0,
            len(result["errors"]),
        )
        return result

    def export_to_dataframe(self, data: Dict[str, Any]) -> Dict[str, pd.DataFrame]:
        """Export scraped data to pandas DataFrames."""
        dfs: Dict[str, pd.DataFrame] = {}
        date = data.get("date", "")

        for key, cols in [
            ("sector_rankings", ["code", "name", "change_pct", "price"]),
            ("limit_up_pool", ["code", "name", "price", "change_pct", "turnover_rate"]),
            ("concept_rankings", ["code", "name", "change_pct"]),
        ]:
            raw = data.get(key)
            if raw:
                if isinstance(raw, tuple):
                    raw_list = raw[0] + raw[1]
                else:
                    raw_list = raw
                df = pd.DataFrame(raw_list)
                if not df.empty:
                    df.insert(0, "date", date)
                    dfs[key] = df

        return dfs


def scrape_board_data() -> Dict[str, Any]:
    """Convenience function: scrape all board data in one call."""
    fetcher = BoardScraperFetcher()
    try:
        return fetcher.scrape_all()
    finally:
        fetcher.close()
