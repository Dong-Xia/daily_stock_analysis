# -*- coding: utf-8 -*-
"""
Industry Research Screener - 产业链研究战法选股服务

基于逆向工程拆解产业链BOM，锁定"扩产周期长、技术门槛高、不可替代"的物理级瓶颈环节，
筛选市值30-500亿的中小盘隐形冠军，穿透财务拐点（毛利率、资本开支），
并通过AI红队测试和熔断机制进行风险管控。
"""
from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

import litellm

logger = logging.getLogger(__name__)


@dataclass
class BottleneckAnalysis:
    sector: str = ""
    bottleneck_description: str = ""
    bottleneck_reason: str = ""
    key_technologies: List[str] = field(default_factory=list)
    expansion_cycle: str = ""
    substitution_risk: str = ""


@dataclass
class IndustryCandidate:
    code: str = ""
    name: str = ""
    market_cap_yi: float = 0.0
    industry: str = ""
    sub_sector: str = ""
    gross_margin: float = 0.0
    gross_margin_change: float = 0.0
    capex_growth: float = 0.0
    revenue_yoy: float = 0.0
    profit_yoy: float = 0.0
    institutional_coverage: str = ""
    bottleneck_match: str = ""
    red_team_report: str = ""
    circuit_breakers: List[Dict[str, str]] = field(default_factory=list)
    composite_score: float = 0.0


@dataclass
class IndustryResearchResult:
    date: str = ""
    sector: str = ""
    bottleneck: Optional[BottleneckAnalysis] = None
    total_scanned: int = 0
    after_market_cap: int = 0
    after_financial: int = 0
    candidates: List[IndustryCandidate] = field(default_factory=list)
    elapsed_seconds: float = 0.0


INDUSTRY_RESEARCH_PROMPT = """你是一位资深的产业研究专家和量化投资分析师。请对【{sector}】行业进行深度产业链分析。

## 分析框架

### 第一步：逆向拆解BOM（物料清单）
分析该行业的完整产业链，从终端产品逆向拆解到原材料/设备/零部件。
识别哪个底层环节具有以下特征：
- 扩产周期长（需要6-18个月以上）
- 技术门槛高（需要特殊工艺、设备或认证）
- 不可替代（没有成熟的替代方案）

### 第二步：锁定非对称标的
在上述瓶颈环节中，找出：
- 市值在30亿-500亿人民币的中小盘股
- 机构覆盖率低（卖方研报少于5篇/年）
- 细分领域的隐形冠军（市占率>20%）
- 低成本占比（原材料成本占产品成本>50%）
- 高失效风险（一旦断供，下游损失巨大）

### 第三步：穿透财务拐点
分析候选标的的财务数据：
- 过去两季度毛利率是否因供需失衡出现爆发性拐点（环比提升>5个百分点）
- 资本支出（CapEx）是否在秘密爬坡（同比增长>30%）以承接未来的爆发需求

### 第四步：AI红队测试
假设你是持有大量空头的分析师，从以下维度写一份正伪报告：
1. 技术路径替代：是否有替代技术正在研发？
2. 大客户自研：大客户是否会自己做这个环节？
3. 供应链断裂：原材料供应是否有风险？

### 第五步：制定熔断机制
为每个候选标的拟定未来6个月的关键可证伪里程碑：

请严格按照以下JSON格式输出：
```json
{{
  "bottleneck": {{
    "description": "瓶颈环节描述",
    "reason": "为什么是瓶颈",
    "key_technologies": ["技术1", "技术2"],
    "expansion_cycle": "扩产周期描述",
    "substitution_risk": "替代风险评估"
  }},
  "candidates": [
    {{
      "code": "股票代码",
      "name": "股票名称",
      "market_cap_yi": 市值(亿),
      "industry": "细分行业",
      "sub_sector": "产业链位置",
      "gross_margin": 毛利率(%),
      "gross_margin_change": 毛利率变化(百分点),
      "capex_growth": 资本开支增速(%),
      "revenue_yoy": 营收同比(%),
      "profit_yoy": 利润同比(%),
      "institutional_coverage": "机构覆盖情况",
      "bottleneck_match": "与瓶颈的匹配度说明",
      "red_team_report": "红队测试报告（技术替代/客户自研/供应链风险）",
      "circuit_breakers": [
        {{"milestone": "里程碑描述", "deadline": "截止时间", "consequence": "未达成后果"}}
      ],
      "composite_score": 综合评分(0-100)
    }}
  ]
}}
```

## 重要提醒
- 数据基于你的训练知识截止日期，需标注信息时效性
- 每个候选标的必须有明确的红队报告和熔断机制
- 综合评分基于：瓶颈匹配度(30%) + 财务拐点(25%) + 机构低覆盖(20%) + 红队风险可控(25%)
- 只输出JSON，不要输出其他内容"""


