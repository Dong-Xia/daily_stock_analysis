# -*- coding: utf-8 -*-
"""
Manual sector review Markdown parser.

Extracts structured ``HotSectorItem``-compatible dictionaries from
user-inputted Chinese Markdown text that describes daily hot-sector
reviews (涨幅TOP5, 涨停数量, 连板梯队, 龙头带动效应).

Only the Python standard library is used.
"""

import re
from typing import Any, Dict, List, Optional, Tuple


# e.g. "1. **能源金属（锂矿/盐湖提锂）**：碳酸锂价格..."
_SECTOR_TOP_RE = re.compile(
    r"^\s*\d+\.\s*\*\*\s*(.+?)\s*\*\*\s*：\s*(.*)$"
)

# e.g. "| 能源金属（锂矿/盐湖提锂） | 8        |"
# Also handles annotated counts: "| 锂电池/储能 | 21只（含储能） |" or "| AI算力 | 10只+ |"
_TABLE_ROW_RE = re.compile(
    r"^\s*\|\s*(.+?)\s*\|\s*(\d+)"
)

# e.g. "### 3连板"
_LADDER_HEADER_RE = re.compile(r"^\s*###\s*(\d+)\s*连板")

# e.g. "- 综艺股份（600770）：半导体/芯片、AI算力、创投"
# Also handles bold-wrapped names: "- **飞马国际（002210）**：快递物流/环保"
_LADDER_STOCK_RE = re.compile(
    r"^\s*[-*]\s*(?:\*\*)?(.+?)(?:\*\*)?\s*（\s*(\d{6})\s*）\s*(?:\*\*)?\s*：\s*(.*)$"
)

# e.g. "- 核心龙头：融捷股份（先锋龙头，3连板）、江特电机（中军龙头，2连板）"
# Also handles bold-wrapped: "- **核心龙头**：北方稀土（板块中军）"
_LEADER_LINE_RE = re.compile(
    r"^\s*[-*]\s*(?:\*\*)?核心龙头(?:\*\*)?\s*：\s*(.+)$"
)

# e.g. "- 带动涨停数量：8只"
# Also handles bold-wrapped: "- **带动涨停数量**：13只"
_DRIVEN_COUNT_RE = re.compile(
    r"^\s*[-*]\s*(?:\*\*)?带动涨停数量(?:\*\*)?\s*：\s*(\d+)"
)

# e.g. "- 具体联动标的：恩捷股份、天华新能、金圆股份..."
# Also handles bold-wrapped: "- **具体联动标的**：北方稀土、中国稀土"
_DRIVEN_STOCKS_RE = re.compile(
    r"^\s*[-*]\s*(?:\*\*)?具体联动标的(?:\*\*)?\s*：\s*(.+)$"
)

_EFFECT_SUMMARY_RE = re.compile(
    r"^\s*[-*]\s*(?:\*\*)?效应总结(?:\*\*)?\s*：\s*(.+)$"
)

# e.g. "融捷股份（先锋龙头，3连板）"
_LEADER_STOCK_RE = re.compile(
    r"([^（(),、]+?)\s*（\s*(?:先锋龙头|中军龙头)?\s*[，,]?\s*(\d+)\s*连板\s*）"
)

# Fallback: any stock name（description）without 连板 info
_LEADER_STOCK_FALLBACK_RE = re.compile(
    r"([^（(),、\s]{2,8})\s*（[^）]*）"
)

_NUM_RE = re.compile(r"\d+")


def _normalize_sector_name(name: str) -> str:
    """Strip Markdown bold/italic and whitespace for cross-section matching."""
    return name.replace("**", "").replace("*", "").strip()


def _sector_key(name: str) -> str:
    """
    Produce a loose matching key for a sector name.

    Keeps Chinese characters and alphanumerics; drops extra spaces so that
    ``能源金属（锂矿/盐湖提锂）`` and ``能源金属(锂矿/盐湖提锂)``
    share the same key.
    """
    name = _normalize_sector_name(name)
    name = name.replace("（", "(").replace("）", ")")
    chars = [c for c in name if "\u4e00" <= c <= "\u9fff" or c.isalnum() or c in "()/\\"]
    return "".join(chars)


