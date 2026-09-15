# 游资交割单分析 Spec

> 来源：《新生代游资交割单》PDF —— 五位一线游资的实盘交割单图解与系统总结
> 用途：供后续模块开发、策略回测、AI 分析 Agent 使用的结构化知识规约

---

## 1. 领域模型

### 1.1 Speculator（游资画像）

```python
@dataclass
class Speculator:
    """游资基本信息与核心特征"""
    id: str                            # 唯一标识 (beijing-chaojia, chen-xiaoqun, etc.)
    name: str                          # 称号 (北京炒家, 陈小群, 92科比, 涅盘重升, 一瞬流光)
    generation: str                     # 代际 (85后/90后/95后)
    birth_year: int
    seat: str                          # 营业部/席位 (长城证券, 大连金马路, 中泰证券湖北分公司)
    start_year: int                    # 入市年份
    known_return: str                  # 知名收益 (如 "一年32倍", "100万→1亿")
    core_mode: SpeculatorMode          # 核心模式
    trade_methods: list[TradeMethod]   # 使用的手法 (打板/半路/低吸)
    risk_preference: RiskLevel         # 风控偏好
    philosophys: list[Philosophy]      # 核心理念
```

### 1.2 SpeculatorMode（核心模式枚举）

```python
class SpeculatorMode(Enum):
    FIRST_BOARD       = "打首板"          # 北京炒家
    DRAGON_LEADER     = "龙头战法"        # 陈小群
    CYCLE_PHASE       = "情绪周期+龙头补涨切换"  # 92科比
    EMOTION_SYSTEM    = "六大情绪体系"     # 涅盘重升
    HIGH_LEVEL_RELAY  = "高位接力"        # 一瞬流光
```

### 1.3 TradeMethod（交易手法）

```python
@dataclass
class TradeMethod:
    name: str                          # 手法名称
    timing: str                        # 时机 (竞价/半路/打板/尾盘/低吸)
    position_preference: PositionLevel  # 仓位偏好
    description: str                   # 适用场景说明

class TradeMethodType(Enum):
    AUCTION_BUY       = "竞价买入"       # 9:25 竞价直接上
    HALF_WAY          = "半路"          # 4%-7% 拉升中买入
    BOARD_SWEEP       = "扫板"          # 涨停瞬间扫入
    BOARD_QUEUE       = "排板"          # 涨停排队
    BOARD_RETAIL      = "回封板"         # 炸板后回封买入
    TAIL_BID          = "尾盘竞价"       # 14:57 竞价买入
    LOW_ABSORPTION    = "低吸"          # 低位/炸板后水下低吸
    COUNTER_STRIKE    = "反核"          # 核按钮后反手接
```

### 1.4 TradeRecord（交割单条目）

> 单笔交易记录，从交割单/分时图中提取

```python
@dataclass
class TradeRecord:
    """单笔交易记录"""
    speculator_id: str                 # 所属游资
    stock_code: str                    # 股票代码
    stock_name: str                    # 股票名称
    trade_date: date                   # 交易日期
    buy_time: time | None              # 买入时间点 (用于判断手法)
    sell_time: time | None             # 卖出时间点
    buy_price: float                   # 买入价格
    sell_price: float                  # 卖出价格
    volume: int                        # 股数
    direction: TradeDirection          # 买入/卖出
    method: TradeMethodType            # 使用的手法
    profit_pct: float                  # 盈亏百分比 (+5.2 / -3.1)
    hold_days: int                     # 持仓天数
    reasoning: str                     # 操作逻辑 (PDF原文或推断)
    self_review: str                   # 自评 (正确/错误/可改善)
    market_context: str                # 当时市场背景
```

### 1.5 MarketPhase（情绪周期阶段）

> 92科比四阶段模型，涅盘六大情绪体系的简化应用

```python
class MarketPhase(Enum):
    LOW_TRIAL       = "低位试错"     # 冰点/轮动/无主线
    UP_TREND        = "主升期"      # 龙头打出高度/普涨
    HIGH_SIDE       = "高位震荡"    # 龙头滞涨/板块分化
    DOWN_TREND      = "主跌期"      # 龙头人气股大跌
```

