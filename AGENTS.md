# AGENTS.md

本文件是仓库内 AI 协作规则的唯一真源。如果与脚本、工作流、代码现状不一致，以实际可执行内容为准，并在相关改动中顺手修正文档。修改 AI 治理资产后运行 `python3 scripts/check_ai_assets.py` 确认完整性。

## 硬规则

- 目录边界：后端 `src/`、`data_provider/`、`api/`、`bot/`；Web 前端 `apps/dsa-web/`；桌面端 `apps/dsa-desktop/`；部署/流水线 `scripts/`、`.github/workflows/`、`docker/`
- 未经明确确认，不执行 `git commit`、`git tag`、`git push`。commit message 用英文，不添加 `Co-Authored-By`
- 不写死密钥、账号、路径、模型名、端口或环境差异逻辑
- 优先复用现有模块、配置入口、脚本和测试。不新增平行实现
- 稳定性优先——非当前任务直接需要的重构一律克制
- 新增配置项时同步更新 `.env.example` 及相关文档
- 用户可见变化（CLI/API/部署/通知/报告结构）必须更新文档与 `docs/CHANGELOG.md`
- `CHANGELOG.md` 的 `[Unreleased]` 节用 flat 格式：`- [类型] 描述`，类型为 `新功能`/`改进`/`修复`/`文档`/`测试`/`chore`。不加 `###` 分类标题（减少并发 PR 的 merge conflict）
- `README.md` 用于入门/运行/部署概览；详细说明在 `docs/*.md`
- 变更中英双语文档之一时评估另一份是否需要同步
- 包管理：Python 用 `pip` + `requirements.txt`，前端用 `npm` + `package-lock.json`，CI 用 `requirements-ci.txt`

## AI 协作资产治理

- `CLAUDE.md` 必须是指向 `AGENTS.md` 的软链接（当前已验证：`CLAUDE.md -> AGENTS.md`）
- `.github/copilot-instructions.md` 与 `.github/instructions/*.instructions.md` 是镜像/分层补充；冲突时以 `AGENTS.md` 为准
- 仓库协作 skill 在 `.claude/skills/`（版本库资产），分析产物在 `.claude/reviews/`
- 根目录 `SKILL.md` 与 `docs/openclaw-skill-integration.md` 属于产品或外部集成说明，不是仓库协作规则真源
- `.gitignore` 必须包含 `.claude/*` 但排除 `!.claude/skills/`（避免跟踪分析产物）

## 仓库结构

### 项目定位

股票智能分析系统，覆盖 A 股/港股/美股。主流程：抓取数据 → 技术分析/新闻检索 → LLM 分析 → 生成报告 → 通知推送。

### 关键入口

| 入口 | 说明 |
|------|------|
| `main.py` | CLI 调度入口。`--webui` 映射到 `--serve`（line 834-838），`--webui-only` 映射到 `--serve-only` |
| `server.py` | FastAPI 服务入口（`from api.app import app`） |
| `webui.py` | Web 界面启动脚本（等效 `python main.py --webui-only`） |
| `analyzer_service.py` | 分析服务封装层（解耦 CLI/Web/Bot 调用方） |
| `apps/dsa-web/` | Vite + React Web 前端 |
| `apps/dsa-desktop/` | Electron 桌面端（当前版本 3.12.0） |
| `.github/workflows/` | CI、发布、每日任务 |

### 目录职责

- **`src/core/`** — 主流程编排（pipeline.py、market_review.py、backtest_engine.py、market_profile.py、market_regime.py、market_strategy.py、sector_analyzer.py、trading_calendar.py、config_manager.py、config_registry.py）
- **`src/services/`** — 业务服务层（~37 模块：analysis_service.py、stock_service.py、agent_model_service.py、task_queue.py、system_config_service.py、portfolio_service.py 等）
- **`src/repositories/`** — 数据访问层（stock_repo.py、analysis_repo.py 等）
- **`src/agent/`** — AI Agent 系统（orchestrator、executor、skills、tools、research、agents/）
- **`src/notification_sender/`** — 11 个渠道：wechat、telegram、email、slack、feishu、discord、astrbot、custom_webhook、pushover、pushplus、serverchan3
- **`src/schemas/`** — Schema / 数据结构
- **`data_provider/`** — 15 模块（14 fetcher + `__init__`），含 base/fetcher/adapter。`BaseFetcher` 在 `data_provider/base.py:241`
- **`api/`** — FastAPI 路由（app.py、v1/ 版本化路由）
- **`bot/`** — 机器人接入（dispatcher.py、commands/ 含 ask/chat/history/research 等 11 命令模块）。Bot 命令：`/ask`（技能分析，支持多股对比）、`/chat`（自由对话）、`/history`（会话历史）、`/strategies`（策略列表）、`/research`（深度研究）
- **`strategies/`** — 策略技能 YAML 定义（13 个内置策略 .yaml 文件）。**注**：目录沿用 `strategies/` 命名以兼容既有部署路径，内部代码统一使用 `skill` 命名体系（`src/agent/skills/`）；`src/agent/strategies/` 为纯 import 兼容层，计划下个大版本移除
- **`tests/`** — pytest 测试（标记：unit / integration / network）
- **`scripts/`** — 本地脚本（ci_gate.sh、check_ai_assets.py、build-*、macOS/Windows 构建脚本）
- **`docker/`** — Dockerfile + docker-compose.yml
- **`templates/`** — Jinja2 报告模板
- **`patch/`** — 运行时补丁（eastmoney_patch 等）

