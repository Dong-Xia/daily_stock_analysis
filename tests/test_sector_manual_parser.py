# -*- coding: utf-8 -*-
import pytest

from src.services.sector_manual_parser import parse_manual_sector_text


FULL_MARKDOWN = """\
## 涨幅TOP5
1. **能源金属**：碳酸锂价格涨超3.5%，全天领涨
2. **半导体**：国产替代逻辑升温，涨超2.1%

## 涨停数量
| 板块名称 | 涨停家数 |
| 能源金属 | 5 |
| 半导体 | 3 |

## 连板梯队
### 3连板
- 融捷股份（002192）：能源金属、锂矿
- 天齐锂业（002466）：能源金属、锂矿
### 2连板
- 中芯国际（688981）：半导体、芯片

## 板块龙头+带动效应
### 1. 能源金属
- 核心龙头：融捷股份（先锋龙头，3连板）
- 带动涨停数量：5只
- 具体联动标的：天齐锂业、赣锋锂业

### 2. 半导体
- 核心龙头：中芯国际（中军龙头，2连板）
- 带动涨停数量：3只
- 具体联动标的：韦尔股份、兆易创新
"""

FULL_MARKDOWN_ENRICHED = """\
## 涨幅TOP5
1. **能源金属**：碳酸锂价格涨超3.5%，全天领涨
2. **半导体**：国产替代逻辑升温，涨超2.1%

## 涨停数量
| 板块名称 | 涨停家数 |
| 能源金属 | 5 |
| 半导体 | 3 |

## 连板梯队
### 3连板
- 融捷股份（002192）：能源金属、锂矿
- 天齐锂业（002466）：能源金属、锂矿
### 2连板
- 中芯国际（688981）：半导体、芯片

## 板块龙头+带动效应
### 1. 能源金属
- 核心龙头：融捷股份（先锋龙头，3连板）
- 带动涨停数量：5只
- 具体联动标的：天齐锂业、赣锋锂业
- 效应总结：龙头强势，带动整个锂矿板块涨停潮

### 2. 半导体
- 核心龙头：中芯国际（中军龙头，2连板）
- 带动涨停数量：3只
- 具体联动标的：韦尔股份、兆易创新
- 效应总结：国产替代预期强化

## 市场情绪小结
沪指跌0.33%（4079.90点），深成指涨0.12%（10234.56点）
上涨**2036家**，下跌**3352家**
涨停**68家**，跌停**37家**
主力资金净流出722.27亿元
"""


def test_full_example_parse():
    result = parse_manual_sector_text(FULL_MARKDOWN)
    assert len(result) > 0
    names = {item["name"] for item in result}
    assert "能源金属" in names
    assert "半导体" in names


def test_empty_input():
    assert parse_manual_sector_text("") == []
    assert parse_manual_sector_text("   ") == []
    assert parse_manual_sector_text(None or "") == []  # type: ignore[arg-type]


def test_partial_input_only_table_no_ladder():
    text = """\
## 涨幅TOP5
1. **能源金属**：碳酸锂价格涨超3.5%

## 涨停数量
| 板块名称 | 涨停家数 |
| 能源金属 | 5 |
"""
    result = parse_manual_sector_text(text)
    assert len(result) == 1
    item = result[0]
    assert item["name"] == "能源金属"
    assert item["limit_up_count"] == 5
    assert item["change_pct"] == 3.5
    assert item["ladder"] == []
    assert item["leader"] is None


def test_ladder_extraction():
    result = parse_manual_sector_text(FULL_MARKDOWN)
    by_name = {item["name"]: item for item in result}

    energy = by_name["能源金属"]
    assert len(energy["ladder"]) == 2
    codes = {r["stock_code"] for r in energy["ladder"]}
    assert "002192" in codes
    assert "002466" in codes
    for r in energy["ladder"]:
        assert r["days"] == 3
        assert "stock_name" in r

    semi = by_name["半导体"]
    assert len(semi["ladder"]) == 1
    assert semi["ladder"][0]["days"] == 2
    assert semi["ladder"][0]["stock_code"] == "688981"
    assert semi["ladder"][0]["stock_name"] == "中芯国际"


def test_leader_extraction():
    result = parse_manual_sector_text(FULL_MARKDOWN)
    by_name = {item["name"]: item for item in result}

    energy = by_name["能源金属"]
    assert energy["leader"] is not None
    assert energy["leader"]["name"] == "融捷股份"
    assert energy["leader"]["code"] == "002192"
    assert energy["leader"]["consecutive_limit_up_days"] == 3

    semi = by_name["半导体"]
    assert semi["leader"] is not None
    assert semi["leader"]["name"] == "中芯国际"
    assert semi["leader"]["code"] == "688981"
    assert semi["leader"]["consecutive_limit_up_days"] == 2