```python
@dataclass
class MarketPhaseSignals:
    """用于判断当前情绪周期的信号指标"""
    # 量化信号
   涨停_count: int                    # 今日涨停数
   跌停_count: int                    # 今日跌停数
   limit_up_ratio: float             # 涨停占比 (涨停数/全市场)
  炸板_rate: float                   # 炸板率
  最高连板: int                       # 最高连板数
  连板梯队_score: float              # 梯队完整度评分
  涨跌_ratio: float                  # 上涨/下跌比

    # 定性信号
  龙头_behavior: str                 # 龙头股状态 (加速/分歧/跌停)
  亏钱效应: bool                      # 是否出现明显亏钱效应
  新题材_active: bool                 # 是否有新题材酝酿
  情绪极值_triggered: bool           # 是否触发情绪极值
```

### 1.6 EmotionSystem（涅盘六大情绪体系）

```python
@dataclass
class EmotionSystem:
    """涅盘重升六大情绪体系 - 每个维度的当前评分"""
   投机_emotion: int                  # 投机情绪 (涨停数/连板高度/炸板率)
    market_emotion: int               # 市场情绪 (指数强度/涨跌比)
   板块_emotion: int                  # 板块情绪 (资金偏好/主升强度)
   整体市场_emotion: int              # 整体市场情绪 (综合赚钱效应)
   整体投机_emotion: int              # 整体投机情绪 (整体投机氛围)
   整体板块_emotion: int              # 整体板块情绪 (龙头持续打高度)
```

### 1.7 Philosophy（心法/理念）

```python
@dataclass
class Philosophy:
    """游资心法/理念 - 可转化为交易规则"""
    speculator_id: str                # 所属游资
    category: PhilosophyCategory      # 分类
    statement: str                    # 原话
    interpretation: str               # 白话解读
    rule_form: str                    # 可执行的规则形式
    when_violated: str                # 违反时的后果

class PhilosophyCategory(Enum):
    POSITION_MGMT     = "仓位管理"
    RISK_CONTROL      = "风控纪律"
    PSYCHOLOGY        = "心态修炼"
    SELECTION         = "选股逻辑"
    TIMING            = "买卖时机"
    SYSTEM            = "系统建设"
    MARKET_UNDERSTAND = "市场理解"
```

---

## 2. 五游资核心模式规约

### 2.1 北京炒家 —— 首板模式

```
模式标识: first_board_spec
核心特征:
  标的筛选:
    - 只做低位首板(非二板接力/非高位板/非龙头板)
    - 具备板块效应(同板块至少2个涨停)
    - 加分项: 低价股/国改/市场风格匹配
  买点规则:
    - 首板类型 → 对应买法:
      秒拉板 → 排板(不冲板), 需有板块效应
      回封板 → 炸板回封时买入(空头释放后更安全)
      换手板 → 5-8个点横盘震荡30分钟以上→扫板
      尾盘板 → 尽量不打(两点半后不打)
      中军板 → 行业龙头打板
  卖点规则:
    - 隔日交易, 次日必换股
    - 满仓不过夜格局
  仓位管理:
    - 进化路径: 满仓单干→双票满仓→四票分仓→八票超市流
    - 弱市: 猥琐发育, 小仓位确定性操作
  风控:
    - 最大回撤目标: <3%
    - 资金底线: 跌破→防守模式
  quantify:
    - board_type_detection: 识别秒拉/回封/换手/尾盘
    - board_success_rate: 按类型统计封板成功率
    - group_effect_strength: 板块内协同涨停数
```

### 2.2 陈小群 —— 龙头模式

```
模式标识: dragon_leader_spec
核心特征:
  标的筛选:
    - 只做主线, 只做人气总龙头
    - 要么做市场总龙, 要么打造市场总龙
    - 注重股票内在逻辑, 尊重市场
  买点规则:
    - 龙头首阴反包 → 分歧转一致的点介入
    - 看好就买: 低吸/半路/打板不拘泥
    - 跌时缩量 → 资金锁仓, 可持有
    - 双龙夺珠 → 一龙封死跌停, 捧另一龙上位
  卖点规则:
    - 高点精准卖出
    - 该弱不弱视为强(持有), 该强不强视为弱(卖出)
    - 大单卖出但封单增大 → 市场合力大, 要加速(持有)
  反核规则:
    - 龙头被核按钮 → 反手接回
    - 条件: 主线还在, 龙头内在逻辑未被破坏
  仓位管理:
    - 分仓控回撤
    - 波段操作, 从头吃到尾
```