### 数据流

```
main.py / api/app.py
  → src/core/pipeline.py
    → src/services/ (业务逻辑)
      → data_provider/ (带 fallback 链)
      → src/repositories/ (持久化)
    → LLM: src/services/agent_model_service.py → LiteLLM (多 Key 负载均衡)
  → src/notification_sender/ (多渠道推送)
```

### 数据源回退链

- **A 股日线**：`efinance` → `akshare` → `tushare` → `pytdx` → `baostock`
- **港股/美股日线**：`longbridge`（条件触发）→ `yfinance` / `akshare`
- **美股大盘指数**（SPX 等）：始终以 `yfinance` 优先
- **实时行情**：`tencent` → `akshare_sina` → `efinance` → `akshare_em`（按 `REALTIME_SOURCE_PRIORITY` 顺序）
- **板块涨跌榜**：`AkShare(EM→Sina)` → `Tushare` → `efinance`

### CI 工作流一览

| 工作流 | 触发 | 说明 |
|--------|------|------|
| `ci.yml` | PR → main | 串行：ai-governance → backend-gate → docker-build；前端变化时加 web-gate |
| `daily_analysis.yml` | 定时(UTC 10:00 工作日) + 手动 | 每日分析，支持 mode/force_run 参数，超时默认 30min（`ANALYSIS_TIMEOUT_MINUTES` var） |
| `pr-review.yml` | PR (py/md/ts/tsx/docs 等) | 安全检测 → 静态检查 → AI 审查 → 自动标签；`ENABLE_AI_REVIEW=false` 可跳过 AI 审查 |
| `auto-tag.yml` | push → main | 仅 commit 包含 `#patch`/`#minor`/`#major` 时触发 |
| `create-release.yml` | tag `v*.*.*` | 从 annotated tag 创建 GitHub Release |
| `desktop-release.yml` | tag `v*.*.*` + 手动 | Windows/macOS 桌面端构建 |
| `docker-publish.yml` / `ghcr-dockerhub.yml` | tag + 手动 | Docker 镜像推送 |
| `network-smoke.yml` | 定时(UTC 02:00 工作日) | 网络依赖测试（非阻断，观测项） |
| `stale.yml` | 定时 | 标记关闭陈旧 Issue/PR |

## 常用命令

### 运行

```bash
python main.py                                   # 正常运行
python main.py --debug                           # 调试模式
python main.py --dry-run                         # 仅获取数据不分析
python main.py --stocks 600519,hk00700,AAPL      # 指定股票
python main.py --market-review                   # 仅大盘复盘
python main.py --schedule                        # 定时任务模式
python main.py --serve | --webui                 # Web 服务 + 分析
python main.py --serve-only | --webui-only       # 仅 Web 服务
python main.py --backtest                        # 运行回测
python main.py --force-run                       # 跳过交易日检查
uvicorn server:app --reload --host 0.0.0.0 --port 8000
python webui.py                                  # 等效 --webui-only
```

`--webui` 在 `main.py` 内部映射为 `--serve`（line 834-838），`--webui-only` 映射为 `--serve-only`。支持旧版 `WEBUI_ENABLED` 环境变量。

### Docker Compose

```bash
docker compose -f docker/docker-compose.yml up -d           # 定时分析
docker compose -f docker/docker-compose.yml up -d server    # API 服务
```

### 后端验证（按顺序）

```bash
./scripts/ci_gate.sh                    # 全部（4 阶段）
./scripts/ci_gate.sh syntax             # py_compile 语法检查
./scripts/ci_gate.sh flake8             # flake8 严重错误 (E9,F63,F7,F82)
./scripts/ci_gate.sh deterministic      # test.sh code + test.sh yfinance
./scripts/ci_gate.sh offline-tests      # pytest -m "not network"
```

### 快速测试