class IndustryResearchScreener:
    """产业链研究战法选股器"""

    def __init__(
        self,
        model: str = None,
        min_market_cap_yi: float = 30.0,
        max_market_cap_yi: float = 500.0,
        min_composite_score: float = 60.0,
    ):
        self.model = model or self._get_default_model()
        self.min_market_cap_yi = min_market_cap_yi
        self.max_market_cap_yi = max_market_cap_yi
        self.min_composite_score = min_composite_score

    def _get_default_model(self) -> str:
        try:
            from src.config import get_config
            config = get_config()
            return config.litellm_model or "openai/gpt-4o-mini"
        except Exception:
            return "openai/gpt-4o-mini"

    def screen(self, sector: str) -> IndustryResearchResult:
        """执行产业链研究选股

        Args:
            sector: 行业/板块名称，如"半导体"、"新能源"、"医药"

        Returns:
            IndustryResearchResult 研究结果
        """
        t0 = time.time()
        today = datetime.now().strftime("%Y-%m-%d")

        # Step 1: LLM产业链分析
        bottleneck, candidates_raw = self._llm_industry_analysis(sector)

        # Step 2: 市值筛选
        candidates_filtered = [
            c for c in candidates_raw
            if self.min_market_cap_yi <= c.market_cap_yi <= self.max_market_cap_yi
        ]
        after_market_cap = len(candidates_filtered)

        # Step 3: 评分筛选
        candidates_final = [
            c for c in candidates_filtered
            if c.composite_score >= self.min_composite_score
        ]

        elapsed = time.time() - t0
        logger.info(
            "产业链研究选股完成: sector=%s, bottleneck=%s, candidates=%d, elapsed=%.1fs",
            sector, bool(bottleneck), len(candidates_final), elapsed,
        )

        return IndustryResearchResult(
            date=today,
            sector=sector,
            bottleneck=bottleneck,
            total_scanned=len(candidates_raw),
            after_market_cap=after_market_cap,
            after_financial=len(candidates_final),
            candidates=candidates_final,
            elapsed_seconds=round(elapsed, 1),
        )

    def _llm_industry_analysis(
        self, sector: str
    ) -> tuple[Optional[BottleneckAnalysis], List[IndustryCandidate]]:
        """调用LLM进行产业链分析"""
        prompt = INDUSTRY_RESEARCH_PROMPT.format(sector=sector)

        try:
            response = litellm.completion(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=4000,
            )

            content = response.choices[0].message.content
            # 提取JSON
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]

            data = json.loads(content.strip())

            # 解析瓶颈分析
            bottleneck = None
            if data.get("bottleneck"):
                b = data["bottleneck"]
                bottleneck = BottleneckAnalysis(
                    sector=sector,
                    bottleneck_description=b.get("description", ""),
                    bottleneck_reason=b.get("reason", ""),
                    key_technologies=b.get("key_technologies", []),
                    expansion_cycle=b.get("expansion_cycle", ""),
                    substitution_risk=b.get("substitution_risk", ""),
                )

            # 解析候选标的
            candidates = []
            for c in data.get("candidates", []):
                candidate = IndustryCandidate(
                    code=c.get("code", ""),
                    name=c.get("name", ""),
                    market_cap_yi=c.get("market_cap_yi", 0),
                    industry=c.get("industry", ""),
                    sub_sector=c.get("sub_sector", ""),
                    gross_margin=c.get("gross_margin", 0),
                    gross_margin_change=c.get("gross_margin_change", 0),
                    capex_growth=c.get("capex_growth", 0),
                    revenue_yoy=c.get("revenue_yoy", 0),
                    profit_yoy=c.get("profit_yoy", 0),
                    institutional_coverage=c.get("institutional_coverage", ""),
                    bottleneck_match=c.get("bottleneck_match", ""),
                    red_team_report=c.get("red_team_report", ""),
                    circuit_breakers=c.get("circuit_breakers", []),
                    composite_score=c.get("composite_score", 0),
                )
                candidates.append(candidate)

            return bottleneck, candidates

        except Exception as e:
            logger.error("LLM产业链分析失败: %s", e)
            return None, []