### 2.3 92科比 —— 周期模式

```
模式标识: cycle_phase_spec
核心特征:
  三支柱:
    - 龙头: 做个股和板块主升段、加速段
    - 补涨: 最强赚钱方向, 低位找类似个股
    - 切换: 板块内部高低切 / 板块间切换 / 风格切换
  四阶段操作指南:
    低位试错:
      - 题材冰点、轮动、无主线
      - 操作: 打首板/低位补涨/切换新题材
    主升期:
      - 主线确认、龙头打出高度、普涨
      - 操作: 买龙头(任何位置进都对) / 补涨 / 潜伏
    高位震荡:
      - 龙头滞涨、板块分化
      - 操作: 轻仓应对 / 低位补涨 / 挖掘低位
    主跌期:
      - 龙头人气股大跌
      - 操作: 切换新题材 / 搏反弹(连续大跌两天尾盘买入)
  核心规则:
    - 妖股看成交量: 量太大走不出来
    - 接力核心看人气
    - 中位股最危险: 要么做高位要么做低位
    - 反包二板大资金最爱: 安全度高
    - 弱转强最好体现在开盘后被买上去(不是竞价高开)
    - 大妖股启动价格必须低
```

### 2.4 涅盘重升 —— 系统模式

```
模式标识: emotion_system_spec
核心特征:
  系统框架:
    - 树干(主要思想) + 树枝(小规律)
    - 新发现→融入系统→验证有效→进化
    - 验证无效→果断砍掉
  六大情绪体系:
    - 详见 EmotionSystem
  核心能力:
    - 预判: 明日不看好一字板也走, 看好尾盘竞价也上仓位
    - 手法融合: 打板+半路+低吸, 不拘泥
    - 系统性复盘: 见 review-template.md
  仓位:
    - 大部分1-2成仓操作一支
    - 三分之一就算重仓
    - 2个月里只有三四次单票超过半仓
  关键认知:
    - 炒作情绪占7成, 图形只占3成
    - 龙头走弱→后排不要碰
    - 确定性=打板+做核心
    - 最容易亏钱: 最有赚钱效应板块的对立面
    - 资金总是流向阻力最小的方向
  卖出能力:
    - 能等到盘中冲高再走(不竞价止损)
    - 判断标准: 看板块/龙头/题材情绪
```

### 2.5 一瞬流光 —— 高位接力模式

```
模式标识: high_level_relay_spec
核心特征:
  标的筛选:
    - 永远只看龙头, 少看杂毛弱转强
    - 喜欢新高, 厌恶下跌
  买点规则:
    - 人气龙头股分歧时进场
    - 涨势中分歧=买点: 越不舒服的买点越大肉
    - 好位置错过就上车(适量买套也正常)
    - 跟风可做的两种情况:
      1) 每日最主流题材
      2) 新题材首发先上车再补票
  卖点规则:
    - 锁仓到两个涨停板, 第三天退场
    - 买入分歧, 卖出一致
    - 截断亏损, 让利润奔跑
  仓位:
    - 手风不顺时尽量别持股
    - 满仓打的板需三点符合:
      1) 指数单边上涨
      2) 板块当日核心
      3) 个股人气容量核心
    - 试仓+空仓
  心法:
    - 杜绝临时起意, 只计划操作
    - 标定空仓日子, 不会空仓永远做不大
    - 先处理好手里的, 再开始下一笔
    - 核心是理解每个阶段的本质炒作
```

---

## 3. 分析维度

### 3.1 行业轮动分析

```python
@dataclass
class SectorRotation:
    """板块轮动分析结果"""
    date: date
    当前主线: str                      # 当日最强板块
    主线强度: float                    # 1-10 分
    龙头股: str                        # 板块内的龙头
    龙二: str                          # 板块内的龙二
    板块涨停数: int                     # 板块内涨停数
    板块梯队: str                      # 龙头X板/龙二X板/后排X板
    板块情绪: str                       # 主升/分歧/退潮
    跷跷板_effect: str                 # 与其他板块的跷跷板关系
```

### 3.2 涨停质量分析

