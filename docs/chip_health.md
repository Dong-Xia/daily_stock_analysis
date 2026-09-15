# 持仓筹码体检（/chip-health）

基于本地 3 年日线数据库的筹码引擎，对持仓清单做**底部筹码多日流失检测**，输出减仓判定。与 `ENABLE_CHIP_DISTRIBUTION`（在线筹码快照，供单股分析上下文）是不同能力。

## 数据依赖

- 数据目录 `CHIP_STOCK_DATA_DIR`（默认 `/Users/zhangze/stockData`），需含：
  - `mrmc_cache_3y.pkl` — 全A三年日线指标缓存（由 stockData 收盘流水线 `daily_signal_screen.py` 每日重建）
  - `market_cap_latest.csv` — 最新市值快照（估算股本→换手率）
- 数据不新鲜时页面会显示各行"数据截止日"，体检结果按缓存截止日计算。

## 判定规则（2023–2026 回测验证，见 stockData/筹码策略回测报告.md）

| 灯 | 触发条件 | 回测依据（2025-26，信号后3日下跌概率） |
|---|---|---|
| 🔴 | 底筹连降 7 日且累计流失 >18% | 61.0% |
| 🟠 | 连降 5 日且累计流失 >15% | 60.6% |
| 🟡 | 连降 3 日且累计流失 >8% | 58.4% |
| ⚪ | 3 日流失 >8% 但**非逐日**（骤减又回补） | 量化做T假象，随后均值+0.89%，**勿卖** |
| 🟢 | 底筹稳定或增加 | 继续持有 |

- 筹码算法：通达信式三角分布 + 换手率衰减（日级）。
- "连降N日"即清单口诀"单日筹码不要信，连看两三辨真假"的量化版。
- 附加：获利比例 >90% 标记高位风险 ⚠️。
- 内置成交量单位自校正（历史库=手；个别采集路径曾写股×100，按每票干净期中位量>25倍自动÷100）。

## 使用

WebUI 左侧导航「筹码体检」→ 填持仓（代码/名称/成本价，成本可空）→「保存并开始体检」。约 30–60 秒（子进程载入 ~1GB 缓存）。

## 买入前体检（信号链联动）

在「信号链筛选」页的**日线**结果中，若状态机产出 `今日回踩完成→明日买入` 标的，页面顶部会出现候选横幅与「开始体检」按钮——把这些候选票（`code/name`，`cost` 空）作为临时清单送入同一筹码引擎，用底部筹码流失判断明日买入是否为诱多/派发陷阱。

买入语义转译（底层引擎数值不变，仅结论展示口径）：

| 引擎灯 | 买入决策 |
|---|---|
| 🟢 | 技术+筹码双确认 · 可买 |
| ⚪ | 量化做T假象 · 可正常买 |
| 🟡 | 筹码不稳 · 轻仓/观察 |
| 🟠 | 底筹连降 · 诱多风险，谨慎 |
| 🔴 | 主力派发 · 放弃明日买入 |

> 该候选标签依赖 stockData 侧日线状态机（`dsa_signal/screen_signal.py`）。历史上该分支为死代码（触发当日即复位），日线恒不产出该标签；现已修复，日线回踩完成当日可正确标注。分钟时段一直正常产出。

## API

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/v1/chip-health/status` | 数据目录/缓存状态/已存持仓数 |
| GET/PUT | `/api/v1/chip-health/holdings` | 读取/全量保存持仓清单（`data/chip_holdings.csv`） |
| POST | `/api/v1/chip-health/run` | 执行体检；body 传 `holdings` 则临时体检，不传用已保存清单 |

## 代码位置

- 引擎+服务：`src/services/chip_health_service.py`（也可 CLI：`python3 -m src.services.chip_health_service --holdings-file x.csv --json`）
- 接口：`api/v1/endpoints/chip_health.py`
- 前端：`apps/dsa-web/src/pages/ChipHealthPage.tsx`
- 买入前体检（信号链联动）：`apps/dsa-web/src/api/signalPipeline.ts`（`pickBuyTomorrow`）、`apps/dsa-web/src/utils/buyVerdict.ts`（买入语义转译）、入口在 `apps/dsa-web/src/pages/SignalPipelinePage.tsx`

## 局限

- 回测结论：该体系价值在**避雷/砍尾部**，非高胜率择时；主线题材维度无法量化检验。
- 股本用最新总市值近似（总市值≠流通市值，小流通盘次新股换手会高估）。
- 结果仅供参考，不构成投资建议。