def _extract_stock_name_code(text: str) -> List[Tuple[str, str]]:
    """
    Extract ``(name, code)`` tuples from a free-form leader line.

    Handles patterns like:
      融捷股份（先锋龙头，3连板）
      江特电机（中军龙头，2连板）
      北方稀土（板块中军）
    """
    results: List[Tuple[str, str]] = []
    for m in _LEADER_STOCK_RE.finditer(text):
        results.append((m.group(1).strip(), ""))
    if not results:
        for m in _LEADER_STOCK_FALLBACK_RE.finditer(text):
            results.append((m.group(1).strip(), ""))
    return results


def _extract_change_pct(text: str) -> float:
    """
    Scan *text* for a percentage like ``涨超17%`` or ``+1.2%``.
    Returns ``0.0`` if none found.
    """
    m = re.search(r"([+-]?\d+(?:\.\d+)?)\s*%", text)
    if m:
        try:
            return float(m.group(1))
        except ValueError:
            pass
    return 0.0


def _extract_number_after_prefix(text: str, prefix: str) -> int:
    """Return the first integer found after *prefix* in *text*, or 0."""
    idx = text.find(prefix)
    if idx == -1:
        return 0
    m = _NUM_RE.search(text, idx + len(prefix))
    return int(m.group()) if m else 0


def _split_sections(text: str) -> Dict[str, List[str]]:
    """
    Split Markdown text into sections keyed by their ``##`` header text.

    Returns a dict mapping lower-cased header keywords to the lines
    belonging to that section (excluding the header itself).
    """
    sections: Dict[str, List[str]] = {}
    current_key: Optional[str] = None
    current_lines: List[str] = []

    for raw_line in text.splitlines():
        line = raw_line.rstrip("\n")
        header_match = re.match(r"^\s*##\s+(.*)$", line)
        if header_match:
            if current_key is not None:
                sections[current_key] = current_lines
            header_text = header_match.group(1).strip().lower()
            current_key = header_text
            current_lines = []
            continue
        if current_key is not None:
            current_lines.append(line)

    if current_key is not None:
        sections[current_key] = current_lines

    return sections


def _parse_top5_sectors(lines: List[str]) -> Dict[str, Dict[str, Any]]:
    """
    Parse the "涨幅TOP5" section.

    Returns a dict mapping ``_sector_key(name)`` ->
    ``{"name": raw_name, "catalyst": str, "change_pct": float}``.
    """
    sectors: Dict[str, Dict[str, Any]] = {}
    for line in lines:
        m = _SECTOR_TOP_RE.match(line)
        if not m:
            continue
        raw_name = m.group(1).strip()
        catalyst = m.group(2).strip()
        key = _sector_key(raw_name)
        sectors[key] = {
            "name": raw_name,
            "catalyst": catalyst,
            "change_pct": _extract_change_pct(catalyst),
        }
    return sectors


def _parse_limit_up_table(lines: List[str]) -> Dict[str, int]:
    """
    Parse the ``| 板块名称 | 涨停家数 |`` table.

    Returns a dict mapping ``_sector_key(name)`` -> ``limit_up_count``.
    """
    counts: Dict[str, int] = {}
    for line in lines:
        m = _TABLE_ROW_RE.match(line)
        if not m:
            continue
        raw_name = m.group(1).strip()
        try:
            count = int(m.group(2))
        except ValueError:
            count = 0
        counts[_sector_key(raw_name)] = count
    return counts


def _parse_ladder(lines: List[str]) -> Tuple[Dict[str, List[Dict[str, Any]]], List[Dict[str, Any]]]:
    """
    Parse the 连板梯队 section.

    Returns:
        1. ``sector_ladders``: ``sector_key -> [LimitUpLadderItem-dict, ...]``
        2. ``all_ladder_stocks``: flat list of ``SectorStockItem``-like dicts
    """
    sector_ladders: Dict[str, List[Dict[str, Any]]] = {}
    all_ladder_stocks: List[Dict[str, Any]] = []
    current_days: int = 0

    for line in lines:
        header = _LADDER_HEADER_RE.match(line)
        if header:
            current_days = int(header.group(1))
            continue

        stock = _LADDER_STOCK_RE.match(line)
        if not stock:
            continue

        name = stock.group(1).strip()
        code = stock.group(2).strip()
        tags_str = stock.group(3).strip()
        tags = [t.strip() for t in re.split(r"[、,，]", tags_str) if t.strip()]

        ladder_item = {
            "days": current_days,
            "stock_code": code,
            "stock_name": name,
        }
        stock_item = {
            "code": code,
            "name": name,
            "change_pct": 0.0,
            "price": 0.0,
            "is_limit_up": True,
            "consecutive_limit_up_days": current_days,
        }

        all_ladder_stocks.append(stock_item)

        for tag in tags:
            key = _sector_key(tag)
            sector_ladders.setdefault(key, []).append(ladder_item)

    return sector_ladders, all_ladder_stocks


