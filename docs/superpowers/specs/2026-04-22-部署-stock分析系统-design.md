# 部署股票分析系统设计方案

**日期**: 2026-04-22
**目标**: 通过 GitHub Actions 部署股票智能分析系统

---

## 1. 部署架构

### 1.1 整体架构
```
GitHub Actions → 克隆仓库 → 安装依赖 → 配置环境变量 → 执行分析 → 生成报告 → 推送到企业微信
```

### 1.2 部署方式
- **方式**: GitHub Actions 自动化工作流
- **触发时间**: 每工作日 18:00（北京时间）
- **成本**: 零成本，使用 GitHub 免费 Actions 配额
- **服务器**: 无需自建服务器，基于 GitHub 云端

---

## 2. 环境配置

### 2.1 必需 Secrets

| Secret 名称 | 说明 | 示例值 |
|-------------|------|--------|
| `STOCK_LIST` | 股票代码列表 | `600519,hk00700,AAPL` |
| `AI_API_KEY` | AI 模型 API Key（至少配置一个） | `sk-xxxxx` |
| `WECHAT_WEBHOOK_URL` | 企业微信 Webhook URL | `https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxxxx` |

### 2.2 推荐 Secrets

| Secret 名称 | 说明 | 示例值 |
|-------------|------|--------|
| `LLM_MODEL` | 指定主模型 | `deepseek-chat` 或 `gpt-4o` |
| `TAVILY_API_KEYS` | 新闻搜索 API Key | `tvly-xxxxx` |

### 2.3 可选配置

- `REPORT_TYPE`: 报告类型（`simple`/`full`/`brief`）
- `REPORT_LANGUAGE`: 报告语言（`zh`/`en`）
- `NEWS_MAX_AGE_DAYS`: 新闻时效（默认 3 天）

---

## 3. 股票列表配置

### 3.1 市场代码
- **A股**: `6xx`（上海）, `3xx`（深圳）
- **港股**: `hk` 前缀
- **美股**: `us` 前缀（如 `AAPL`, `TSLA`）

### 3.2 示例股票列表
```
600519,hk00700,AAPL,TSLA,0700.HK,BABA
```

### 3.3 数据源优先级
- **A股**: Efinance → AkShare → Tushare → Pytdx → Baostock
- **港股**: Longbridge → AkShare（未配置 Longbridge 时）
- **美股**: YFinance → Longbridge → AkShare（港股）

---

## 4. AI 模型配置

### 4.1 支持的模型
- Gemini（需科学上网）
- Claude（Anthropic）
- OpenAI 兼容（DeepSeek、通义千问等）
- AIHubMix（一 Key 多模型，国内可用）

### 4.2 配置示例

#### 方式一：使用 AIHubMix
```
AIHUBMIX_KEY=your_key_here
LLM_MODEL=openai/gemini-3.1-pro-preview
```

#### 方式二：使用 DeepSeek
```
OPENAI_API_KEY=sk-deepseek-key
OPENAI_BASE_URL=https://api.deepseek.com/v1
LLM_MODEL=openai/deepseek-chat
```

#### 方式三：使用 Claude
```
ANTHROPIC_API_KEY=sk-ant-xxx
ANTHROPIC_MODEL=claude-3-5-sonnet-20241022
LLM_MODEL=claude-3-5-sonnet-20241022
```

---

## 5. 企业微信 Webhook 配置

### 5.1 获取 Webhook
1. 企业微信 → 创建群聊或选择现有群
2. 群设置 → 群机器人 → 添加机器人
3. 复制 Webhook URL

### 5.2 Webhook URL 格式
```
https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=YOUR_KEY
```

### 5.3 注意事项
- 确保机器人添加到正确的群
- Webhook URL 对应的群会接收推送消息
- 建议添加到工作通知群

---

## 6. GitHub Actions 工作流配置

### 6.1 工作流文件
位置: `.github/workflows/daily_analysis.yml`

### 6.2 触发条件
- **定时触发**: 每工作日 18:00（北京时间）
- **手动触发**: 支持在 Actions 页面手动运行

