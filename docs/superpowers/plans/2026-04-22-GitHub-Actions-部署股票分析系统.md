# GitHub Actions 部署股票分析系统实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 GitHub 上部署股票智能分析系统，实现每日自动分析股票并推送至企业微信

**Architecture:** Fork 原仓库 → 配置 GitHub Secrets（STOCK_LIST、AI API Key、企业微信 Webhook）→ 启用 Actions 工作流 → 定时执行分析 → 推送决策仪表盘

**Tech Stack:** GitHub Actions, Python, FastAPI, AkShare/Tushare/YFinance（数据源）, LiteLLM（AI 模型调用）

---

## 部署架构文件结构

```
daily_stock_analysis/
├── .github/
│   └── workflows/
│       └── daily_analysis.yml  (GitHub Actions 工作流配置)
├── docs/
│   └── superpowers/
│       ├── plans/
│       │   └── 2026-04-22-GitHub-Actions-部署股票分析系统.md  (本计划)
│       └── specs/
│           └── 2026-04-22-部署-stock分析系统-design.md  (设计文档)
└── .env.example  (环境变量配置示例)
```

---

## 部署步骤

### Task 1: Fork 原仓库到个人 GitHub 账号

**文件:**
- 创建: `用户个人仓库: Dong-Xia/daily_stock_analysis` (Fork 操作)

**步骤:**

- [ ] **Step 1: Fork 仓库**

操作步骤：
1. 打开 https://github.com/Dong-Xia/daily_stock_analysis
2. 点击右上角 "Fork" 按钮
3. 确认 Fork 到您的 GitHub 账号
4. 等待 Fork 完成（约 30 秒）

预期结果：
- 在您的 GitHub 账号下创建了新仓库：`您的用户名/daily_stock_analysis`
- 新仓库包含所有源代码和配置文件

- [ ] **Step 2: 验证 Fork 成功**

命令：
```bash
gh repo view YOUR_USERNAME/daily_stock_analysis
```

预期输出：
- 仓库存在
- 仓库类型为 fork
- 仓库 URL 正确

- [ ] **Step 3: 克隆到本地（可选）**

命令：
```bash
cd /Users/zhangze/Desktop/app/stock
git clone https://github.com/YOUR_USERNAME/daily_stock_analysis.git
cd daily_stock_analysis
```

预期结果：
- 本地获得仓库副本
- 可以看到所有源代码文件

- [ ] **Step 4: 验证工作流文件存在**

命令：
```bash
ls -la .github/workflows/
```

预期输出：
```
daily_analysis.yml
```

- [ ] **Step 5: Commit (如果进行了本地克隆)**
```bash
git add .
git commit -m "feat: fork daily_stock_analysis repository"
git push origin main
```

---

### Task 2: 配置 GitHub Secrets - 股票列表

**文件:**
- 修改: `用户仓库: Dong-Xia/daily_stock_analysis` (GitHub Secrets)

**步骤:**

- [ ] **Step 1: 打开仓库 Secrets 页面**

操作步骤：
1. 进入您的 GitHub 仓库：`https://github.com/YOUR_USERNAME/daily_stock_analysis`
2. 点击 "Settings" 标签
3. 点击左侧菜单 "Secrets and variables" → "Actions"
4. 点击 "New repository secret" 按钮

- [ ] **Step 2: 添加 STOCK_LIST Secret**

操作步骤：
1. Name 输入: `STOCK_LIST`
2. Value 输入: `600519,hk00700,AAPL,TSLA`
3. 点击 "Add secret"

预期结果：
- Secret 列表中出现 `STOCK_LIST`
- Value 不显示（已加密）

**Stock List 说明：**
- `600519` - 贵州茅台（A股）
- `hk00700` - 腾讯控股（港股）
- `AAPL` - Apple（美股）
- `TSLA` - Tesla（美股）

可以添加更多股票代码，格式为：`A股代码,港股代码,美股代码,美股代码`

- [ ] **Step 3: 验证 Secret 配置**

操作步骤：
1. 在 Secrets 页面查看 `STOCK_LIST`
2. 确认类型为 "Repository secret"
3. 确认可以点击 "Update" 或 "Delete" 按钮

---

### Task 3: 配置 GitHub Secrets - AI 模型 API Key

**文件:**
- 修改: `用户仓库: Dong-Xia/daily_stock_analysis` (GitHub Secrets)

**步骤:**

- [ ] **Step 1: 确定 AI 模型类型并获取 API Key**

选项 A: DeepSeek
```
OPENAI_API_KEY=sk-deepseek-your-key
OPENAI_BASE_URL=https://api.deepseek.com/v1
LLM_MODEL=openai/deepseek-chat
```

