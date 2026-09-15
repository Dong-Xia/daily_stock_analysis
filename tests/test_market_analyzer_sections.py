# -*- coding: utf-8 -*-
"""英文复盘报告 section 提取回归测试（源码级，无重依赖导入）。

背景：英文 prompt 输出标题改为 '### 4. Sector / Concept Highlights'，
而 _ENGLISH_SECTION_PATTERNS 旧正则只匹配 'Sector Highlights|Sector/Theme Highlights'，
_insert_after_section 不命中时静默原样返回，导致英文报告的板块统计表整段丢失。

本测试用 AST 从源码提取正则与 prompt 标题字面量，两者一旦漂移即失败。
（src.market_analyzer 导入链依赖 newspaper 等运行时库，不适合单测导入。）
"""
import ast
import re
from pathlib import Path

SOURCE = Path(__file__).resolve().parent.parent / "src" / "market_analyzer.py"


def _english_patterns() -> dict:
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "_ENGLISH_SECTION_PATTERNS":
                    result = {}
                    for key, value in zip(node.value.keys, node.value.values):
                        result[key.value] = value.value
                    return result
    raise AssertionError("_ENGLISH_SECTION_PATTERNS not found in source")


def _prompt_sector_headings() -> list:
    """从源码中提取所有 '### 4. Sector...' 形态的标题字面量。"""
    text = SOURCE.read_text(encoding="utf-8")
    return re.findall(r"### 4\. Sector[^\n{]*", text)


def test_english_sector_pattern_matches_all_prompt_headings():
    pattern = _english_patterns()["sector_highlights"]
    headings = _prompt_sector_headings()
    assert headings, "prompt 中未找到 '### 4. Sector' 标题，检查提取逻辑是否过时"
    for heading in headings:
        assert re.search(pattern, heading), f"正则无法匹配实际标题: {heading!r}"


def test_english_sector_pattern_does_not_match_unrelated_headings():
    pattern = _english_patterns()["sector_highlights"]
    assert not re.search(pattern, "### 5. Hotspot & Sentiment")
    assert not re.search(pattern, "### 4. Sentiment Cycle")