def test_limit_up_stocks_deduplication():
    result = parse_manual_sector_text(FULL_MARKDOWN)
    by_name = {item["name"]: item for item in result}

    energy = by_name["能源金属"]
    codes = [s["code"] for s in energy["limit_up_stocks"]]
    names = [s["name"] for s in energy["limit_up_stocks"]]
    assert codes.count("002466") == 1
    assert names.count("天齐锂业") == 1

    seen = set()
    for stock in energy["limit_up_stocks"]:
        identifier = stock["code"] or stock["name"]
        assert identifier not in seen
        seen.add(identifier)


def test_catalyst_extraction():
    result = parse_manual_sector_text(FULL_MARKDOWN_ENRICHED)
    by_name = {item["name"]: item for item in result}
    assert by_name["能源金属"]["catalyst"] == "碳酸锂价格涨超3.5%，全天领涨"
    assert by_name["半导体"]["catalyst"] == "国产替代逻辑升温，涨超2.1%"


def test_effect_summary_extraction():
    result = parse_manual_sector_text(FULL_MARKDOWN_ENRICHED)
    by_name = {item["name"]: item for item in result}
    assert by_name["能源金属"]["effect_summary"] == "龙头强势，带动整个锂矿板块涨停潮"
    assert by_name["半导体"]["effect_summary"] == "国产替代预期强化"


def test_related_stocks_extraction():
    result = parse_manual_sector_text(FULL_MARKDOWN_ENRICHED)
    by_name = {item["name"]: item for item in result}
    energy_related = by_name["能源金属"]["related_stocks"]
    assert len(energy_related) == 2
    assert energy_related[0]["name"] == "天齐锂业"
    assert energy_related[0]["code"] == "002466"
    assert energy_related[1]["name"] == "赣锋锂业"
    semi_related = by_name["半导体"]["related_stocks"]
    assert len(semi_related) == 2
    assert semi_related[0]["name"] == "韦尔股份"
    assert semi_related[1]["name"] == "兆易创新"


def test_market_sentiment_extraction():
    result = parse_manual_sector_text(FULL_MARKDOWN_ENRICHED)
    assert hasattr(result, "market_sentiment")
    ms = result.market_sentiment
    assert ms is not None
    assert "indices" in ms
    assert len(ms["indices"]) == 2
    idx_by_name = {i["name"]: i for i in ms["indices"]}
    assert "沪指" in idx_by_name
    assert idx_by_name["沪指"]["change_pct"] == -0.33
    assert idx_by_name["沪指"]["value"] == 4079.90
    assert "深成指" in idx_by_name
    assert idx_by_name["深成指"]["change_pct"] == 0.12
    assert ms["market_summary"]["up_count"] == 2036
    assert ms["market_summary"]["down_count"] == 3352
    assert ms["market_summary"]["limit_up_count"] == 68
    assert ms["market_summary"]["limit_down_count"] == 37
    assert ms["capital_flow"]["direction"] == "流出"
    assert ms["capital_flow"]["amount"] == 722.27


# ================================================================
#  Regression tests for real-world Markdown formats (bold-wrapped
#  names, annotated counts, modifiers in counts, flexible flow)
# ================================================================

REAL_WORLD_MARKDOWN = """\
## 一、近3-7日涨幅TOP5板块（附核心催化逻辑）
1. **稀土/小金属**：产业链龙头一季报业绩集体爆发
2. **锂电产业链**：电池级碳酸锂近一月涨幅达12.82%
3. **AI算力/算力租赁/CPO**：政治局会议点名推进算力网建设

## 二、核心板块今日涨停数量
| 板块名称 | 涨停家数 |
| :--- | :--- |
| 锂电产业链 | 21只（含储能） |
| 稀土/小金属 | 13只（稀土永磁方向为主） |
| AI算力/算力租赁/CPO | 10只+ |
| 食品饮料/大消费 | 8只 |

## 三、市场连板梯队（含股票代码+核心属性）
### 3连板（市场最高标）
- **飞马国际（002210）**：稀土/小金属、纺织
- ***ST宇顺（002289）**：稀土/小金属、算力
### 2连板（业绩线主导）
- **利通电子（603629）**：AI算力/算力租赁/CPO
- **永杉锂业（603399）**：锂电产业链、小金属

## 四、板块龙头+带动效应
### 1. 稀土/小金属
- **核心龙头**：北方稀土（板块中军）、翔鹭钨业（业绩弹性先锋）
- **带动涨停数量**：13只
- **具体联动标的**：北方稀土、中国稀土、翔鹭钨业、盛和资源
- **效应总结**：业绩+催化共振，形成极强的首板涨停潮

### 2. 锂电产业链
- **核心龙头**：鹏辉能源（20cm情绪先锋）
- **带动涨停数量**：20只
- **具体联动标的**：鹏辉能源、德方纳米、永杉锂业
- **效应总结**：涨价逻辑验证+储能高景气

## 五、当日市场情绪小结
1. **指数表现**：沪指涨0.71%报4107.51点（创阶段收盘新高），深成指涨1.96%，创业板指涨2.52%。
2. **涨跌分布**：上涨近4000家，下跌约1100家，实际涨停约120家，跌停家数极少。
3. **资金流向**：主力资金大幅涌入储能（+160亿）、小金属（+132亿）。
"""