选项 B: OpenAI
```
OPENAI_API_KEY=sk-your-openai-key
LLM_MODEL=gpt-4o
```

选项 C: Claude
```
ANTHROPIC_API_KEY=sk-ant-your-claude-key
ANTHROPIC_MODEL=claude-3-5-sonnet-20241022
LLM_MODEL=claude-3-5-sonnet-20241022
```

选项 D: AIHubMix
```
AIHUBMIX_KEY=your-aihubmix-key
LLM_MODEL=openai/gemini-3.1-pro-preview
```

选择您已经拥有的 API Key 类型，获取对应的 Key。

- [ ] **Step 2: 添加 OPENAI_API_KEY Secret**

操作步骤：
1. 在 Secrets 页面点击 "New repository secret"
2. Name 输入: `OPENAI_API_KEY`
3. Value 输入: 您的 API Key（如 `sk-deepseek-xxxxx`）
4. 点击 "Add secret"

- [ ] **Step 3: 添加 OPENAI_BASE_URL Secret（如使用 DeepSeek）**

操作步骤：
1. Name 输入: `OPENAI_BASE_URL`
2. Value 输入: `https://api.deepseek.com/v1`
3. 点击 "Add secret"

- [ ] **Step 4: 添加 LITELLM_MODEL Secret**

操作步骤：
1. Name 输入: `LITELLM_MODEL`
2. Value 输入: `openai/deepseek-chat`
3. 点击 "Add secret"

- [ ] **Step 5: 验证 AI Secret 配置**

操作步骤：
1. 检查 Secrets 页面，确认以下 Secret 已添加：
   - `OPENAI_API_KEY`
   - `OPENAI_BASE_URL`（如有）
   - `LITELLM_MODEL`

2. 验证每个 Secret 的 Value 都是加密状态

---

### Task 4: 配置 GitHub Secrets - 企业微信 Webhook

**文件:**
- 修改: `用户仓库: Dong-Xia/daily_stock_analysis` (GitHub Secrets)

**步骤:**

- [ ] **Step 1: 创建企业微信机器人**

操作步骤：
1. 登录企业微信 → 打开目标工作群
2. 点击群设置（齿轮图标）→ 群机器人
3. 点击 "添加机器人"
4. 选择 "自定义" → "创建"
5. 输入机器人名称：`股票分析助手`
6. 点击 "完成" → "复制"

预期结果：
- 获得一个 Webhook URL，格式如：
  ```
  https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=YOUR_KEY_HERE
  ```

- [ ] **Step 2: 提取 Webhook Key**

操作步骤：
1. 从 Webhook URL 中提取 `key=` 后面的值
2. 示例：
   ```
   https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=abcd1234-5678-90ef-ghij-klmnopqrstuv
   ```
   提取的 Key: `abcd1234-5678-90ef-ghij-klmnopqrstuv`

- [ ] **Step 3: 添加 WECHAT_WEBHOOK_URL Secret**

操作步骤：
1. 在 Secrets 页面点击 "New repository secret"
2. Name 输入: `WECHAT_WEBHOOK_URL`
3. Value 输入: 完整的 Webhook URL
   ```
   https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=abcd1234-5678-90ef-ghij-klmnopqrstuv
   ```
4. 点击 "Add secret"

- [ ] **Step 4: 验证 Webhook Secret 配置**

操作步骤：
1. 检查 Secrets 页面，确认 `WECHAT_WEBHOOK_URL` 已添加
2. 验证 Webhook URL 格式正确
3. （可选）在 Webhook URL 前添加备注，方便识别

---

### Task 5: 启用 GitHub Actions Workflow

**文件:**
- 修改: `用户仓库: Dong-Xia/daily_stock_analysis` (Actions Settings)

**步骤:**

- [ ] **Step 1: 打开 Actions 设置页面**

操作步骤：
1. 进入您的 GitHub 仓库：`https://github.com/YOUR_USERNAME/daily_stock_analysis`
2. 点击 "Actions" 标签
3. 点击左侧 "I understand my workflows, go ahead and enable them"

预期结果：
- 页面显示 "You've successfully enabled GitHub Actions"
- 可以看到 workflow 列表

- [ ] **Step 2: 验证工作流文件存在**

操作步骤：
1. 检查 Actions 页面是否显示 `daily_stock_analysis.yml` workflow
2. 如果未显示，说明工作流文件不在标准位置，需要检查文件路径

预期结果：
- Actions 页面显示 "daily_stock_analysis" workflow
- Workflow 状态为 "Ready to run" 或类似

- [ ] **Step 3: 检查工作流文件位置**

命令（在本地克隆的仓库中）：
```bash
ls -la .github/workflows/
```

预期输出：
```
daily_analysis.yml
```

