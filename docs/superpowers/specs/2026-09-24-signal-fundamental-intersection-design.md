# 设计:信号链 × 基本面交集过滤

- 日期:2026-09-24
- 状态:已与用户确认设计,待实现
- 类型:新功能(feat)

## 1. 背景与目标

信号链页面(`/signal-pipeline`)每日产出的信号股票较多,用户只想关注"有信号 **且** 基本面好"的股票。本功能在信号链页面新增一个过滤视图:把信号链结果与基本面筛选(选股第 3 步的 `FundamentalScreener`)的结果取交集,只展示交集股票,并增补基本面指标列。

**硬性约束:不覆盖原信号链分析结果。** CSV 文件、`/results` 端点、默认表格视图全部不动;过滤是叠加视图,开关关闭即恢复原表。

## 2. 需求决策(用户已确认)

| 决策点 | 结论 |
|--------|------|
| 展示位置 | 信号链页面结果表格上方加"仅看基本面达标"开关,同一张表格切换视图 |
| "基本面好"口径 | 三条硬性标准全过:营收同比≥20% + 净利润同比≥50% + 净利润≥0.5亿;**不受**现有 `max_candidates=50` 展示截断影响 |
| 交集行顺序 | 保持信号链 CSV 原顺序(信号状态自带优先级语义),不按基本面评分重排 |
| 失败降级 | AkShare 财报拉取失败时红字提示,表格回退显示全部信号,不阻塞 |

## 3. 架构与数据流

```
SignalPipelinePage 开关"仅看基本面达标"
  → GET /api/v1/signal-pipeline/fundamental-filter?date&timeframe
    → 复用现有 CSV 文件解析(只读)
    → FundamentalScreener.get_pass_map():全市场财报 → 三条标准过滤(不截断)→ Dict[代码, 基本面字段](6h 缓存)
    → 取交集,信号行增补基本面列
  → 前端渲染交集表格
```

代码格式两边均为裸 6 位数字符串(信号链 CSV 实测 `000429`;基本面候选来自 AkShare `股票代码`),直接字符串相等取交集,仅做 strip。

## 4. 组件设计

### 4.1 `src/services/fundamental_screener.py`

- 抽私有 helper `_fetch_quarter_df(quarter_date) -> pd.DataFrame`:拉 `ak.stock_yjbb_em` + dropna + 三列数值化 + `_pass_revenue` / `_pass_profit` / `_pass_net_profit` 布尔列 + `_score` 评分列。现有 `screen()` 改为调用该 helper,行为不变(消除两处重复)。
- 新增 `get_pass_map(quarter_date: Optional[str] = None) -> Dict[str, Dict[str, Any]]`:基于 helper,返回**全部**通过三条标准的股票(不做 top-N 截断),结构:
  ```python
  { "600519": {"name", "revenue_yoy", "profit_yoy", "net_profit"(元), "industry", "composite_score"}, ... }
  ```
- **缓存**:类级 `_PASS_MAP_CACHE: Dict[quarter_date, (fetched_at_monotonic, pass_map)]`,TTL 6 小时(模块常量)。财报数据低频变化;uvicorn 单进程部署,重启后首拉一次。缓存过期或首次调用时重新拉取;AkShare 异常向上抛,由端点转 502。

### 4.2 `api/v1/endpoints/signal_pipeline.py`

- 从 `get_results` 中抽私有函数 `_load_signal_df(date, timeframe)`(fundflow 优先的文件解析 + 列重命名,404 语义不变),`get_results` 与新端点共用。
- 新端点:
  ```
  GET /api/v1/signal-pipeline/fundamental-filter?date=YYYY-MM-DD&timeframe=daily
  ```
  响应模型 `FundamentalFilterResults`:
  ```python
  { "date", "timeframe", "timeframe_label", "quarter",
    "total": int,      # 原信号总数
    "matched": int,    # 交集数
    "rows": [ ... ] }  # 原信号行全部字段(中文 key 原样)+ 增补 4 个 key
  ```
