# B2-lite 免费新闻/公告源接入 设计文档

- 日期:2026-09-24
- 类型:feat(数据接入,零新配置)
- 状态:设计已获用户认可,待写实现计划
- 背景:capital_forensics 第三/四阶段依赖 `search_stock_news`,而搜索引擎链全灭(所有 API key 为空 + searx.space 被墙 + 代理未开,见 2026-09-24 排查)。本设计用 akshare 免费接口做保底,零 key 零代理国内直连。
- 上游:方法论 `docs/资金筹码取证方法论.md` 第 6 章(公告是法定信源)/第 10 章(数据映射)

## 1. 目标与范围

**目标**:任何网络环境下,agent 的新闻检索与公告核验不再全灭:
1. `search_stock_news` 引擎链失败时自动降级到东财免费个股新闻;
2. 新增独立工具 `get_stock_announcements` 拉取个股法定公告(一手信源,服务监管痕迹链 A/B/C)。

**范围外**:链 A/B/C 程序化匹配引擎、公告正文抓取、付费搜索 key 接入、消息面情绪量化。

## 2. 已验证的接口事实(2026-09-24 真机)

| 接口 | 签名 | 实测 | 输出列 |
|------|------|------|--------|
| `ak.stock_news_em` | `(symbol: str)` | 0.33s,10 行 | 关键词/新闻标题/新闻内容/发布时间/文章来源/新闻链接 |
| `ak.stock_individual_notice_report` | `(security: str, symbol: str = '全部', begin_date=None, end_date=None)` | 可用 | 代码/名称/公告标题/公告类型/公告日期/网址(公告日期为 date 对象) |

注意:`ak.stock_notice_report` 的 symbol 是**公告类别**非股票代码(传代码 KeyError),不可用;按股查公告用 `stock_individual_notice_report`。

## 3. 组件设计

### 3.1 `data_provider/free_news_adapter.py`(新,无状态,~100 行)

```python
class FreeNewsAdapter:
    """akshare 免费新闻/公告源(国内直连,无 key,_fail-open)。"""

    def get_stock_news(self, stock_code: str, max_items: int = 10) -> Dict[str, Any]:
        # 返回 {"status": "ok"|"failed", "items": [...], "errors": [...]}
        # item: {title, snippet(内容前200字), url, source, published_date}
        # akshare 调用 try/except 全吞,列用关键词定位(风格同 fundamental_adapter._find_col)

    def get_stock_announcements(self, stock_code: str, days: int = 90,
                                 keyword: Optional[str] = None) -> Dict[str, Any]:
        # 返回 {"status": "ok"|"failed", "items": [...], "errors": [...]}
        # item: {date(YYYY-MM-DD), notice_type, title, url}
        # begin_date/end_date 按 days 计算;keyword 对公告标题做大小写不敏感包含过滤
```

实现约定:模块内自带 `_find_col` 同形 helper(不跨模块 import fundamental_adapter 的私有函数);日期解析用 `_safe_datetime` 同形防御;fail-open(异常进 errors,不抛出)。

### 3.2 `search_stock_news` 降级(`src/agent/tools/search_tools.py` 修改)

降级触发条件(**仅原本的 error 路径**,成功路径零改动):
- `service.is_available == False`(当前环境即此状态),或
- `response.success == False`(引擎链失败)

降级动作:调 `FreeNewsAdapter.get_stock_news(stock_code)`:
- 成功 → 返回与搜索引擎**同构**的结果结构,附加 `"provider": "eastmoney_free"`、`"fallback": true`;
- 也失败 → 返回原 error(附免费源错误摘要)。

不改 `SearchService` 本身(不污染通用搜索语义,降级是 agent 工具层的策略)。

### 3.3 新工具 `get_stock_announcements`

- 注册:`src/agent/tools/registry.py`(仿 search_stock_news 的 ToolDefinition 形态)
- 参数:`stock_code`(必填)、`days`(默认 90)、`keyword`(可选)
- handler:调 `FreeNewsAdapter.get_stock_announcements`,返回结构化列表;A 股之外的市场返回 `{"error": "announcements only support A-shares"}`
- description 写明用途:法定公告一手信源(减持/质押/回购/问询/举牌核验),供监管痕迹验证

### 3.4 消费端配套

1. `strategies/capital_forensics.yaml` 第四步改写:
   - 开头加一句:"优先使用 `get_stock_announcements` 获取法定公告(一手信源),按链 A/B/C 匹配公告标题;`search_stock_news` 作为补充(新闻转述,注意区分一手/二手信源)。"
   - A 链的"大宗交易折价/新增质押"等仍可用新闻补充;输出格式不变。
2. `docs/资金筹码取证方法论.md` 第 10 章 ✅ 段追加两行(两接口名+免费/直连属性)。
3. `docs/资金筹码取证使用指南.md` FAQ 增补:搜索引擎不可用时新闻自动降级东财免费源;公告用 get_stock_announcements(一手信源)。
4. `docs/CHANGELOG.md` `[Unreleased]` 两条 flat 记录(新功能×1、文档×1)。

## 4. 错误处理

```
akshare 调用异常/超时 → adapter 内吞掉,返回 {"status":"failed", "errors":[...]}
  → 工具层:新闻降级也失败 → 结构化 error(含两级失败原因)
  → 公告工具失败 → {"success": false, "error": ...}
空数据(无新闻/窗口内无公告)→ status=ok + items=[],属正常路径
非 A 股 → 公告工具明确 unsupported;新闻降级对非 A 股同样返回 unsupported(stock_news_em 仅 A 股)
```

## 5. 测试与验收

- **单元(mock akshare)**,`tests/test_free_news_adapter.py` + 扩展 `tests/test_search_tools_*`:
  - 两接口列映射(中文列名 fixture);
  - 降级触发:`is_available=False` → handler 走免费源,输出 provider=eastmoney_free、fallback=true;引擎成功时**不触发**降级(mock 断言免费源未被调用);
  - 公告:days 窗口过滤(边界日期含/不含)、keyword 过滤、空数据、异常 fail-open;
  - 非 A 股 unsupported。
- **真机**:`600519` 上验证 ① 当前引擎不可用状态下 search_stock_news 返回东财新闻(带 fallback 标注)② get_stock_announcements 返回带类型的公告列表。
- **回归**:`pytest -m "not network"` 相关文件全绿;`ci_gate.sh deterministic`。

## 6. 关键决策记录

1. 形态=新闻降级 + 公告独立工具(用户选定);否决"只降级"(公告/新闻语义混杂)与"双独立工具"(搜索全灭时 LLM 不会自动换工具)。
2. 零新配置:降级仅在原 error 路径触发,公告工具显式调用——不配可运行。
3. 数据获取放 `data_provider/`(目录职责),tools 层只做包装。
4. 降级输出标注 `fallback: true` + provider,LLM 可据此调整置信度措辞。
5. 不做链 A/B/C 程序化预分类(YAGNI,公告类型字段+YAML 指引已够;结构化匹配留 B2)。
6. `stock_notice_report` 弃用(symbol 为类别非代码);按股公告用 `stock_individual_notice_report`。