如果文件不在 `daily_analysis.yml`，记下正确的文件名，后续步骤需要相应调整。

---

### Task 6: 手动触发 Workflow 测试

**文件:**
- 修改: `用户仓库: Dong-Xia/daily_stock_analysis` (Actions 页面)

**步骤:**

- [ ] **Step 1: 打开 workflow 运行页面**

操作步骤：
1. 进入仓库 "Actions" 标签
2. 点击 "daily_stock_analysis" workflow
3. 点击右上角 "Run workflow" 按钮
4. 选择分支：`main` 或 `master`
5. 点击 "Run workflow" 按钮

预期结果：
- 页面显示新的 workflow 运行，状态为 "In progress"
- 工作流包含多个步骤：Checkout、Setup Python、Install Dependencies、Run Analysis 等

- [ ] **Step 2: 监控 workflow 执行**

操作步骤：
1. 等待 workflow 完成（预计 5-15 分钟）
2. 定期刷新页面查看进度
3. 查看每个步骤的日志输出

预期结果：
- 所有步骤成功执行（绿色 ✅）
- 无错误或警告

- [ ] **Step 3: 检查日志输出**

操作步骤：
1. 在 workflow 运行页面点击具体的步骤
2. 查看日志输出，重点关注：
   - 检查是否读取了配置的 Secrets
   - 检查是否执行了股票分析
   - 检查是否生成了报告
   - 检查是否成功发送到企业微信

关键日志检查点：
```
[INFO] Loading configuration from .env
[INFO] STOCK_LIST: 600519,hk00700,AAPL,TSLA
[INFO] Running analysis for: 600519
[INFO] Analysis completed successfully
[INFO] Sending report to WeChat
[INFO] Report sent successfully
```

- [ ] **Step 4: 检查企业微信群是否收到消息**

操作步骤：
1. 打开配置了 Webhook 的企业微信群
2. 查看是否收到股票分析推送消息

预期结果：
- 收到决策仪表盘消息
- 包含股票名称、代码、状态、评分、观点
- 包含股票详情：重要信息、风险警报、利好催化等

---

### Task 7: 验证定时任务配置

**文件:**
- 修改: `用户仓库: Dong-Xia/daily_stock_analysis` (Actions workflow 文件)

**步骤:**

- [ ] **Step 1: 检查工作流触发时间**

操作步骤：
1. 打开仓库 "Actions" 标签
2. 点击 "daily_stock_analysis" workflow
3. 查看右上角 "Schedule" 时间

预期结果：
- 看到 cron 表达式，如：
  ```
  At 18:00 every weekday
  ```

默认配置：每工作日 18:00（北京时间）

- [ ] **Step 2: 验证工作日检测机制**

操作步骤：
1. 在日志中查找以下关键信息：
   ```
   [INFO] Checking if today is a trading day
   [INFO] Today is a trading day (skip non-trading days)
   [INFO] Skipping non-trading day (weekend or holiday)
   ```

预期结果：
- 工作日自动执行
- 周末自动跳过
- 节假日自动跳过

- [ ] **Step 3: （可选）修改定时时间**

如果需要修改执行时间：

操作步骤：
1. 在本地克隆的仓库中编辑 `.github/workflows/daily_analysis.yml`
2. 找到 `on:` → `schedule:` 部分
3. 修改 cron 表达式

示例：
```yaml
on:
  schedule:
    - cron: '0 18 * * 1-5'  # 工作日 18:00（北京时间）
```

注意：GitHub Actions 使用 UTC 时间，北京时间是 UTC+8

转换示例：
- UTC 18:00 = 北京时间 02:00（第二天）
- 北京时间 18:00 = UTC 10:00

- [ ] **Step 4: 提交并推送修改**

命令：
```bash
git add .github/workflows/daily_analysis.yml
git commit -m "config: adjust schedule to 18:00 Beijing time"
git push origin main
```

---

### Task 8: 配置新闻搜索 API（推荐）

**文件:**
- 修改: `用户仓库: Dong-Xia/daily_stock_analysis` (GitHub Secrets)

**步骤:**

- [ ] **Step 1: 注册 Tavily API**

操作步骤：
1. 访问 https://tavily.com/
2. 注册账号
3. 获取 API Key

预期结果：
- 获得 Tavily API Key，格式如：`tvly-xxxxx-xxxxx-xxxxx`

- [ ] **Step 2: 添加 TAVILY_API_KEYS Secret**

操作步骤：
1. 在 Secrets 页面点击 "New repository secret"
2. Name 输入: `TAVILY_API_KEYS`
3. Value 输入: `tvly-your-key-here`
4. 点击 "Add secret"

预期结果：
- Secret 添加成功
- API Key 加密存储

- [ ] **Step 3: 验证配置**