def test_real_world_bold_table_and_ladder():
    result = parse_manual_sector_text(REAL_WORLD_MARKDOWN)
    assert len(result) > 0

    by_name = {item["name"]: item for item in result}

    # Fuzzy merge combines 稀土/小金属 ← 有色金属/稀土/小金属 → 小金属
    assert "小金属" in by_name
    assert "锂电产业链" in by_name
    assert "AI算力/算力租赁/CPO" in by_name

    rare_earth = by_name["小金属"]
    assert rare_earth["limit_up_count"] == 13
    assert rare_earth["catalyst"] is not None

    lithium = by_name["锂电产业链"]
    assert lithium["limit_up_count"] == 21

    ai = by_name["AI算力/算力租赁/CPO"]
    assert ai["limit_up_count"] == 10


def test_real_world_ladder_bold_names():
    result = parse_manual_sector_text(REAL_WORLD_MARKDOWN)
    by_name = {item["name"]: item for item in result}

    rare_earth = by_name["小金属"]
    ladder_codes = {r["stock_code"] for r in rare_earth["ladder"]}
    assert "002210" in ladder_codes
    assert "002289" in ladder_codes


def test_real_world_leader_bold_labels():
    result = parse_manual_sector_text(REAL_WORLD_MARKDOWN)
    by_name = {item["name"]: item for item in result}

    rare_earth = by_name["小金属"]
    assert rare_earth["leader"] is not None
    assert rare_earth["leader"]["name"] == "北方稀土"
    assert rare_earth["effect_summary"] == "业绩+催化共振，形成极强的首板涨停潮"

    related_names = {s["name"] for s in rare_earth.get("related_stocks", [])}
    assert "中国稀土" in related_names
    assert "翔鹭钨业" in related_names

    lithium = by_name["锂电产业链"]
    assert lithium["leader"] is not None
    assert lithium["leader"]["name"] == "鹏辉能源"


def test_real_world_market_sentiment():
    result = parse_manual_sector_text(REAL_WORLD_MARKDOWN)
    ms = getattr(result, "market_sentiment", None)
    assert ms is not None

    assert len(ms.get("indices", [])) >= 1
    idx_by_name = {i["name"]: i for i in ms["indices"]}
    assert "沪指" in idx_by_name
    assert idx_by_name["沪指"]["change_pct"] == 0.71
    assert idx_by_name["沪指"]["value"] == 4107.51

    assert ms["market_summary"]["up_count"] == 4000
    assert ms["market_summary"]["down_count"] == 1100
    assert ms["market_summary"]["limit_up_count"] == 120

    assert ms["capital_flow"]["direction"] == "流入"
    assert ms["capital_flow"]["amount"] == 160.0


def test_table_annotated_counts():
    text = """\
## 涨停数量
| 板块名称 | 涨停家数 |
| 光伏/新能源 | 8只+ |
| 消费电子 | 5只（含ST） |
"""
    result = parse_manual_sector_text(text)
    assert len(result) == 2
    counts = {item["name"]: item["limit_up_count"] for item in result}
    assert counts["光伏/新能源"] == 8
    assert counts["消费电子"] == 5


def test_ladder_bold_wrapped_names():
    text = """\
## 连板梯队
### 2连板
- **利通电子（603629）**：算力租赁
- **三人行（605168）**：算力租赁
"""
    result = parse_manual_sector_text(text)
    assert len(result) == 1
    sector = result[0]
    assert len(sector["ladder"]) == 2
    codes = {r["stock_code"] for r in sector["ladder"]}
    assert "603629" in codes
    assert "605168" in codes


def test_leader_bold_labels():
    text = """\
## 涨幅TOP5
1. **能源金属**：锂价上涨

## 板块龙头+带动效应
### 1. 能源金属
- **核心龙头**：融捷股份（先锋龙头，3连板）
- **带动涨停数量**：8只
- **具体联动标的**：天齐锂业、赣锋锂业
- **效应总结**：龙头强势涨停潮
"""
    result = parse_manual_sector_text(text)
    assert len(result) == 1
    sector = result[0]
    assert sector["leader"] is not None
    assert sector["leader"]["name"] == "融捷股份"
    assert sector["effect_summary"] == "龙头强势涨停潮"
    assert len(sector.get("related_stocks", [])) == 2


def test_market_sentiment_flexible_flow():
    text = """\
## 市场情绪小结
主力资金大幅涌入储能（+160亿）、小金属（+132亿）
上涨近4000家，下跌约1100家
涨停约120家，跌停家数极少
沪指涨0.71%报4107.51点（创阶段新高）
"""
    result = parse_manual_sector_text(text)
    ms = getattr(result, "market_sentiment", None)
    assert ms is not None
    assert ms["market_summary"]["up_count"] == 4000
    assert ms["market_summary"]["down_count"] == 1100
    assert ms["market_summary"]["limit_up_count"] == 120
    assert ms["capital_flow"]["amount"] == 160.0
    assert ms["capital_flow"]["direction"] == "流入"
    assert len(ms["indices"]) >= 1
    assert ms["indices"][0]["change_pct"] == 0.71