### 6.3 执行步骤
```yaml
- Checkout code
- Setup Python
- Install dependencies
- Create .env file from secrets
- Run analysis
- Generate report
- Send to WeChat
```

---

## 7. 推送内容结构

### 7.1 决策仪表盘
```
🎯 2026-04-22 决策仪表盘
共分析3只股票 | 🟢买入:0 🟡观望:2 🔴卖出:1

📊 分析结果摘要
⚪ 股票名称(代码): 状态 | 评分 | 观点
⚪ ...
⚪ ...
```

### 7.2 股票详情
- 📰 重要信息速览
- 📊 业绩预期
- 🚨 风险警报
- ✨ 利好催化
- 📢 最新动态

### 7.3 大盘复盘（可选）
- 📊 主要指数
- 📈 市场概况
- 🔥 板块表现

---

## 8. 验证与测试

### 8.1 手动测试步骤
1. Fork 仓库到个人 GitHub 账号
2. 配置必需的 Secrets
3. 启用 Actions workflow
4. 手动触发 "每日股票分析" workflow
5. 检查 Actions 运行结果
6. 查看企业微信群接收到的推送消息

### 8.2 预期结果
- ✅ Actions workflow 成功执行
- ✅ 生成分析报告
- ✅ 企业微信收到推送消息
- ✅ 消息内容包含决策建议和详细信息

### 8.3 常见问题排查
- **Actions 失败**: 检查 Secrets 是否正确配置
- **未收到消息**: 确认 Webhook URL 和群设置
- **分析失败**: 检查股票代码是否正确，数据源权限
- **AI 调用失败**: 检查 API Key 是否有效

---

## 9. 维护与更新

### 9.1 更新股票列表
修改仓库中的 `.env` 文件或通过 GitHub Secrets 更新 `STOCK_LIST`

### 9.2 切换 AI 模型
修改 `LLM_MODEL` 或添加新的 API Key 到 Secrets

### 9.3 调整推送频率
修改 GitHub Actions workflow 中的 cron 时间表达式

### 9.4 查看运行日志
进入仓库 → Actions 标签 → 点击具体的 workflow 运行 → 查看日志

---

## 10. 安全性考虑

### 10.1 Secrets 保护
- GitHub Secrets 自动加密，不会泄露
- 每次运行时从 Secrets 读取，不会硬编码
- 可以通过 GitHub 界面随时修改或删除

### 10.2 权限管理
- Fork 后的仓库仅您有写入权限
- Actions 权限默认已启用
- 建议定期审查 Secrets 列表

---

## 11. 成本说明

### 11.1 GitHub Actions
- **免费额度**: 2000 分钟/月（团队版无限）
- 本项目分析时间通常 < 10 分钟/次
- 30 次分析后使用量约 300 分钟

### 11.2 AI API 成本
- 取决于使用的模型和调用频率
- DeepSeek: 约 ¥0.001/千tokens（极低成本）
- OpenAI GPT-4: 约 ¥0.03/千tokens
- 建议使用 DeepSeek 或类似性价比高的模型

### 11.3 数据源成本
- AkShare/Tushare: 大部分免费或低成本
- Longbridge: 按套餐付费（可选）
- 其他数据源: 大部分免费

---

## 12. 扩展功能

### 12.1 添加更多通知渠道
配置以下 Secrets 可同时推送到多个渠道：
- `FEISHU_WEBHOOK_URL`（飞书）
- `TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHAT_ID`（Telegram）
- `DISCORD_WEBHOOK_URL`（Discord）

### 12.2 启用 Web 界面
本地运行时添加 `--webui` 参数可启动 Web 管理界面

### 12.3 自定义报告模板
在 `templates/` 目录下创建自定义 Jinja2 模板

---

## 13. 参考文档

- [完整配置指南](docs/full-guide.md)
- [LLM 配置指南](docs/LLM_CONFIG_GUIDE.md)
- [GitHub Actions 文档](https://docs.github.com/en/actions)
- [企业微信机器人文档](https://developer.work.weixin.qq.com/document/path/91770)