操作步骤：
1. 检查 Secrets 页面，确认 `TAVILY_API_KEYS` 已添加
2. 等待下次 workflow 运行，检查日志中是否使用 Tavily 进行新闻搜索

预期日志：
```
[INFO] Using Tavily API for news search
[INFO] Search results retrieved successfully
```

---

### Task 9: 监控和故障排查

**文件:**
- 无（操作类）

**步骤:**

- [ ] **Step 1: 查看历史运行记录**

操作步骤：
1. 进入仓库 "Actions" 标签
2. 点击 "daily_stock_analysis" workflow
3. 查看运行历史列表

预期结果：
- 可以看到所有运行记录
- 显示运行时间、状态（成功/失败/跳过）

- [ ] **Step 2: 排查失败的 workflow**

操作步骤：
1. 点击失败的 workflow 运行
2. 查看失败步骤的日志
3. 根据错误信息进行修复

常见错误及解决方案：

**错误 1: Secret 未配置**
```
Error: STOCK_LIST is not set
```
解决方案：
1. 进入 Settings → Secrets
2. 添加缺失的 SECRET

**错误 2: AI API 调用失败**
```
Error: OpenAI API call failed
```
解决方案：
1. 验证 API Key 是否有效
2. 检查 API 配额是否充足
3. 验证 OPENAI_BASE_URL 是否正确

**错误 3: Webhook 推送失败**
```
Error: Failed to send to WeChat
```
解决方案：
1. 验证 Webhook URL 是否正确
2. 确认机器人添加到正确的群
3. 检查网络连接

**错误 4: 股票代码无效**
```
Error: Stock code 999999 not found
```
解决方案：
1. 验证股票代码格式是否正确
2. 确认股票代码支持的市场代码

- [ ] **Step 3: 配置告警（可选）**

操作步骤：
1. 在仓库 Settings → Notifications 中配置
2. 选择在 workflow 失败时发送通知到您的邮箱或手机

---

## 验证清单

### 部署完成验证

- [ ] ✅ 仓库已 Fork 到个人 GitHub 账号
- [ ] ✅ `STOCK_LIST` Secret 已配置
- [ ] ✅ AI API Key Secret 已配置（至少一个）
- [ ] ✅ 企业微信 Webhook URL Secret 已配置
- [ ] ✅ Actions Workflow 已启用
- [ ] ✅ 手动触发 workflow 执行成功
- [ ] ✅ 企业微信群收到推送消息
- [ ] ✅ 推送消息内容正确（包含股票分析结果）

### 运行验证

- [ ] ✅ 定时任务正常执行（通过查看历史记录）
- [ ] ✅ 工作日自动执行
- [ ] ✅ 非交易日自动跳过
- [ ] ✅ 消息推送成功

---

## 常用命令参考

### 查看仓库信息
```bash
gh repo view YOUR_USERNAME/daily_stock_analysis
```

### 查看最近的 workflow 运行
```bash
gh run list --repo YOUR_USERNAME/daily_stock_analysis --limit 10
```

### 查看某个 workflow 运行的详情
```bash
gh run view YOUR_RUN_ID --repo YOUR_USERNAME/daily_stock_analysis
```

### 查看某个 workflow 运行的日志
```bash
gh run view YOUR_RUN_ID --repo YOUR_USERNAME/daily_stock_analysis --log-failed
```

### 手动触发 workflow
```bash
gh workflow run daily_analysis.yml --repo YOUR_USERNAME/daily_stock_analysis
```

---

## 扩展配置

### 添加更多通知渠道

配置以下 Secrets 可同时推送到多个渠道：

**飞书：**
- `FEISHU_WEBHOOK_URL` = `https://open.feishu.cn/open-apis/bot/v2/hook/xxxx`

**Telegram：**
- `TELEGRAM_BOT_TOKEN` = `123456789:ABCdefGHIjklMNOpqrsTUVwxyz`
- `TELEGRAM_CHAT_ID` = `123456789`

**Discord：**
- `DISCORD_WEBHOOK_URL` = `https://discord.com/api/webhooks/xxxx`

### 修改报告类型

添加 Secret：
- `REPORT_TYPE` = `full`（完整报告）或 `simple`（精简报告）

### 修改报告语言

添加 Secret：
- `REPORT_LANGUAGE` = `zh`（中文）或 `en`（英文）

---

## 参考资源

- [GitHub Actions 文档](https://docs.github.com/en/actions)
- [GitHub Secrets 文档](https://docs.github.com/en/actions/security-guides/encrypted-secrets)
- [企业微信机器人文档](https://developer.work.weixin.qq.com/document/path/91770)
- [完整配置指南](docs/full-guide.md)
- [LLM 配置指南](docs/LLM_CONFIG_GUIDE.md)