```python
@dataclass
class LimitUpQuality:
    """涨停质量分析 - 涅盘情绪体系的应用"""
    date: date
    一字板_count: int                  # 一字涨停数
    换手板_count: int                  # 换手涨停数
    炸板_count: int                    # 炸板数
    炸板率: float                      # 炸板/涨停
    首次涨停_time_distribution: dict   # 涨停时间分布
    最高连板: int                      # 当前最高板
    连板梯队: dict[int, int]           # {板数: 家数}
    昨日涨停_溢价率: float              # 昨日涨停股今日平均收益
    昨日涨停_高开率: float             # 昨日涨停今日高开比例
    赚钱效应: str                       # 好/一般/差

    # 衍生指标
    情绪_score: int                    # 1-100 情绪综合分
    风险_warning: str                   # 预警信号 (如有)
```

### 3.3 龙头分析

```python
@dataclass
class LeaderAnalysis:
    """龙头股分析"""
    总龙头: StockLeader | None          # 市场总龙头
    板块龙头: list[StockLeader]         # 各板块龙一
    leaderboard: list[StockLeader]      # 连板排名

@dataclass
class StockLeader:
    stock: str                         # 股票名称/代码
    board_count: int                   # 连板数
    sector: str                        # 所属板块
    带动性: float                      # 1-10 分 (带动力)
    板块效应: bool                      # 是否有板块效应
    分歧_or_一致: str                  # 分歧/一致/加速
    成交量_异常: str                    # 缩量/放量/正常
    反包_signal: bool                  # 是否出现反包信号
```

### 3.4 炸板分析

```python
@dataclass
class BoardBreakAnalysis:
    """炸板分析 - 涅盘最核心的复盘内容"""
    stock: str
    board_time: time                   # 涨停时间
    break_time: time                   # 炸板时间
    break_reason: str                  # 板块不行/盘子太大/指数拖累/抛压太重
    is_fatal: bool                     # 是否属于致命炸板(过后不回封)
    avoid_signal: str                  # 下次如何避免

    @staticmethod
    def detect_break_pattern(records: list[TradeRecord]) -> list[str]:
        """提取炸板的共性pattern: 高位炸板/跟风炸板/指数拖累炸板"""
        pass
```

### 3.5 仓位诊断

```python
@dataclass
class PositionDiagnosis:
    """仓位健康度诊断 - 基于五位游资的仓位管理规则"""
    当前仓位_pct: float
    建议仓位_pct: float                # 根据当前市场阶段
    是否匹配市场: bool                  # 进攻/均衡/防守
    分散度_score: float                # 1-10 越分散越高
    风险_exposure: str                 # 集中持股风险提示
    知行合一_check: str                # 实际仓位与计划是否一致
    问题: list[str]                    # 仓位问题列表
```

---

## 4. 模块规约

### 4.1 游资风格匹配模块

```
功能: 分析用户的交易记录, 匹配最相似的游资风格

输入:
  - 用户交割单 (TradeRecord 列表)
  - 用户持仓周期偏好
  - 用户胜率/盈亏比

输出:
  - 风格匹配结果:
    与每个游资的相似度评分
    最匹配的游资
    建议学习的方向(如 "你的风格类似北京炒家, 建议从首板练起")
    差距分析(用户与目标游资的关键差异)

匹配维度:
  - 交易频率 (高频/中频/低频)
  - 持仓周期 (隔日/短线/波段)
  - 标的偏好 (首板/龙头/跟风)
  - 买卖点手法分布
  - 仓位管理风格
  - 风险偏好
  - 胜率和盈亏比特征
```

### 4.2 情绪周期实时识别模块

```
功能: 根据当日盘面数据, 自动判定市场处于哪个情绪周期阶段

输入:
  - 全市场涨停/跌停/炸板数据
  - 连板高度 + 梯队
  - 涨跌比
  - 成交额
  - 龙头股状态

输出:
  - 当前阶段: 低位试错/主升/高位震荡/主跌
  - 置信度: 高/中/低
  - 信号明细: 哪些指标指向该结论
  - 阶段变化: 与昨日相比是否切换
  - 对应操作建议:
    低位试错 → 打首板/轻仓/新题材
    主升期 → 上仓位/买龙头
    高位震荡 → 补涨/低位/减仓
    主跌期 → 空仓/防守/极值反弹

算法建议: 使用规则引擎 + 概率加权
  规则示例:
    IF 涨停数>80 AND 最高连板>5 AND 炸板率<20% → 主升期 (高置信度)
    IF 涨停数<30 AND 最高连板<3 AND 涨跌比<0.3 → 主跌期
    IF 昨日主升 AND 涨停数下降>30% AND 龙头分歧 → 高位震荡
```