def _parse_leader_sections(lines: List[str]) -> Dict[str, Dict[str, Any]]:
    """
    Parse the 板块龙头+带动效应 section.

    Returns a dict mapping ``_sector_key(subsection_name)`` ->
    ``{"leader_text": str, "driven_count": int, "driven_names": List[str]}``.
    """
    results: Dict[str, Dict[str, Any]] = {}
    current_sector: Optional[str] = None

    for line in lines:
        sec_header = re.match(r"^\s*###\s*\d+\.\s*(.+)$", line)
        if sec_header:
            current_sector = sec_header.group(1).strip()
            results.setdefault(_sector_key(current_sector), {
                "leader_text": "",
                "driven_count": 0,
                "driven_names": [],
            })
            continue

        if current_sector is None:
            continue

        key = _sector_key(current_sector)
        entry = results[key]

        leader_m = _LEADER_LINE_RE.match(line)
        if leader_m:
            entry["leader_text"] = leader_m.group(1).strip()
            continue

        count_m = _DRIVEN_COUNT_RE.match(line)
        if count_m:
            entry["driven_count"] = int(count_m.group(1))
            continue

        driven_m = _DRIVEN_STOCKS_RE.match(line)
        if driven_m:
            raw = driven_m.group(1)
            names = [n.strip() for n in re.split(r"[、,，]", raw) if n.strip()]
            names = [n for n in names if n != "..." and not n.endswith("...")]
            entry["driven_names"] = names
            continue

        effect_m = _EFFECT_SUMMARY_RE.match(line)
        if effect_m:
            entry["effect_summary"] = effect_m.group(1).strip()
            continue

    return results


class SectorParseResult(list):
    def __init__(self, sectors: List[Dict[str, Any]], market_sentiment: Optional[Dict[str, Any]] = None):
        super().__init__(sectors)
        self.market_sentiment = market_sentiment or {}


def _parse_market_sentiment(lines: List[str]) -> Dict[str, Any]:
    indices: List[Dict[str, Any]] = []
    market_summary: Dict[str, Any] = {}
    capital_flow: Dict[str, Any] = {}

    text = "\n".join(lines)

    index_pattern = re.compile(
        r"(?:[：:]|^|[\s，,；;])([\u4e00-\u9fff]{2,8})(涨|跌)([+-]?\d+(?:\.\d+)?)%.*?([\d.]+)点"
    )
    for m in index_pattern.finditer(text):
        direction = m.group(2)
        change_pct = float(m.group(3))
        if direction == "跌":
            change_pct = -change_pct
        indices.append({
            "name": m.group(1).strip(),
            "change_pct": change_pct,
            "value": float(m.group(4)),
        })

    up_match = re.search(r"上涨\D*(\d+)家", text)
    if up_match:
        market_summary["up_count"] = int(up_match.group(1))
    down_match = re.search(r"下跌\D*(\d+)家", text)
    if down_match:
        market_summary["down_count"] = int(down_match.group(1))

    lu_match = re.search(r"涨停\D*(\d+)家", text)
    if lu_match:
        market_summary["limit_up_count"] = int(lu_match.group(1))
    ld_match = re.search(r"跌停\D*(\d+)家", text)
    if ld_match:
        market_summary["limit_down_count"] = int(ld_match.group(1))

    flow_match = re.search(r"主力资金.*?(流入|流出|涌入)\D*([+-]?[\d.]+)\s*亿", text)
    if flow_match:
        direction = flow_match.group(1)
        if direction == "涌入":
            direction = "流入"
        capital_flow = {
            "direction": direction,
            "amount": float(flow_match.group(2)),
            "unit": "亿元",
        }

    return {
        "indices": indices,
        "market_summary": market_summary,
        "capital_flow": capital_flow,
    }