```bash
./test.sh quick       # 单只股票快速测试（600519）
./test.sh a-stock     # A 股（600519,000001）
./test.sh hk-stock    # 港股（hk00700,hk09988）
./test.sh us-stock    # 美股（AAPL）
./test.sh market      # 大盘复盘
./test.sh etf         # ETF 分析（563230,512400）
./test.sh code        # 代码识别测试（无网络依赖）
./test.sh yfinance    # YFinance 代码转换测试（无网络依赖）
./test.sh all         # 运行所有确定性测试
```

### Web / Desktop

```bash
cd apps/dsa-web
npm ci
npm run lint          # eslint
npm run build         # tsc -b + vite build（输出到 ../../static/）
npm run test          # vitest
npm run test:smoke    # playwright（e2e）

cd ../dsa-desktop
npm install
npm run build         # electron-builder
npm run test          # node --test tests/preload.test.js
```

Web 前端打包产物输出到项目根 `static/`（由 vite.config.ts 控制），被 FastAPI 作为静态文件服务。

### PR / CI 证据

```bash
gh pr view <pr_number> --repo ZhuLinsen/daily_stock_analysis
gh pr checks <pr_number> --repo ZhuLinsen/daily_stock_analysis
gh run view <run_id> --log-failed
```

## 默认工作流

1. 判断任务类型（对照 `.github/PULL_REQUEST_TEMPLATE.md`）：`fix / feat / refactor / docs / chore / test`
2. 读现有实现、配置、测试、脚本和文档，再动手
3. 识别改动边界：后端 / API / Web / Desktop / Workflow / Docs / AI 协作资产
4. 判断是否命中高风险区域：配置语义、API/Schema、数据源 fallback、报告结构、认证、调度、发布流程、桌面端启动链路
5. 只做和当前任务直接相关的最小改动
6. 若文档、脚本、工作流描述不一致，优先信任实际代码与工作流
7. 改完后按验证矩阵执行检查
8. 最终交付说明：改了什么、为什么、验证情况、未验证项、风险点、回滚方式

**Issue / PR / Skill 补充：**
- 已有 skill（slash 命令调用）：`/analyze-issue`、`/analyze-pr`、`/fix-issue`
- skill 优先读取 CI/工作流证据，不默认执行 `git pull`、`git push`、`git tag`、`gh pr create`
- 产物保存到 `.claude/reviews/`
- PR 审查顺序：必要性 → 关联性 → 描述完整性 → 验证证据 → 正确性 → 合入判定
- `fix` 类 PR 必须说明：原问题、根因、修复点、回归风险
- 合入阻断条件：正确性/安全问题、阻断型 CI 未通过、PR 描述与实际内容实质性矛盾、缺少回滚方案
- `docs` 任务交付直接写 `Docs only, tests not run`，但仍需说明是否核对命令和文件名

## 验证矩阵

| 改动面 | 适用范围 | 验证方式 |
|--------|----------|----------|
| Python 后端 | `main.py`、`src/`、`data_provider/`、`api/`、`bot/`、`tests/` | 优先 `./scripts/ci_gate.sh`；最低 `python3 -m py_compile` + 最接近的确定性测试 |
| Web 前端 | `apps/dsa-web/` | `npm ci && npm run lint && npm run build` |
| 桌面端 | `apps/dsa-desktop/`、构建脚本、`docs/desktop-package.md` | 先构建 Web，再构建桌面端 |
| API/Schema/认证联动 | `api/**`、`src/schemas/**`、`src/services/**` | 后端验证 + 受影响客户端构建验证 |
| 文档与治理文件 | `README.md`、`docs/**`、`AGENTS.md`、`.github/**`、`.claude/skills/**` | 确认命令/文件名与实际仓库一致；改 AI 治理资产时运行 `python3 scripts/check_ai_assets.py` |
| 网络/三方依赖 | 涉及 timeout/retry/fallback 的改动 | 先跑离线/确定性检查；确认降级路径仍成立 |

Python 后端顺序：`syntax → flake8(严重) → deterministic → offline-tests`

## 稳定性护栏

- **配置与运行入口**：改 `.env` 语义/默认值/CLI 参数/启动方式/调度语义时，同时评估本地、Docker、Actions、API、Web、Desktop 的影响。新配置优先做到不配可运行，配置后增强能力
- **数据源与 fallback**：改 `data_provider/` 时关注优先级、失败降级、字段标准化、缓存与超时。单数据源失败不应拖垮整体流程
- **API/Web/Desktop 兼容**：改 API/Schema/认证/报告载荷时检查后端、Web、Desktop 兼容；默认优先追加字段、保留旧字段
- **报告/Prompt/通知**：改报告结构/Prompt/提取器/通知模板/机器人链路时检查上下游兼容。改 `src/services/image_stock_extractor.py` 中 `EXTRACT_PROMPT` 时，PR 描述必须附完整最新 prompt
- **工作流/发布/打包**：改自动 tag/Release/Docker 发布/分析调度/桌面端打包时评估触发条件、产物路径、权限边界。自动 tag 默认 opt-in（仅含 `#patch`/`#minor`/`#major` 的 commit 触发）。手动 tag 必须用 annotated tag
- **Proxy 仅为本地环境**：GitHub Actions 环境自动跳过代理配置（`main.py` line 36）