### 4.3 交易复盘评分模块

```
功能: 对一笔已完成的交易进行复盘评分, 对照五位游资的规则

输入: TradeRecord

输出:
  - 各维度评分 (1-10):
    买点合理性     (对照手法规则)
    卖点合理性     (对照预判和止盈止损规则)
    仓位适配度     (对照仓位管理规则)
    知行合一程度   (是否按计划执行)
    风险控制评分   (是否设置了止损/是否越级操作)

  - 游资对照分析:
    北京炒家会怎么评价这笔交易
    陈小群会怎么评价
    ... (五个游资视角)
    综合改进建议

  - 知识关联:
    这笔交易触发了哪些Philosophy规则
    违反复盘心法清单
```

### 4.4 资金流向分析模块

> 涅盘"炒作情绪7成, 图形3成" + "资金流向阻力最小方向"

```
功能: 分析资金在不同板块间的流动, 识别市场合力方向

输入: 板块涨跌幅/资金净流入/涨停分布

输出:
  - 资金主攻方向 (主力板块)
  - 资金流出方向 (退潮板块)
  - 跷跷板效应检测 (如白马涨→题材跌)
  - 资金合力强度评分
```

---

## 5. 事件/触发条件

### 5.1 可量化的买入信号

| 信号 | 来源游资 | 触发条件 | 置信度 |
|------|---------|---------|--------|
| 首板板块效应 | 北京炒家 | 同板块≥2涨停 + 首板换手充分 | 高 |
| 龙头首阴反包 | 陈小群 | 龙头连板后首阴 + 逻辑未破坏 | 中 |
| 反核信号 | 陈小群 | 龙头核按钮 + 主线未死 | 中 |
| 弱转强 | 陈小群/92科比 | 开盘后被买上去(非竞价做高) | 高 |
| 分歧买点 | 一瞬流光 | 人气龙头分歧日 + 指数多头 | 中 |
| 尾盘冰点反弹 | 92科比 | 连续大跌2天 + 尾盘买入 | 中 |
| 炸板低吸 | 涅盘重升 | 炸板+判断是分歧不是出货 | 低(需经验) |

### 5.2 可量化的卖出信号

| 信号 | 来源游资 | 触发条件 | 置信度 |
|------|---------|---------|--------|
| 该强不强 | 陈小群 | 龙头该加速但走弱 | 高 |
| 一致性卖出 | 一瞬流光 | 龙头高位一致加速 | 中 |
| 后排走弱→卖出 | 涅盘重升 | 自己一字板但后排全挂 | 高 |
| 题材退潮卖出 | 92科比 | 已淘汰题材反弹 | 高 |
| 隔日交易 | 北京炒家 | 次日必换股(首板) | 高 |
| 第三日离场 | 一瞬流光 | 锁仓2涨停后第3天走 | 中 |

---

## 6. 核心算法规约

### 6.1 情绪周期判定算法

```python
def determine_market_phase(signals: MarketPhaseSignals) -> tuple[MarketPhase, float]:
    """
    基于规则引擎判定当前情绪周期阶段

    Returns:
        (phase, confidence)
        confidence: 0.0 - 1.0
    """
    # 规则优先级: 主跌 > 主升 > 高位震荡 > 低位试错
    rules = {
        MarketPhase.UP_TREND: [
            ("涨停数 > 80", 0.8),
            ("最高连板 >= 5", 0.6),
            ("炸板率 < 20%", 0.5),
            ("涨跌比 > 2.0", 0.5),
        ],
        MarketPhase.DOWN_TREND: [
            ("涨停数 < 30", 0.8),
            ("跌停数 > 涨停数", 0.9),
            ("最高连板 < 3", 0.6),
            ("涨跌比 < 0.3", 0.7),
        ],
        # ... 其他阶段规则
    }
    # 加权投票
    # 返回得分最高的阶段 + 置信度
```

### 6.2 涨停质量评分算法