def parse_manual_sector_text(text: str) -> SectorParseResult:
    """
    Parse Chinese Markdown hot-sector review text into structured data.

    The returned list contains dictionaries compatible with the
    ``HotSectorItem`` schema:

    .. code-block:: python

        {
            "name": str,
            "change_pct": float,
            "limit_up_count": int,
            "limit_up_stocks": List[Dict],   # SectorStockItem-like
            "ladder": List[Dict],            # LimitUpLadderItem-like
            "leader": Optional[Dict],        # SectorStockItem-like or None
            "leader_correlation": float,
            "score": float,
        }

    Parameters
    ----------
    text:
        Raw Markdown text (may be empty or partially malformed).

    Returns
    -------
    List[Dict[str, Any]]
        Extracted sectors.  Returns ``[]`` for empty input.
    """
    if not text or not text.strip():
        return []

    sections = _split_sections(text)

    top5: Dict[str, Dict[str, Any]] = {}
    table_counts: Dict[str, int] = {}
    sector_ladders: Dict[str, List[Dict[str, Any]]] = {}
    all_ladder_stocks: List[Dict[str, Any]] = []
    leader_info: Dict[str, Dict[str, Any]] = {}
    market_sentiment: Optional[Dict[str, Any]] = None

    for header, lines in sections.items():
        if "涨幅" in header or "top5" in header:
            top5 = _parse_top5_sectors(lines)
        elif "涨停数量" in header or "涨停家数" in header:
            table_counts = _parse_limit_up_table(lines)
        elif "连板梯队" in header or "连板" in header:
            sector_ladders, all_ladder_stocks = _parse_ladder(lines)
        elif "龙头" in header or "带动效应" in header:
            leader_info = _parse_leader_sections(lines)
        elif "情绪" in header or "小结" in header:
            market_sentiment = _parse_market_sentiment(lines)

    all_keys = set(top5.keys()) | set(table_counts.keys()) | set(sector_ladders.keys()) | set(leader_info.keys())

    name_to_code: Dict[str, str] = {}
    for s in all_ladder_stocks:
        name_to_code[s["name"]] = s["code"]

    result: List[Dict[str, Any]] = []

    for key in sorted(all_keys):
        raw_name = (
            _find_original_name(key, table_counts)
            or _find_original_name(key, top5)
            or _find_original_name(key, leader_info)
            or _find_original_name(key, sector_ladders)
            or key
        )

        change_pct = top5.get(key, {}).get("change_pct", 0.0)
        limit_up_count = table_counts.get(key, 0)
        ladder = sector_ladders.get(key, [])
        leader_data = leader_info.get(key, {})

        leader: Optional[Dict[str, Any]] = None
        leader_text = leader_data.get("leader_text", "")
        if leader_text:
            candidates = _extract_stock_name_code(leader_text)
            if candidates:
                best_name, _ = candidates[0]
                best_code = name_to_code.get(best_name, "")
                best_days = _extract_number_after_prefix(leader_text, best_name)
                leader = {
                    "code": best_code,
                    "name": best_name,
                    "change_pct": 0.0,
                    "price": 0.0,
                    "is_limit_up": True,
                    "consecutive_limit_up_days": best_days,
                }

        if leader is None and ladder:
            highest = max(ladder, key=lambda x: x["days"])
            leader = {
                "code": highest["stock_code"],
                "name": highest["stock_name"],
                "change_pct": 0.0,
                "price": 0.0,
                "is_limit_up": True,
                "consecutive_limit_up_days": highest["days"],
            }

        limit_up_stocks: List[Dict[str, Any]] = []
        seen_codes: set = set()

        for rung in ladder:
            code = rung["stock_code"]
            if code not in seen_codes:
                seen_codes.add(code)
                limit_up_stocks.append({
                    "code": code,
                    "name": rung["stock_name"],
                    "change_pct": 0.0,
                    "price": 0.0,
                    "is_limit_up": True,
                    "consecutive_limit_up_days": rung["days"],
                })

        for driven_name in leader_data.get("driven_names", []):
            code = name_to_code.get(driven_name, "")
            if code and code in seen_codes:
                continue
            identifier = code or driven_name
            if identifier in seen_codes:
                continue
            seen_codes.add(identifier)
            limit_up_stocks.append({
                "code": code,
                "name": driven_name,
                "change_pct": 0.0,
                "price": 0.0,
                "is_limit_up": True,
                "consecutive_limit_up_days": 0,
            })

        score = 0.0
        if limit_up_count:
            score += limit_up_count * 5.0
        if ladder:
            score += sum(r["days"] for r in ladder) * 3.0
        if leader:
            score += leader.get("consecutive_limit_up_days", 0) * 2.0
        score = round(score, 2)

        related_stocks: List[Dict[str, str]] = []
        for driven_name in leader_data.get("driven_names", []):
            related_stocks.append({
                "name": driven_name,
                "code": name_to_code.get(driven_name, ""),
            })

        result.append({
            "name": raw_name,
            "change_pct": change_pct,
            "limit_up_count": limit_up_count,
            "limit_up_stocks": limit_up_stocks,
            "ladder": ladder,
            "leader": leader,
            "leader_correlation": 0.0,
            "score": score,
            "catalyst": top5.get(key, {}).get("catalyst"),
            "effect_summary": leader_data.get("effect_summary", ""),
            "related_stocks": related_stocks,
        })

    return SectorParseResult(_merge_overlapping_sectors(result), market_sentiment)