- 增补 key(与现有行中文 key 风格一致):`营收同比%`、`利润同比%`、`净利润(亿)`、`基本面评分`,数值已格式化(前两者 1 位小数,净利润 2 位小数,评分 1 位小数)。
- 交集行保持 CSV 原顺序。
- 错误:信号 CSV 不存在 → 404(同现有);财报拉取失败 → `HTTPException(502, "财报数据获取失败: ...")`。

### 4.3 前端 `apps/dsa-web`

**`src/api/signalPipeline.ts`**
- 新增 `FundamentalFilterResults` 接口与 `fundamentalFilter(date, timeframe)` 方法(外层 key 无需 camelCase 转换,rows 中文 key 原样,同 `results()` 先例)。

**`src/pages/SignalPipelinePage.tsx`**
- 新增状态:`fundOn`(开关)、`fundLoading`、`fundResults`、`fundError`。
- 结果表格上方新增控制条:
  - 开关:"仅看基本面达标"
  - 灰字提示:`财报季度 {quarter} · 营收≥20% / 利润≥50% / 净利润≥0.5亿`
- 触发时机与基础结果加载保持同步:①开关从关→开时按当前 `(date, activeTab)` 拉取;②开关开着时,基础结果重新加载完成(切 Tab、流水线跑完、初始加载)后自动重拉。改日期本身不触发(与页面现有行为一致:改日期需切 Tab 或重跑流水线才刷新结果)。开关关闭即恢复原表(不请求)。
- 表格:开关开着且拉取成功 → 渲染 `fundResults.rows`,同一张表尾部追加 4 列(营收同比 / 利润同比 / 净利润亿 / 基本面评分);页脚显示 `基本面达标 X / 信号总数 M`。`SignalRow` 行组件以 prop 控制是否渲染基本面单元格。
- 降级:拉取失败 → 开关旁红字显示错误,表格回退渲染原 `results`;交集为 0 → 空态提示"当前时段信号股中无基本面达标标的"。

## 5. 边界与降级

| 场景 | 行为 |
|------|------|
| 财报季度切换期(如 10 月后自动切 Q3 但数据不完整) | 沿用现有 `_resolve_latest_quarter` 自动选季,响应带 `quarter` 字段,前端展示可见 |
| AkShare 偶发失败 | 502 → 前端红字 + 回退原表 |
| 交集为 0 | 空态提示 |
| 缓存 | 6h TTL,同日反复开关只拉一次;多 worker 部署时各自缓存(仅多拉一次,无正确性问题) |
| 原信号链结果 | CSV、`/results`、默认视图零改动 |

## 6. 测试与验证

- 新增 `tests/test_fundamental_screener_pass_map.py`(unit,mock AkShare df):
  - 三条标准判定(边界值)
  - 评分计算
  - 不截断(构造 >50 只通过)
  - 缓存命中(第二次调用不重新拉取)
  - `screen()` 重构后行为不变(通过数/截断/criteria)
- 新增端点测试(mock screener + 临时 CSV 文件):交集正确、增补字段、顺序保持、404、502。
- 运行方式:`.venv/bin/python -m pytest`(系统 3.9 会收集失败);后端整体走 `./scripts/ci_gate.sh`。
- 前端:`npm run lint && npm run build`。

## 7. 文档与配置

- `docs/CHANGELOG.md` `[Unreleased]` 加一条:`- [新功能] 信号链页面新增"仅看基本面达标"过滤视图,展示信号与基本面(三标准全过)交集`
- 无新增配置项,不动 `.env.example`。

## 8. 风险与回滚

- 风险:低。纯叠加只读视图;最坏情况为新端点报错,原功能不受影响。
- 回滚:revert 对应 commit 即可;无数据迁移、无配置变更、无外部依赖变化。