```python
def score_limit_up_quality(data: LimitUpQuality) -> int:
    """
    0-100 分评分涨停质量
    涅盘体系中, 涨停质量 = 情绪的直接体现
    """
    score = 50  # 基准分
    # 加分项
    if data.炸板率 < 20%: score += 20
    if data.最高连板 >= 5: score += 15
    if data.连板梯队[3] >= 2: score += 10  # 中间梯队完整
    if data.昨日涨停_溢价率 > 3%: score += 10
    # 减分项
    if data.炸板率 > 40%: score -= 20
    if data.最高连板 < 3: score -= 15
    if data.一字板 / data.换手板 > 1.5: score -= 10  # 一字过多=买不到
    return clamp(score, 0, 100)
```

### 6.3 模式匹配算法

```python
def match_speculator_pattern(trades: list[TradeRecord]) -> dict[str, float]:
    """
    将用户交割单与五位游资的模式进行匹配
    返回各游资的相似度评分

    匹配维度:
    - 平均持仓天数分布 → 隔日/短线/波段
    - 标的涨停板数偏好 → 首板/2板/3板+/龙头
    - 手法分布 → 打板/半路/低吸比例
    - 仓位集中度 → 单票仓位标准差
    - 胜率 vs 盈亏比特征
    - 最大回撤特征
    - 买入时间分布
    - 卖出时间分布
    """
```

---

## 7. 数据源依赖

| 数据 | 用途 | 现有源 | 新源是否必要 |
|------|------|--------|------------|
| 涨停板(含炸板/回封) | 涨停质量/炸板分析 | akshare/eastmoney | 需确认炸板率可获取 |
| 连板梯队 | 情绪周期判定 | eastmoney | 已有 |
| 个股分时图 | 买卖点识别 | akshare | 可选(可视化用) |
| 龙虎榜数据 | 游资席位识别 | akshare/tushare | 新功能需 |
| 板块成分股 | 板块效应分析 | akshare | 已有 |
| 北向资金 | 市场情绪辅助 | akshare | 已有 |

---

## 8. 后续实现建议

### Phase 1 — 分析增强 (复用现有数据)
1. `src/core/speculator_profile.py` — 游资画像 + 模式定义 (本 spec 的 Section 1-2)
2. `src/core/market_phase.py` — 情绪周期判定 (Section 6.1)
3. `src/core/limit_up_quality.py` — 涨停质量评分 (Section 6.2)
4. 集成到现有大盘复盘报告 (market_strategy.py 的维度中)

### Phase 2 — 用户功能
5. `src/services/speculator_match_service.py` — 游资风格匹配 (Section 4.1)
6. `src/services/trade_review_service.py` — 交易复盘评分 (Section 4.3)
7. API 路由 + Web 前端页面

### Phase 3 — 高级
8. 游资操作信号实时预警 (Section 5)
9. AI Agent 复盘助手 — 用 LLM 解读用户交割单并给出五位游资视角的评价

---

## 9. 附录

### 9.1 参考文件

| 文件 | 内容 | 用途 |
|------|------|------|
| `docs/review-template.md` | 涅盘重升式每日复盘模板 | 用户手动复盘表单 |
| `docs/speculator-analysis-spec.md` | 本文件 | 模块开发规约 |
| `src/market_analyzer.py` | AI 大盘复盘报告生成 | 集成情绪周期/涨停质量 |
| `src/core/market_strategy.py` | 策略蓝图维度定义 | 扩展分析维度 |
| `src/core/market_review.py` | 大盘复盘主流程 | 扩展执行流程 |

### 9.2 术语表

| 术语 | 解释 |
|------|------|
| 首板 | 股票第一个涨停板 |
| 二板/三板 | 连续第2/3个涨停板 |
| 炸板 | 涨停后被打开 |
| 回封 | 炸板后重新封板 |
| 扫板 | 在涨停价大量扫货 |
| 排板 | 在涨停价排队 |
| 半路 | 在股票拉升但没有涨停时买入 |
| 低吸 | 在股票下跌/回调时买入 |
| 反核 | 核按钮(跌停)后买入 |
| 核按钮 | 开盘直接跌停 |
| 龙头 | 板块/市场中涨幅最大、带动性最强的股票 |
| 龙二 | 板块中仅次于龙头的股票 |
| 补涨 | 龙头打出空间后, 低位跟涨的股票 |
| 切换 | 不同板块/风格间的资金转移 |
| 情绪周期 | 市场投机情绪的四个阶段循环 |
| 跷跷板效应 | 不同板块此消彼长(如白马涨题材跌) |
| 知行合一 | 按照盘前计划执行, 不临时起意 |