def _merge_overlapping_sectors(result: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Merge sectors whose names are subsets/supersets of each other.

    Example: ``稀土/小金属`` ← ``有色金属/稀土/小金属``,
    ``锂电产业链`` ← ``锂电产业链(固态电池/锂矿)``.
    Prefers the shorter canonical name and combines all data.
    """
    used: set = set()
    merged: List[Dict[str, Any]] = []

    for i, a in enumerate(result):
        if i in used:
            continue
        best = dict(a)
        best_key = _sector_key(a["name"])

        for j, b in enumerate(result):
            if j <= i or j in used:
                continue
            b_key = _sector_key(b["name"])
            if best_key not in b_key and b_key not in best_key:
                continue
            # Only merge when one name is a suffix of the other
            # (e.g. 有色金属/稀土/小金属 → 小金属, not 算力 → AI算力/算力租赁/CPO)
            if not (best_key.endswith(b_key) or b_key.endswith(best_key)):
                continue

            if len(b["name"]) < len(best["name"]):
                best["name"] = b["name"]
            if b["limit_up_count"] > best["limit_up_count"]:
                best["limit_up_count"] = b["limit_up_count"]
            if b["change_pct"] and not best["change_pct"]:
                best["change_pct"] = b["change_pct"]
            if b["ladder"]:
                have = {r["stock_code"] for r in best["ladder"]}
                for r in b["ladder"]:
                    if r["stock_code"] not in have:
                        best["ladder"].append(r)
                        have.add(r["stock_code"])
            leader_override = (
                b["leader"]
                and (
                    not best["leader"]
                    or (bool(b.get("catalyst")) and not bool(best.get("catalyst")))
                )
            )
            if leader_override:
                best["leader"] = b["leader"]
            if b.get("catalyst") and not best.get("catalyst"):
                best["catalyst"] = b["catalyst"]
            if b.get("effect_summary") and not best.get("effect_summary"):
                best["effect_summary"] = b["effect_summary"]
            if b.get("related_stocks"):
                have_names = {s["name"] for s in best.get("related_stocks", [])}
                for s in b.get("related_stocks", []):
                    if s["name"] not in have_names:
                        best.setdefault("related_stocks", []).append(s)
                        have_names.add(s["name"])

            score = 0.0
            if best["limit_up_count"]:
                score += best["limit_up_count"] * 5.0
            if best["ladder"]:
                score += sum(r["days"] for r in best["ladder"]) * 3.0
            if best["leader"]:
                score += best["leader"].get("consecutive_limit_up_days", 0) * 2.0
            best["score"] = round(score, 2)
            used.add(j)

        merged.append(best)

    return merged


def _find_original_name(key: str, mapping: Dict[str, Any]) -> Optional[str]:
    """
    Given a normalized *key*, return the original display name stored in
    *mapping* (if the mapping stores one under ``"name"``), or the dict key
    itself if the dict keys are the raw names.
    """
    if key in mapping:
        val = mapping[key]
        if isinstance(val, dict):
            return val.get("name", key)
        if isinstance(val, list) and val:
            return key
        return key
    return None