## 常见实现模式

### 数据源修改
1. 继承 `BaseFetcher`（`data_provider/base.py`）
2. 在 `base.py` 的 `DataFetcherManager` 中注册新数据源
3. 定义 fallback 顺序与字段映射逻辑
4. 修改后执行 `./scripts/ci_gate.sh`

### Service / API 层新增
- 在 `src/services/` 新建服务类，Repository 层使用现有数据访问模式，新增单元测试
- API 路由在 `api/app.py` 或 `api/v1/` 下注册，在 `src/schemas/` 定义 Schema，前端如需调用则更新 `apps/dsa-web/` 接口定义

### 报告模板修改
- 模板位于 `templates/`（Jinja2 格式）
- 使用 `REPORT_RENDERER_ENABLED=true` 预览
- 改 `EXTRACT_PROMPT` 时必须完整附在 PR 描述中

### 配置新增
- 所有新配置项需在 `.env.example` 中带注释说明
- 命名用大写蛇形（`LIKE_THIS`）
- 新增后评估本地/Docker/Actions/API/Web/Desktop 影响

## 后端特定指导

- 保留现有管道边界，复用 services/repositories/schemas/fallback，勿创建平行路径
- 改 config/CLI 参数/调度语义/API 行为/认证/报告载荷时同步 `.env.example` 并评估 Web/Desktop 兼容
- 改 `data_provider/` 时保留优先级、字段标准化、超时/重试和降级逻辑
- 除非需求明确要求 fail-fast，否则单 provider/通知/可选集成失败不应中断主流程
- SQLite 默认 WAL 模式（`SQLITE_WAL_ENABLED=true`），批量写入注意锁竞争（`SQLITE_BUSY_TIMEOUT_MS=5000`，重试 3 次，指数退避）

## 客户端特定指导

- Web 技术栈：React 19、React Router 7、zustand、Tailwind CSS 4、recharts、react-markdown + remark-gfm。测试：vitest（单元）、playwright（e2e）
- 构建产物输出到项目根 `static/`，由 FastAPI 提供静态文件服务（见 `vite.config.ts`）
- 验证：`cd apps/dsa-web && npm ci && npm run lint && npm run build`
- Desktop 验证：先构建 Web，再构建 `apps/dsa-desktop`；平台限制无法验证时要在交付中说明具体风险
- 前端使用 `npm`（含 `package-lock.json`），不用 `yarn`/`pnpm`

## 代码风格

- Python：`black` 格式化（line-length=120），`isort` 排序（profile=black），`flake8` 检查（忽略 E501/W503/E203/E402）
- TypeScript/TSX：ESLint 检查
- `pyproject.toml` 配置了 `black`、`isort`、`bandit` 规则
- `setup.cfg` 配置了 `flake8` 和 `pytest` 规则
- pytest 标记：`unit`（快速离线）、`integration`（服务级无网络）、`network`（需网络）；默认离线：`pytest -m "not network"`

## 调试指南

- 应用日志写入 `logs/stock_analysis_YYYYMMDD.log`；`--debug` 或 `LOG_LEVEL=DEBUG` 启用 DEBUG 级别
- API 调试：`uvicorn server:app --reload --host 0.0.0.0 --port 8000`，Swagger 在 `http://localhost:8000/docs`

| 症状 | 排查方向 |
|------|----------|
| 分析失败 | 检查 `logs/` 中最近日志，关注 `data_provider` 与 `agent_model_service` 错误 |
| LLM 调用失败 | 确认 `LITELLM_MODEL`、API Key、网络连通性。`LITELLM_MODEL` 可能需要 `provider/model` 前缀（如 `openai/deepseek-chat`）|
| 数据源失败 | 检查对应 fetcher 的 fallback 链配置 |
| 前端构建错误 | 检查 `node_modules`、npm 版本、`package-lock.json` |
| Docker 问题 | 参考 `docker/Dockerfile` 多阶段构建流程，注意 `wkhtmltopdf` 依赖 |

---

*修改 AI 治理资产后运行 `python3 scripts/check_ai_assets.py` 确认完整性。*
