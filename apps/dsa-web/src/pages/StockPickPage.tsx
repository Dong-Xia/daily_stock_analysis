import type React from 'react';
import { useEffect, useMemo } from 'react';
import {
  BarChart3,
  Calculator,
  Info,
  Layers,
  RefreshCw,
  Search,
  Shield,
  Target,
} from 'lucide-react';
import HotSectorPicker from '../components/stockPick/HotSectorPicker';
import { useStockPickStore } from '../stores/stockPickStore';
import type { ParsedApiError } from '../api/error';
import { Badge, Card, EmptyState, SectionCard, Tooltip } from '../components/common';
import { cn } from '../utils/cn';
import type {
  CandidateItem,
  SectorDurabilityItem,
  SignalCard,
  SignalType,
  StopEvent,
} from '../types/stockPick';

// ============ Pipeline Step Definitions ============

const PIPELINE_STEPS = [
  { num: 1, label: '市场状态', icon: BarChart3 },
  { num: 2, label: '板块锁定', icon: Layers },
  { num: 3, label: '基本面扫描', icon: Search },
  { num: 4, label: '个股精选', icon: Target },
  { num: 5, label: '仓位计算', icon: Calculator },
  { num: 6, label: '止损评估', icon: Shield },
  { num: 7, label: '调仓信号', icon: RefreshCw },
] as const;

const DIMENSION_LABELS: Record<string, string> = {
  trend: '趋势',
  volume: '量能',
  breadth: '宽度',
  volatility: '波动率',
  sentiment: '情绪',
};

const CLASSIFICATION_COLORS: Record<string, string> = {
  '主线': 'bg-success/10 text-success border-success/20',
  '强势轮动': 'bg-cyan/10 text-cyan border-cyan/20',
  '轮动': 'bg-warning/10 text-warning border-warning/20',
  '脉冲': 'bg-muted/30 text-secondary-text border-border/40',
  '异动': 'bg-purple/10 text-purple border-purple/20',
  '退潮': 'bg-orange-500/10 text-orange-500 border-orange-500/20',
};

const SIGNAL_COLORS: Record<SignalType, string> = {
  BUY: 'bg-success/10 text-success border-success/20',
  ADD: 'bg-cyan/10 text-cyan border-cyan/20',
  HOLD: 'bg-warning/10 text-warning border-warning/20',
  REDUCE: 'bg-orange-500/10 text-orange-500 border-orange-500/20',
  EXIT: 'bg-danger/10 text-danger border-danger/20',
  ROTATE: 'bg-purple/10 text-purple border-purple/20',
};

const SIGNAL_LABELS: Record<SignalType, string> = {
  BUY: '买入',
  ADD: '加仓',
  HOLD: '持有',
  REDUCE: '减仓',
  EXIT: '清仓',
  ROTATE: '轮换',
};

// ============ Helper Components ============

const PipelineProgress: React.FC<{
  completedSteps: Set<number>;
}> = ({ completedSteps }) => {
  return (
    <div className="flex items-center justify-between gap-1 rounded-2xl border border-border/40 bg-card/50 p-2 sm:gap-2 sm:p-3">
      {PIPELINE_STEPS.map((step, index) => {
        const isCompleted = completedSteps.has(step.num);
        const isFirst = index === 0;
        const isLast = index === PIPELINE_STEPS.length - 1;
        return (
          <div key={step.num} className="flex flex-1 items-center gap-0 sm:gap-1">
            {!isFirst && (
              <div
                className={cn(
                  'hidden h-px flex-1 sm:block',
                  isCompleted ? 'bg-cyan/50' : 'bg-border/30',
                )}
              />
            )}
            <div className="flex flex-col items-center gap-1">
              <div
                className={cn(
                  'flex h-6 w-6 items-center justify-center rounded-full text-[11px] font-semibold transition-all duration-300 sm:h-7 sm:w-7 sm:text-xs',
                  isCompleted
                    ? 'bg-cyan text-white shadow-sm shadow-cyan/30'
                    : 'bg-muted/30 text-secondary-text border border-border/40',
                )}
              >
                {isCompleted ? (
                  <svg className="h-3 w-3 sm:h-3.5 sm:w-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
                    <polyline points="20 6 9 17 4 12" />
                  </svg>
                ) : (
                  step.num
                )}
              </div>
              <span className={cn(
                'hidden text-[10px] leading-tight sm:inline',
                isCompleted ? 'text-cyan font-medium' : 'text-secondary-text',
              )}>
                {step.label}
              </span>
            </div>
            {!isLast && (
              <div
                className={cn(
                  'h-px flex-1 sm:hidden',
                  isCompleted ? 'bg-cyan/50' : 'bg-border/30',
                )}
              />
            )}
          </div>
        );
      })}
    </div>
  );
};

const ClassificationBadge: React.FC<{
  classification: string;
}> = ({ classification }) => {
  const colorClass = CLASSIFICATION_COLORS[classification] || 'bg-muted/30 text-secondary-text border-border/40';
  return (
    <span className={cn('inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-medium', colorClass)}>
      {classification}
    </span>
  );
};

const SignalBadge: React.FC<{
  signal: SignalType;
}> = ({ signal }) => {
  const colorClass = SIGNAL_COLORS[signal] || SIGNAL_COLORS.HOLD;
  const label = SIGNAL_LABELS[signal] || signal;
  return (
    <span className={cn('inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold tracking-wide', colorClass)}>
      {label}
    </span>
  );
};

const LoadingSpinner: React.FC<{ text?: string }> = ({ text = '加载中...' }) => (
  <div className="flex min-h-[120px] flex-col items-center justify-center gap-3">
    <div className="h-7 w-7 animate-spin rounded-full border-2 border-cyan/20 border-t-cyan" />
    <p className="text-xs text-secondary-text">{text}</p>
  </div>
);

const GenericError: React.FC<{
  error: ParsedApiError;
  onRetry: () => void;
  isLoading?: boolean;
}> = ({ error, onRetry, isLoading }) => (
  <div className="rounded-xl border border-warning/20 bg-warning/5 p-4">
    <div className="flex items-start gap-3">
      <div className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-warning/10 text-warning">
        <RefreshCw className="h-4 w-4" />
      </div>
      <div className="min-w-0 flex-1">
        <p className="text-sm font-medium text-foreground">请求失败</p>
        <p className="mt-1 text-xs text-secondary-text">{error.message}</p>
        <button
          type="button"
          onClick={onRetry}
          disabled={isLoading}
          className="btn-primary mt-3 h-8 px-3 text-xs"
        >
          {isLoading ? '重试中...' : '重新加载'}
        </button>
      </div>
    </div>
  </div>
);

// ============ Main Page Component ============

const StockPickPage: React.FC = () => {
  useEffect(() => {
    document.title = '选股中心 - DSA';
  }, []);

  const {
    regimeLoading, regimeError, regimeData,
    lookbackDays, rotationLoading, rotationError, rotationData,
    fundQuarterDate, fundLoading, fundError, fundData,
    sectorName, screenLoading, screenError, screenData,
    posStockCode, posEntryPrice, posStopLoss, posAccountEquity, posRegimeFactor, posConfidence,
    posLoading, posError, posData,
    slStockCode, slEntryPrice, slCurrentPrice, slStopPrice,
    slLoading, slError, slData,
    rebalancePositions, rebalanceLoading, rebalanceError, rebalanceData,
    handleMarketRegime, setLookbackDays, handleRotation,
    setFundQuarterDate, handleFundamental,
    setSectorName, handleScreen,
    setPosStockCode, setPosEntryPrice, setPosStopLoss, setPosAccountEquity, setPosRegimeFactor, setPosConfidence,
    handlePositionSize,
    setSlStockCode, setSlEntryPrice, setSlCurrentPrice, setSlStopPrice,
    handleStopLoss,
    setRebalancePositions, handleRebalance,
  } = useStockPickStore();

  // Pipeline tracking
  const completedSteps = useMemo(() => {
    const steps = new Set<number>();
    if (regimeData) steps.add(1);
    if (rotationData) steps.add(2);
    if (fundData) steps.add(3);
    if (screenData) steps.add(4);
    if (posData) steps.add(5);
    if (slData) steps.add(6);
    if (rebalanceData) steps.add(7);
    return steps;
  }, [regimeData, rotationData, fundData, screenData, posData, slData, rebalanceData]);

  const inputClass = 'w-full rounded-xl border border-border/40 bg-surface px-3 py-2 text-sm text-foreground placeholder:text-secondary-text outline-none transition-colors focus:border-cyan/50';
  const numberInputClass = 'w-full rounded-xl border border-border/40 bg-surface px-3 py-2 text-sm text-foreground outline-none transition-colors focus:border-cyan/50 [appearance:textfield] [&::-webkit-outer-spin-button]:appearance-none [&::-webkit-inner-spin-button]:appearance-none';

  return (
    <div className="min-h-screen space-y-4 p-4 md:p-6">
      {/* Header */}
      <div className="flex items-center gap-2">
        <Target className="h-5 w-5 text-cyan" />
        <h1 className="text-xl font-semibold text-foreground">选股中心</h1>
      </div>

      {/* Hot Sector Chain (一键选股) */}
      <HotSectorPicker />

      {/* Pipeline Progress */}
      <PipelineProgress completedSteps={completedSteps} />

      {/* ===== Step 1: Market Regime ===== */}
      <SectionCard
        title={
          <span className="inline-flex items-center gap-1.5">
            步骤 1：市场状态
            <Tooltip
              contentClassName="max-w-[24rem]"
              content={
                <div className="space-y-2">
                  <p className="font-medium">市场状态筛选原理</p>
                  <p>基于上证/深证/创业板三大指数，从 5 个维度加权评分，将市场划分为 7 个阶段，并输出建议仓位。</p>
                  <div className="space-y-3">
                    <div>
                      <span className="font-medium">五个判断维度：</span>
                      <div className="text-xs space-y-1 pl-3 mt-1">
                        <p><span className="text-cyan font-medium">趋势 (35%)</span> — MA5/MA10/MA20/MA60 排列，多头→高分，空头→低分</p>
                        <p><span className="text-cyan font-medium">量能 (20%)</span> — 5日/20日均量比，放量&gt;1.2→高分，缩量&lt;0.8→低分</p>
                        <p><span className="text-cyan font-medium">宽度 (20%)</span> — 全市场涨跌家数比，普涨&gt;60%→高分，普跌&lt;40%→低分</p>
                        <p><span className="text-yellow-500 font-medium">波动率 (10%)</span> — 5日/20日ATR比，波动扩张→低分，收缩→高分</p>
                        <p><span className="text-yellow-500 font-medium">情绪 (15%)</span> — 近10日极端波动天数，越平静→高分，越极端→低分</p>
                      </div>
                    </div>
                    <div className="border-t border-border/20 pt-2">
                      <span className="font-medium">七种市场阶段：</span>
                      <div className="text-xs space-y-1 pl-3 mt-1.5">
                        <p><span className="text-success font-medium">主升趋势</span> ≥85分 — 进攻，仓位 85%-100%</p>
                        <p><span className="text-success font-medium">震荡上行</span> 70-84分 — 均衡偏进攻，仓位 60%-80%</p>
                        <p><span className="text-yellow-500 font-medium">横盘震荡</span> 40-69分 — 均衡，仓位 30%-50%</p>
                        <p><span className="text-orange-500 font-medium">震荡下行</span> 25-39分 — 防御，仓位 20%-40%</p>
                        <p><span className="text-danger font-medium">主跌趋势</span> {'<'}25分 — 空仓防守，仓位 0%-20%</p>
                        <p><span className="text-purple-500 font-medium">底部反转</span> 趋势见底信号 — 试探建仓，仓位 50%-70%</p>
                        <p><span className="text-orange-500 font-medium">情绪极端</span> 情绪&gt;90且波动&gt;85 — 减仓警惕，仓位 20%-60%</p>
                      </div>
                    </div>
                    <div className="border-t border-border/20 pt-2">
                      <p className="text-[11px] text-secondary-text leading-relaxed">
                        <strong>综合判定</strong>：5 维度加权平均得分 → 特殊案例（底部反转/情绪极端）优先判定 → 常规阈值映射 → 仓位区间线性插值。
                        数据来源：上证综指(000001)、深证成指(399001)、创业板指(399006)。
                      </p>
                    </div>
                  </div>
                </div>
              }
              side="bottom"
            >
              <span className="inline-flex h-5 w-5 cursor-help items-center justify-center rounded-full border border-border/60 text-xs font-bold text-cyan hover:border-cyan hover:bg-cyan/10 hover:text-cyan">
                <Info className="h-3.5 w-3.5" />
              </span>
            </Tooltip>
          </span>
        }
        subtitle="市场状态"
      >
        <div className="mb-4 flex items-end gap-3">
          <button
            type="button"
            onClick={() => void handleMarketRegime()}
            disabled={regimeLoading}
            className="btn-primary h-9 px-4 text-sm"
          >
            {regimeLoading ? (
              <span className="flex items-center gap-1.5">
                <RefreshCw className="h-3.5 w-3.5 animate-spin" />
                分析中
              </span>
            ) : (
              <span className="flex items-center gap-1.5">
                <BarChart3 className="h-3.5 w-3.5" />
                分析当前市场状态
              </span>
            )}
          </button>
        </div>

        {regimeError && (
          <GenericError error={regimeError} onRetry={() => void handleMarketRegime()} isLoading={regimeLoading} />
        )}
        {regimeLoading && !regimeData && <LoadingSpinner text="正在分析市场状态..." />}

        {regimeData && (
          <div className="space-y-4">
            <div className="rounded-xl border border-cyan/20 bg-cyan/[0.04] p-4">
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-4">
                <div>
                  <p className="text-xs uppercase tracking-wider text-secondary-text">市场阶段</p>
                  <p className="mt-1.5 text-lg font-semibold text-cyan">{regimeData.regimeLabel}</p>
                </div>
                <div>
                  <p className="text-xs uppercase tracking-wider text-secondary-text">置信度</p>
                  <p className="mt-1.5 text-lg font-semibold text-foreground">{regimeData.confidence}%</p>
                </div>
                <div>
                  <p className="text-xs uppercase tracking-wider text-secondary-text">建议仓位上限</p>
                  <p className="mt-1.5 text-lg font-semibold text-foreground">{(regimeData.positionFactor * 100).toFixed(0)}%</p>
                </div>
                <div>
                  <p className="text-xs uppercase tracking-wider text-secondary-text">操作建议</p>
                  <p className="mt-1.5 text-sm font-medium text-foreground">{regimeData.recommendation}</p>
                </div>
              </div>
            </div>

            {/* Evidence dimensions */}
            {regimeData.evidence.length > 0 && (
              <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-5">
                {regimeData.evidence.map((ev, i) => (
                  <div key={i} className="rounded-lg border border-border/40 bg-surface/30 p-3 text-center">
                    <p className="text-xs tracking-wider text-secondary-text">{DIMENSION_LABELS[ev.dimension] || ev.dimension}</p>
                    <p className="mt-1 text-lg font-semibold text-foreground">{ev.score.toFixed(0)}</p>
                    <p className="text-xs text-secondary-text">{ev.signal}</p>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {!regimeLoading && !regimeError && !regimeData && (
          <EmptyState title="分析市场状态" description="点击「分析当前市场状态」按钮，基于趋势/量能/宽度/波动率/情绪判断当前市场阶段。" />
        )}
      </SectionCard>

      {/* ===== Step 2: Sector Rotation ===== */}
      <SectionCard
        title={
          <span className="inline-flex items-center gap-1.5">
            步骤 2：板块锁定
            <Tooltip
              contentClassName="max-w-[24rem]"
              content={
                <div className="space-y-2">
                  <p className="font-medium">板块锁定原理</p>
                  <p>通过对板块排行榜进行多日持续性分析，识别主线板块，过滤一日游脉冲行情。</p>
                  <div className="space-y-3">
                    <div>
                      <span className="font-medium">四个判断维度：</span>
                      <div className="text-xs space-y-1 pl-3 mt-1">
                        <p><strong>持续天数</strong> — 板块连续在榜的交易日数。≥5 天可视为有效主线，≥3 天有潜力，&lt;3 天持续性不足</p>
                        <p><strong>前3次数</strong> — 回看期内进入排行榜前 3 的总天数。次数高说明板块反复活跃，非一日游行情</p>
                        <p><strong>评分趋势</strong> — 最近评分变化方向（线性回归斜率归一化到 ±10）。上升↗关注度提升，下降↘热度减退</p>
                        <p><strong>出现率</strong> — 板块在榜天数 ÷ 回看期总天数。出现率越高，持续性越强</p>
                      </div>
                    </div>
                    <div className="border-t border-border/20 pt-2">
                      <span className="font-medium">六种分类：</span>
                      <div className="text-xs space-y-1 pl-3 mt-1.5">
                        <p><span className="text-cyan font-medium">主线</span> — 持续≥5天 + 出现率≥60%，板块核心方向，重点参与</p>
                        <p><span className="text-cyan font-medium">强势轮动</span> — 持续≥3天 + 出现率≥40% 或趋势强劲，观察确认</p>
                        <p><span className="text-yellow-500 font-medium">轮动</span> — 出现率≥30%，反复活跃但未成主线，正常参与</p>
                        <p><span className="text-secondary-text font-medium">脉冲</span> — ≤2天隔日上榜，一日游行情，不追</p>
                        <p><span className="text-purple-500 font-medium">异动</span> — 突然上榜此前很少出现，可能为新主线启动，标记观察</p>
                        <p><span className="text-orange-500 font-medium">退潮</span> — 趋势持续向下，板块热度减退，回避</p>
                      </div>
                    </div>
                    <div className="border-t border-border/20 pt-2">
                      <p className="text-[11px] text-secondary-text leading-relaxed">
                        <strong>核心逻辑</strong>：A 股板块轮动周期通常在 3-5 周。默认回看 20 个交易日，持续 5 天在榜 = 25% 时间占比，有效过滤脉冲行情。真正的主线板块在持续天数、前3次数、评分趋势三个维度上都表现优异。
                      </p>
                    </div>
                  </div>
                </div>
              }
              side="bottom"
            >
              <span className="inline-flex h-5 w-5 cursor-help items-center justify-center rounded-full border border-border/60 text-xs font-bold text-cyan hover:border-cyan hover:bg-cyan/10 hover:text-cyan">
                <Info className="h-3.5 w-3.5" />
              </span>
            </Tooltip>
          </span>
        }
        subtitle="板块锁定"
      >
        <div className="mb-4 flex flex-wrap items-end gap-3">
          <div className="min-w-0 flex-1 sm:max-w-[200px]">
            <label className="mb-1.5 block text-xs font-medium text-secondary-text">
              回溯天数
              <Tooltip
                content={
                  <div className="space-y-1.5">
                    <p className="font-medium">回溯天数参考：</p>
                    <table className="w-full text-[11px]">
                      <thead>
                        <tr className="border-b border-border/30 text-secondary-text">
                          <th className="pr-2 text-left font-medium">天数</th>
                          <th className="pr-2 text-left font-medium">适合场景</th>
                          <th className="text-left font-medium">说明</th>
                        </tr>
                      </thead>
                      <tbody>
                        <tr className="border-b border-border/20">
                          <td className="pr-2 whitespace-nowrap text-cyan">5-10</td>
                          <td className="pr-2">短线轮动</td>
                          <td>灵敏但噪声大，容易把短期脉冲当成主线</td>
                        </tr>
                        <tr className="border-b border-border/20">
                          <td className="pr-2 whitespace-nowrap text-cyan"><strong>15-25</strong></td>
                          <td className="pr-2"><strong>通用（默认20）</strong></td>
                          <td>平衡响应速度和信号质量，持续5天=25%~33%，有效过滤一日游脉冲</td>
                        </tr>
                        <tr className="border-b border-border/20">
                          <td className="pr-2 whitespace-nowrap text-cyan">30-45</td>
                          <td className="pr-2">中线趋势</td>
                          <td>更稳定，只抓真正有持续性的主线板块，但确认时可能已涨一段</td>
                        </tr>
                        <tr>
                          <td className="pr-2 whitespace-nowrap text-cyan">50-60</td>
                          <td className="pr-2">长线产业</td>
                          <td>极稳定，但滞后明显，主线确认时可能已在高位，适合产业级潜伏策略</td>
                        </tr>
                      </tbody>
                    </table>
                    <p className="mt-2 border-t border-border/20 pt-1.5 text-[11px] leading-relaxed text-secondary-text">
                      <strong>建议值：20（默认）</strong><br />
                      原因：A 股板块轮动周期通常在 3-5 周，20 个交易日正好覆盖；连续 5 天 = 25% 时间在榜，能有效过滤一日游脉冲。取值范围 5~60 天，20 处于中间偏短，兼顾灵敏度和稳定性。<br />
                      如果想看<strong>短期热点轮动</strong>（追涨），设 10-15；<br />
                      如果想看<strong>产业级趋势</strong>（潜伏），设 30-40。
                    </p>
                  </div>
                }
                side="bottom"
              >
                <span className="ml-1 inline-flex h-5 w-5 cursor-help items-center justify-center rounded-full border border-border/60 text-xs font-bold text-cyan hover:border-cyan hover:bg-cyan/10 hover:text-cyan">
                  <Info className="h-3.5 w-3.5" />
                </span>
              </Tooltip>
            </label>
            <input
              type="number"
              min={5}
              max={120}
              value={lookbackDays === 0 ? '' : lookbackDays}
              onChange={(e) => {
                setLookbackDays(e.target.value === '' ? 0 : Number(e.target.value));
              }}
              onBlur={() => {
                if (!lookbackDays || lookbackDays < 5) setLookbackDays(5);
                if (lookbackDays > 120) setLookbackDays(120);
              }}
              className={numberInputClass}
            />
          </div>
          <button
            type="button"
            onClick={() => void handleRotation()}
            disabled={rotationLoading}
            className="btn-primary h-9 px-4 text-sm"
          >
            {rotationLoading ? (
              <span className="flex items-center gap-1.5">
                <RefreshCw className="h-3.5 w-3.5 animate-spin" />
                分析中
              </span>
            ) : (
              <span className="flex items-center gap-1.5">
                <Layers className="h-3.5 w-3.5" />
                分析板块轮动
              </span>
            )}
          </button>
        </div>

        {rotationError && (
          <GenericError error={rotationError} onRetry={() => void handleRotation()} isLoading={rotationLoading} />
        )}
        {rotationLoading && !rotationData && <LoadingSpinner text="正在分析板块轮动..." />}

        {rotationData && (
          <div className="space-y-4">
            <div className="rounded-xl border border-cyan/20 bg-cyan/[0.04] p-4">
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
                <div>
                  <p className="text-xs uppercase tracking-wider text-secondary-text">分析日期</p>
                  <p className="mt-1.5 text-lg font-semibold text-cyan">{rotationData.analysisDate}</p>
                </div>
                <div>
                  <p className="text-xs uppercase tracking-wider text-secondary-text">回看天数</p>
                  <p className="mt-1.5 text-lg font-semibold text-foreground">{rotationData.lookbackDays}天</p>
                </div>
                <div>
                  <p className="text-xs uppercase tracking-wider text-secondary-text">有效交易日</p>
                  <p className="mt-1.5 text-lg font-semibold text-foreground">{rotationData.totalRankingDays}天</p>
                </div>
              </div>
            </div>

            <div className="rounded-xl border border-border/40 bg-surface/50 p-4">
              <div className="mb-3 flex items-center gap-2">
                <Layers className="h-4 w-4 text-cyan" />
                <h3 className="text-sm font-semibold text-foreground">板块分类</h3>
              </div>
              {rotationData.sectors.length === 0 ? (
                <EmptyState title="暂无板块数据" description="当前未检测到板块持续性数据。" />
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-xs">
                    <thead className="border-b border-border/40 text-secondary-text">
                      <tr>
                        <th className="py-2 pr-3 text-left font-medium">板块名称</th>
                        <th className="py-2 pr-3 text-left font-medium">分类</th>
                        <th className="py-2 pr-3 text-right font-medium">持续天数</th>
                        <th className="py-2 pr-3 text-right font-medium">前3次数</th>
                        <th className="py-2 text-right font-medium">趋势</th>
                      </tr>
                    </thead>
                    <tbody>
                      {rotationData.sectors.map((item, idx) => (
                        <SectorDurabilityRow key={`${item.name}-${idx}`} item={item} />
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </div>
        )}

        {!rotationLoading && !rotationError && !rotationData && (
          <EmptyState title="分析板块轮动" description="设置回溯天数后点击「分析板块轮动」按钮，识别主线/轮动/脉冲板块。" />
        )}
      </SectionCard>

      {/* ===== Step 3: Fundamental Screener ===== */}
      <SectionCard
        title={
          <span className="inline-flex items-center gap-1.5">
            步骤 3：基本面扫描
            <Tooltip
              contentClassName="max-w-[24rem]"
              content={
                <div className="space-y-2">
                  <p className="font-medium">基本面扫描原理</p>
                  <p>业绩是股票增长的核心驱动力。基于 AkShare 财报数据，全市场 A 股一次性扫描，精选业绩高增长标的。</p>
                  <div className="space-y-3">
                    <div>
                      <span className="font-medium">五项筛选条件：</span>
                      <div className="text-xs space-y-1.5 pl-3 mt-1">
                        <p><strong>① 扣非利润高增长</strong> — 当季扣非净利润同比增长 <span className="text-cyan">≥50%</span>，确保盈利质量真实提升</p>
                        <p><strong>② 营收同步增长</strong> — 同期营业总收入同比增长 <span className="text-cyan">≥20%</span>，营收是利润的基础，防止单纯靠变卖资产美化利润</p>
                        <p><strong>③ 利润规模达标</strong> — 扣非净利润绝对值 <span className="text-cyan">≥5000 万</span>，剔除微利公司，避免低基数带来的增速失真</p>
                        <p><strong>④ 市场验证</strong> — 财报公告当日股价大涨或涨停，说明市场资金高度认可这份业绩</p>
                        <p><strong>⑤ 行业景气度</strong> — 公司所处行业高景气、有增长潜力，结合板块轮动评分确认赛道方向</p>
                      </div>
                    </div>
                    <div className="border-t border-border/20 pt-2">
                      <span className="font-medium">评分公式（满分 10 分）：</span>
                      <div className="text-xs space-y-1.5 pl-3 mt-1.5">
                        <p><span className="text-cyan font-medium">营收增速（3分）</span> — ≥20%→1分，≥30%→2分，≥50%→3分</p>
                        <p><span className="text-cyan font-medium">利润增速（5分）</span> — ≥50%→1分，≥70%→3分，≥100%→5分。利润权重最大，体现盈利爆发力</p>
                        <p><span className="text-cyan font-medium">利润规模（2分）</span> — ≥0.5亿→1分，≥5亿→2分。规模越大抗风险能力越强</p>
                      </div>
                    </div>
                    <div className="border-t border-border/20 pt-2">
                      <p className="text-[11px] text-secondary-text leading-relaxed">
                        <strong>核心理念</strong>：业绩是股价上涨最坚实的支撑。好业绩 + 市场认可 + 好赛道，三者共振才是真正的优质标的。
                      </p>
                    </div>
                  </div>
                </div>
              }
              side="bottom"
            >
              <span className="inline-flex h-5 w-5 cursor-help items-center justify-center rounded-full border border-border/60 text-xs font-bold text-cyan hover:border-cyan hover:bg-cyan/10 hover:text-cyan">
                <Info className="h-3.5 w-3.5" />
              </span>
            </Tooltip>
          </span>
        }
        subtitle="基本面扫描"
      >
        <div className="mb-4 flex flex-wrap items-end gap-3">
          <div className="min-w-0 flex-1 sm:max-w-[200px]">
            <label className="mb-1.5 block text-xs font-medium text-secondary-text">财报季度</label>
            <input
              type="text"
              value={fundQuarterDate}
              onChange={(e) => setFundQuarterDate(e.target.value)}
              placeholder="20260331 (空=最新)"
              className={inputClass}
            />
          </div>
          <button
            type="button"
            onClick={() => void handleFundamental()}
            disabled={fundLoading}
            className="btn-primary h-9 px-4 text-sm"
          >
            {fundLoading ? '筛选中...' : '扫描全市场'}
          </button>
        </div>

        {fundError && <GenericError error={fundError} onRetry={() => void handleFundamental()} isLoading={fundLoading} />}
        {fundLoading && !fundData && <LoadingSpinner text="正在获取财报数据..." />}

        {fundData && (
          <div className="space-y-3">
            <div className="grid grid-cols-4 gap-3">
              <FunnelCard label="总股票数" value={fundData.totalStocks} color="text-foreground" />
              <FunnelCard label="营收同比≥20%" value={fundData.afterRevenueTest} color="text-cyan" />
              <FunnelCard label="利润同比≥50%" value={fundData.afterProfitTest} color="text-warning" />
              <FunnelCard label="全部通过" value={fundData.candidates.length} color="text-success" />
            </div>
            {fundData.candidates.length > 0 ? (
              <div className="overflow-x-auto">
                <table className="w-full text-xs">
                  <thead><tr className="border-b border-border/40 text-secondary-text">
                    <th className="py-2 pr-2 text-left font-medium">代码</th>
                    <th className="py-2 pr-2 text-left font-medium">名称</th>
                    <th className="py-2 pr-2 text-right font-medium">营收同比</th>
                    <th className="py-2 pr-2 text-right font-medium">利润同比</th>
                    <th className="py-2 pr-2 text-right font-medium">净利润</th>
                    <th className="py-2 text-right font-medium">评分</th>
                  </tr></thead>
                  <tbody>
                    {fundData.candidates.map((c) => (
                      <tr key={c.code} className="border-b border-border/20 hover:bg-surface/50">
                        <td className="py-2 pr-2 text-foreground">{c.code}</td>
                        <td className="py-2 pr-2 text-foreground">{c.name}</td>
                        <td className="py-2 pr-2 text-right text-success">{c.revenueYoy > 0 ? '+' : ''}{c.revenueYoy.toFixed(1)}%</td>
                        <td className="py-2 pr-2 text-right text-success">{c.profitYoy > 0 ? '+' : ''}{c.profitYoy.toFixed(1)}%</td>
                        <td className="py-2 pr-2 text-right text-foreground">{(c.netProfit / 1e8).toFixed(2)}亿</td>
                        <td className="py-2 text-right font-medium text-cyan">{c.compositeScore.toFixed(1)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="space-y-2">
                {fundData.criteria && (
                  <div className="rounded-lg border border-border/40 bg-surface/30 p-3">
                    <p className="text-xs leading-relaxed text-secondary-text">{fundData.criteria}</p>
                  </div>
                )}
                <EmptyState title="无匹配股票" description="当前季度无股票满足全部筛选条件，可尝试其他财报季度。" />
              </div>
            )}
          </div>
        )}

      </SectionCard>

      {/* ===== Step 4: Stock Screening ===== */}
      <SectionCard
        title={
          <span className="inline-flex items-center gap-1.5">
            步骤 4：个股精选
            <Tooltip
              contentClassName="max-w-[26rem]"
              content={
                <div className="space-y-2">
                  <p className="font-medium">个股精选筛选原理</p>
                  <p>基于多级漏斗从板块成分股中筛选优质标的，过滤掉流动性差、趋势弱、排名靠后的个股。</p>
                  <div className="space-y-3">
                    <div>
                      <span className="font-medium">四级漏斗：</span>
                      <div className="text-xs space-y-1 pl-3 mt-1">
                        <p><strong>L1 候选池</strong> — 获取板块全部成分股，按涨跌幅绝对值排序取前 30 只进入下一层</p>
                        <p><strong>L2 趋势过滤</strong> — 计算 MA5/MA10/MA20，仅保留多头排列（MA5&gt;MA10&gt;MA20）的个股</p>
                        <p><strong>L3 板块排名</strong> — 计算近 20 日涨幅，板块内排名前 30% 的个股晋级</p>
                        <p><strong>L4 综合评分</strong> — 6 因子加权评分，取前 10 名作为最终精选结果</p>
                      </div>
                    </div>
                    <div className="border-t border-border/20 pt-2">
                      <span className="font-medium">六项评分因子：</span>
                      <div className="text-xs space-y-2.5 pl-3 mt-1.5">
                        <p>
                          <span className="text-cyan font-medium">趋势强度（25%）</span> — 判断股票当前是否处于健康的上升趋势。核心看 MA5、MA10、MA20 的排列方式——多头排列（MA5&gt;MA10&gt;MA20）得分高；均线走平或空头排列得分低。权重最大，回答最基本的问题：<strong>这股现在趋势好吗？</strong>
                        </p>
                        <p>
                          <span className="text-cyan font-medium">相对强度 RS（25%）</span> — 个股涨幅与所属板块平均涨幅的比值。RS 比值 = 2.0（个股涨幅是板块的 2 倍）得满分 100，RS 比值 = 0.5 得 30 分。它回答：<strong>这股在板块里跑赢了多少？</strong>强势股 RS 持续大于 1，弱势股持续小于 1。与趋势强度并列最高权重，先选对板块方向，再选对领涨股。
                        </p>
                        <p>
                          <span className="text-yellow-500 font-medium">量能确认（15%）</span> — 近期成交量与长期平均成交量的比值（5 日均量 / 20 日均量）。量比值大于 1.3 得分 70+（放量上涨可信度高），量比值小于 0.7 得分低于 30（缩量上涨可能是诱多）。<strong>用真金白银验证趋势的真伪。</strong>辅助确认信号，不是主信号。
                        </p>
                        <p>
                          <span className="text-secondary-text font-medium">乖离率（10%）</span> — 现价偏离 MA5 的百分比。控制在 MA5 附近 3% 以内得分最高（80+），超过 5% 开始减分，超过 8% 直接低分（&lt;40）。核心纪律：<strong>不追高。</strong>涨太急偏离均线太远，大概率会回踩。低权重反映粗略风控，精细化风控留到后续步骤。
                        </p>
                        <p>
                          <span className="text-secondary-text font-medium">涨停距离（10%）</span> — 距最近一个涨停板的价格距离。小于 5% 追涨风险高（低分），大于 20% 安全但可能已滞涨。过滤刚涨停后次日追进去的短期风险。
                        </p>
                        <p>
                          <span className="text-secondary-text font-medium">龙头评分（15%）</span> — 该股在所属板块内的涨幅排名。板块涨幅前 3 → 80 分，前 10 → 65 分，前 20 → 50 分，其余 → 40 分。<strong>买就买板块里的领头羊，不碰跟风杂毛股。</strong>
                        </p>
                      </div>
                    </div>
                    <div className="border-t border-border/20 pt-2">
                      <p className="text-[11px] text-secondary-text leading-relaxed">
                        <strong>核心逻辑</strong>：先确保趋势向上（L2），再确认板块内相对强势（L3），最后多因子评分精选（L4）。
                        趋势强度和相对强度合计占 50% 权重，确保选出的个股既有趋势支撑又有板块内领涨地位。
                      </p>
                    </div>
                  </div>
                </div>
              }
              side="bottom"
            >
              <span className="inline-flex h-5 w-5 cursor-help items-center justify-center rounded-full border border-border/60 text-xs font-bold text-cyan hover:border-cyan hover:bg-cyan/10 hover:text-cyan">
                <Info className="h-3.5 w-3.5" />
              </span>
            </Tooltip>
          </span>
        }
        subtitle="个股精选"
      >
        <div className="mb-4 flex flex-wrap items-end gap-3">
          <div className="min-w-0 flex-1 sm:max-w-[280px]">
            <label className="mb-1.5 block text-xs font-medium text-secondary-text">
              板块名称
            </label>
            <input
              type="text"
              value={sectorName}
              onChange={(e) => setSectorName(e.target.value)}
              placeholder="如：白酒、半导体、新能源"
              className={inputClass}
            />
          </div>
          <button
            type="button"
            onClick={() => void handleScreen()}
            disabled={screenLoading || !sectorName.trim()}
            className="btn-primary h-9 px-4 text-sm"
          >
            {screenLoading ? (
              <span className="flex items-center gap-1.5">
                <RefreshCw className="h-3.5 w-3.5 animate-spin" />
                筛选中
              </span>
            ) : (
              <span className="flex items-center gap-1.5">
                <Search className="h-3.5 w-3.5" />
                精选个股
              </span>
            )}
          </button>
        </div>

        {screenError && (
          <GenericError error={screenError} onRetry={() => void handleScreen()} isLoading={screenLoading} />
        )}

        {screenLoading && !screenData && <LoadingSpinner text="正在筛选个股..." />}

        {screenData && (
          <div className="space-y-4">
            <div className="grid grid-cols-4 gap-2 sm:gap-4">
              <FunnelCard label="总候选" value={screenData.totalConsidered} color="text-foreground" />
              <FunnelCard label="L1 过滤" value={screenData.afterLiquidity} color="text-cyan" />
              <FunnelCard label="L2 过滤" value={screenData.afterTrend} color="text-warning" />
              <FunnelCard label="L3 精选" value={screenData.afterRanking} color="text-success" />
            </div>

            {screenData.candidates.length === 0 ? (
              <EmptyState title="未筛选到个股" description="当前板块未筛选出符合条件的个股。" />
            ) : (
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
                {screenData.candidates.map((candidate) => (
                  <CandidateCard key={candidate.code} candidate={candidate} />
                ))}
              </div>
            )}
          </div>
        )}

        {!screenLoading && !screenError && !screenData && (
          <EmptyState title="精选个股" description="输入板块名称后点击「精选个股」，系统将使用多级漏斗筛选优质标的。" />
        )}
      </SectionCard>

      {/* ===== Step 5: Position Sizing ===== */}
      <SectionCard
        title={
          <span className="inline-flex items-center gap-1.5">
            步骤 5：仓位计算
            <Tooltip
              contentClassName="max-w-[24rem]"
              content={
                <div className="space-y-2">
                  <p className="font-medium">仓位计算原理</p>
                  <p>基于凯利公式 + 风控约束 + 市场状态的三层决策体系，输出建议股数和仓位比例。</p>
                  <div className="space-y-3">
                    <div>
                      <span className="font-medium">第一层：基础约束</span>
                      <div className="text-xs space-y-1 pl-3 mt-1">
                        <p><strong>均分仓位</strong> — 总资产 ÷ 最大持仓数（默认 5 只），得到单只股票基础分配额度</p>
                        <p><strong>市场状态缩放</strong> — 市场状态因子（步骡 1 输出，0~1）乘以单只上限（默认 25%），进攻市场放仓位，防御市场缩仓位</p>
                        <p><strong>单笔风控</strong> — 单笔最大亏损不超过总资产 2%。每股风险 = |入场价 − 止损价|，用 2% 额度反推最大可买股数</p>
                        <p><strong>板块集中度</strong> — 同一板块总仓位上限 40%，板块内股票均分后单只不可超限</p>
                      </div>
                    </div>
                    <div className="border-t border-border/20 pt-2">
                      <span className="font-medium">第二层：凯利公式</span>
                      <div className="text-xs space-y-1 pl-3 mt-1.5">
                        <p>凯利公式计算最优仓位比例：</p>
                        <p className="pl-2"><strong>f* = (p × R − q) / R</strong></p>
                        <p>其中 <strong>p</strong> = 信号置信度（胜率），<strong>q</strong> = 1 − p（失败率），<strong>R</strong> = 目标盈亏比（默认 2.0）</p>
                        <p className="mt-1">凯利系数上限截断在 25%，防止过度集中。实际使用<strong>半凯利（×0.5）</strong>进一步保守化，降低波动风险。</p>
                      </div>
                    </div>
                    <div className="border-t border-border/20 pt-2">
                      <span className="font-medium">第三层：综合决策</span>
                      <div className="text-xs space-y-1 pl-3 mt-1.5">
                        <p><span className="text-danger font-medium">高置信（≥70%）+ 进攻市场（因子≥0.7）</span> → 使用全凯利结果，进攻性配置</p>
                        <p><span className="text-yellow-500 font-medium">中置信（≥60%）</span> → 使用半凯利（×0.5），攻守平衡</p>
                        <p><span className="text-secondary-text font-medium">低置信（&lt;60%）</span> → 放弃凯利，只用纯风控结果的一半，保守入场</p>
                      </div>
                    </div>
                    <div className="border-t border-border/20 pt-2">
                      <p className="text-[11px] text-secondary-text leading-relaxed">
                        <strong>最终输出</strong>：推荐股数和仓位比例还会经过市场阶段上限的裁剪，确保不超过当前市场状态允许的最大仓位。
                        如果最终仓位过低（&lt;1%），系统会提示可能不适合入场。最大亏损金额 = 推荐股数 × 每股风险，入场前应确认能承受此亏损。
                      </p>
                    </div>
                  </div>
                </div>
              }
              side="bottom"
            >
              <span className="inline-flex h-5 w-5 cursor-help items-center justify-center rounded-full border border-border/60 text-xs font-bold text-cyan hover:border-cyan hover:bg-cyan/10 hover:text-cyan">
                <Info className="h-3.5 w-3.5" />
              </span>
            </Tooltip>
          </span>
        }
        subtitle="仓位计算"
      >
        <div className="mb-4 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          <div>
            <label className="mb-1.5 block text-xs font-medium text-secondary-text">股票代码</label>
            <input
              type="text"
              value={posStockCode}
              onChange={(e) => setPosStockCode(e.target.value)}
              placeholder="600519"
              className={inputClass}
            />
          </div>
          <div>
            <label className="mb-1.5 block text-xs font-medium text-secondary-text">入场价格</label>
            <input
              type="number"
              step="0.01"
              value={posEntryPrice}
              onChange={(e) => setPosEntryPrice(e.target.value)}
              placeholder="180.50"
              className={numberInputClass}
            />
          </div>
          <div>
            <label className="mb-1.5 block text-xs font-medium text-secondary-text">止损价格</label>
            <input
              type="number"
              step="0.01"
              value={posStopLoss}
              onChange={(e) => setPosStopLoss(e.target.value)}
              placeholder="170.00"
              className={numberInputClass}
            />
          </div>
          <div>
            <label className="mb-1.5 block text-xs font-medium text-secondary-text">账户总资产</label>
            <input
              type="number"
              step="1000"
              value={posAccountEquity}
              onChange={(e) => setPosAccountEquity(e.target.value)}
              placeholder="100000"
              className={numberInputClass}
            />
          </div>
          <div>
            <label className="mb-1.5 block text-xs font-medium text-secondary-text">市场状态因子</label>
            <input
              type="number"
              step="0.1"
              min="0"
              max="1"
              value={posRegimeFactor}
              onChange={(e) => setPosRegimeFactor(e.target.value)}
              placeholder="1.0"
              className={numberInputClass}
            />
          </div>
          <div>
            <label className="mb-1.5 block text-xs font-medium text-secondary-text">信号置信度</label>
            <input
              type="number"
              step="0.05"
              min="0"
              max="1"
              value={posConfidence}
              onChange={(e) => setPosConfidence(e.target.value)}
              placeholder="0.5"
              className={numberInputClass}
            />
          </div>
        </div>
        <button
          type="button"
          onClick={() => void handlePositionSize()}
          disabled={posLoading || !posStockCode.trim() || !posEntryPrice || !posStopLoss || !posAccountEquity}
          className="btn-primary h-9 px-4 text-sm"
        >
          {posLoading ? (
            <span className="flex items-center gap-1.5">
              <RefreshCw className="h-3.5 w-3.5 animate-spin" />
              计算中
            </span>
          ) : (
            <span className="flex items-center gap-1.5">
              <Calculator className="h-3.5 w-3.5" />
              计算仓位
            </span>
          )}
        </button>

        {posError && (
          <GenericError
            error={posError}
            onRetry={() => void handlePositionSize()}
            isLoading={posLoading}
          />
        )}

        {posLoading && !posData && <LoadingSpinner text="正在计算仓位..." />}

        {posData && (
          <div className="mt-4 rounded-xl border border-cyan/20 bg-cyan/[0.04] p-4">
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
              <div>
                <p className="text-xs uppercase tracking-wider text-secondary-text">建议股数</p>
                <p className="mt-1 text-lg font-semibold text-foreground">
                  {posData.recommendedShares.toLocaleString()}
                </p>
              </div>
              <div>
                <p className="text-xs uppercase tracking-wider text-secondary-text">仓位比例</p>
                <p className="mt-1 text-lg font-semibold text-cyan">
                  {(posData.recommendedPct * 100).toFixed(1)}%
                </p>
              </div>
              <div>
                <p className="text-xs uppercase tracking-wider text-secondary-text">最大亏损</p>
                <p className="mt-1 text-lg font-semibold text-danger">
                  {posData.maxLoss.toFixed(2)}
                </p>
              </div>
              <div>
                <p className="text-xs uppercase tracking-wider text-secondary-text">凯利分数</p>
                <p className="mt-1 text-lg font-semibold text-foreground">
                  {(posData.kellyFraction * 100).toFixed(1)}%
                </p>
              </div>
            </div>
            {posData.rationale.length > 0 && (
              <div className="mt-4 border-t border-border/40 pt-4">
                <p className="mb-2 text-xs font-medium text-secondary-text">计算依据</p>
                <ul className="space-y-1">
                  {posData.rationale.map((reason, idx) => (
                    <li key={idx} className="flex items-start gap-2 text-xs text-foreground">
                      <span className="mt-1.5 h-1 w-1 shrink-0 rounded-full bg-cyan" />
                      {reason}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}

        {!posLoading && !posError && !posData && (
          <p className="mt-3 text-xs text-secondary-text">
            填写股票代码、入场价、止损价等参数后计算建议仓位。
          </p>
        )}
      </SectionCard>

      {/* ===== Step 6: Stop Loss Evaluation ===== */}
      <SectionCard
        title={
          <span className="inline-flex items-center gap-1.5">
            步骤 6：止损评估
            <Tooltip
              contentClassName="max-w-[24rem]"
              content={
                <div className="space-y-2">
                  <p className="font-medium">止损评估原理</p>
                  <p>三层止损体系 + 四种计算方式，逐一检测当前价是否触及止损线，输出触发状态和盈亏。</p>
                  <div className="space-y-3">
                    <div>
                      <span className="font-medium">三层止损类型：</span>
                      <div className="text-xs space-y-1 pl-3 mt-1">
                        <p><span className="text-danger font-medium">硬止损</span> — 入场前确定的固定止损价。当前价跌破此价格即触发，是最后防线</p>
                        <p><span className="text-yellow-500 font-medium">移动止损</span> — 价格创新高后止损价同步上移，锁定已实现利润。最高价 − 2 倍 ATR（或固定 8%），随上涨自动抬升</p>
                        <p><span className="text-secondary-text font-medium">时间止损</span> — 持仓超过设定天数（默认 20 日）仍未验证入场逻辑，强制退出。天数 = 持仓日 / 时间上限 × 100%</p>
                      </div>
                    </div>
                    <div className="border-t border-border/20 pt-2">
                      <span className="font-medium">四种止损定价方式：</span>
                      <div className="text-xs space-y-1 pl-3 mt-1.5">
                        <p><span className="text-cyan font-medium">ATR（默认）</span> — 止损价 = 入场价 − 2 倍 ATR（Average True Range，14 日均真实波幅）。根据近期波动率动态定价，波动大放空间，波动小收紧</p>
                        <p><span className="text-cyan font-medium">MA（均线）</span> — 以 20 日均线作为止损线，均线有技术支撑意义，跌破均线代表趋势转弱</p>
                        <p><span className="text-cyan font-medium">结构（Structure）</span> — 以最近 60 个交易日的最低点为止损价，跌破前期关键低点意味着结构破位</p>
                        <p><span className="text-secondary-text font-medium">百分比（兜底）</span> — 当无足够数据计算以上三种时，使用固定比例（默认 −4%）作为最后保底</p>
                      </div>
                    </div>
                    <div className="border-t border-border/20 pt-2">
                      <p className="text-[11px] text-secondary-text leading-relaxed">
                        <strong>评估逻辑</strong>：输入入场价、止损价、当前价后，系统计算距止损的距离百分比和浮动盈亏百分比。若当前价 ≤ 止损价，标记为"已触发"。若提供了入场日期，还会额外检测时间止损条件（持仓天数是否超限）。对于已建立的仓位，应每日评估三层止损状态，任一止损触发即执行退出。
                      </p>
                    </div>
                  </div>
                </div>
              }
              side="bottom"
            >
              <span className="inline-flex h-5 w-5 cursor-help items-center justify-center rounded-full border border-border/60 text-xs font-bold text-cyan hover:border-cyan hover:bg-cyan/10 hover:text-cyan">
                <Info className="h-3.5 w-3.5" />
              </span>
            </Tooltip>
          </span>
        }
        subtitle="止损评估"
      >
        <div className="mb-4 grid grid-cols-1 gap-3 sm:grid-cols-2">
          <div>
            <label className="mb-1.5 block text-xs font-medium text-secondary-text">股票代码</label>
            <input
              type="text"
              value={slStockCode}
              onChange={(e) => setSlStockCode(e.target.value)}
              placeholder="600519"
              className={inputClass}
            />
          </div>
          <div>
            <label className="mb-1.5 block text-xs font-medium text-secondary-text">入场价格</label>
            <input
              type="number"
              step="0.01"
              value={slEntryPrice}
              onChange={(e) => setSlEntryPrice(e.target.value)}
              placeholder="180.50"
              className={numberInputClass}
            />
          </div>
          <div>
            <label className="mb-1.5 block text-xs font-medium text-secondary-text">当前价格</label>
            <input
              type="number"
              step="0.01"
              value={slCurrentPrice}
              onChange={(e) => setSlCurrentPrice(e.target.value)}
              placeholder="175.00"
              className={numberInputClass}
            />
          </div>
          <div>
            <label className="mb-1.5 block text-xs font-medium text-secondary-text">止损价格</label>
            <input
              type="number"
              step="0.01"
              value={slStopPrice}
              onChange={(e) => setSlStopPrice(e.target.value)}
              placeholder="170.00"
              className={numberInputClass}
            />
          </div>
        </div>
        <button
          type="button"
          onClick={() => void handleStopLoss()}
          disabled={slLoading || !slStockCode.trim() || !slEntryPrice || !slCurrentPrice || !slStopPrice}
          className="btn-primary h-9 px-4 text-sm"
        >
          {slLoading ? (
            <span className="flex items-center gap-1.5">
              <RefreshCw className="h-3.5 w-3.5 animate-spin" />
              评估中
            </span>
          ) : (
            <span className="flex items-center gap-1.5">
              <Shield className="h-3.5 w-3.5" />
              评估止损
            </span>
          )}
        </button>

        {slError && (
          <GenericError
            error={slError}
            onRetry={() => void handleStopLoss()}
            isLoading={slLoading}
          />
        )}

        {slLoading && !slData && <LoadingSpinner text="正在评估止损..." />}

        {slData && (
          <div className="mt-4 space-y-3">
            {slData.events.length === 0 ? (
              <EmptyState title="无止损事件" description="当前参数未触发任何止损事件。" />
            ) : (
              slData.events.map((event, idx) => (
                <StopEventCard key={idx} event={event} />
              ))
            )}
          </div>
        )}

        {!slLoading && !slError && !slData && (
          <p className="mt-3 text-xs text-secondary-text">
            输入股票代码、入场价、当前价和止损价，评估各止损策略是否触发。
          </p>
        )}
      </SectionCard>

      {/* ===== Step 7: Rebalance Signals ===== */}
      <SectionCard
        title={
          <span className="inline-flex items-center gap-1.5">
            步骤 7：调仓信号
            <Tooltip
              contentClassName="max-w-[24rem]"
              content={
                <div className="space-y-2">
                  <p className="font-medium">调仓信号原理</p>
                  <p>按相对强度（RS）对持仓排序，输出加减仓信号，实现「去弱留强」和「龙头切换」。</p>
                  <div className="space-y-3">
                    <div>
                      <span className="font-medium">核心逻辑：</span>
                      <div className="text-xs space-y-1 pl-3 mt-1">
                        <p><strong>RS 排序</strong> — 每只持仓计算相对强度（个股涨幅 / 同板块平均涨幅），按 RS 从高到低排名。RS &gt; 1 表示跑赢板块，RS &lt; 1 表示跑输板块</p>
                        <p><strong>分位数</strong> — 将 RS 排名映射为百分位（0%~100%），排行最高的仓位百分位最高，一眼看出每只持仓的相对位置</p>
                      </div>
                    </div>
                    <div className="border-t border-border/20 pt-2">
                      <span className="font-medium">信号规则：</span>
                      <div className="text-xs space-y-1 pl-3 mt-1.5">
                        <p><span className="text-danger font-medium">EXIT（清仓）</span> — 排名后 20% + 亏损超过 8%。弱股加速下跌，紧急止损，优先级别最高</p>
                        <p><span className="text-orange-500 font-medium">REDUCE（减仓）</span> — 排名后 20% + 亏损不超过 8%。弱势但未严重亏损，建议减半仓</p>
                        <p><span className="text-secondary-text font-medium">HOLD（持有）</span> — 排名前 50% 但不满足加仓条件。中间位置，持有观察</p>
                        <p><span className="text-cyan font-medium">ADD（加仓）</span> — 排名前 50% + RS &gt; 1.3 + 盈利超过 5%。领涨板块的强势股，可追加</p>
                        <p><span className="text-purple-500 font-medium">ROTATE（轮换）</span> — 有清仓信号且账户现金 &gt; 20% 时，用释放的资金买入当前最强候选股，完成龙头切换</p>
                      </div>
                    </div>
                    <div className="border-t border-border/20 pt-2">
                      <p className="text-[11px] text-secondary-text leading-relaxed">
                        <strong>整体策略</strong>：先 st 一列按 RS 排名，再逐只判定信号。<br />
                        同时会检查同板块持仓数是否超过 3 只上限，避免单一板块过度集中。<br />
                        实操中可以按月或按周运行一次调仓分析，持续去弱留强，让持仓始终集中在强势股上。
                      </p>
                    </div>
                  </div>
                </div>
              }
              side="bottom"
            >
              <span className="inline-flex h-5 w-5 cursor-help items-center justify-center rounded-full border border-border/60 text-xs font-bold text-cyan hover:border-cyan hover:bg-cyan/10 hover:text-cyan">
                <Info className="h-3.5 w-3.5" />
              </span>
            </Tooltip>
          </span>
        }
        subtitle="调仓信号"
      >
        <div className="mb-4">
          <label className="mb-1.5 block text-xs font-medium text-secondary-text">
            持仓列表（格式：CODE:PRICE:SECTOR，多组用换行或逗号分隔）
          </label>
          <textarea
            value={rebalancePositions}
            onChange={(e) => setRebalancePositions(e.target.value)}
            placeholder={'600519:180.50:白酒\n000858:150.20:白酒\n300750:200.00:新能源'}
            rows={4}
            className="w-full resize-y rounded-xl border border-border/40 bg-surface p-3 text-sm text-foreground placeholder:text-secondary-text outline-none transition-colors focus:border-cyan/50"
          />
        </div>
        <button
          type="button"
          onClick={() => void handleRebalance()}
          disabled={rebalanceLoading || !rebalancePositions.trim()}
          className="btn-primary h-9 px-4 text-sm"
        >
          {rebalanceLoading ? (
            <span className="flex items-center gap-1.5">
              <RefreshCw className="h-3.5 w-3.5 animate-spin" />
              分析中
            </span>
          ) : (
            <span className="flex items-center gap-1.5">
              <RefreshCw className="h-3.5 w-3.5" />
              分析调仓
            </span>
          )}
        </button>

        {rebalanceError && (
          <GenericError
            error={rebalanceError}
            onRetry={() => void handleRebalance()}
            isLoading={rebalanceLoading}
          />
        )}

        {rebalanceLoading && !rebalanceData && <LoadingSpinner text="正在分析调仓信号..." />}

        {rebalanceData && (
          <div className="mt-4 space-y-4">
            {/* Rankings Table */}
            {rebalanceData.rankings.length > 0 && (
              <div className="overflow-x-auto rounded-xl border border-border/40 bg-surface/50">
                <table className="w-full text-xs">
                  <thead className="border-b border-border/40 text-secondary-text">
                    <tr>
                      <th className="py-2.5 pl-4 pr-2 text-left font-medium">排名</th>
                      <th className="py-2.5 px-2 text-left font-medium">代码</th>
                      <th className="py-2.5 px-2 text-left font-medium">名称</th>
                      <th className="py-2.5 px-2 text-right font-medium">盈亏</th>
                      <th className="py-2.5 px-2 text-right font-medium">RS值</th>
                      <th className="py-2.5 pr-4 pl-2 text-right font-medium">百分位</th>
                    </tr>
                  </thead>
                  <tbody>
                    {rebalanceData.rankings.map((item) => (
                      <tr key={item.code} className="border-b border-border/20 hover:bg-surface/50">
                        <td className="py-2 pl-4 pr-2 text-foreground">{item.rank}</td>
                        <td className="py-2 px-2 text-foreground">{item.code}</td>
                        <td className="py-2 px-2 text-foreground">{item.name}</td>
                        <td className={cn(
                          'py-2 px-2 text-right font-medium',
                          item.pnlPct >= 0 ? 'text-success' : 'text-danger',
                        )}>
                          {item.pnlPct >= 0 ? '+' : ''}{item.pnlPct.toFixed(2)}%
                        </td>
                        <td className="py-2 px-2 text-right text-foreground">{item.rsRatio.toFixed(2)}</td>
                        <td className="py-2 pr-4 pl-2 text-right text-foreground">
                          {(item.percentile * 100).toFixed(1)}%
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            {/* Signal Cards */}
            {rebalanceData.signals.length > 0 && (
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
                {rebalanceData.signals.map((signal) => (
                  <SignalCardView key={`${signal.code}-${signal.signal}`} signal={signal} />
                ))}
              </div>
            )}

            {rebalanceData.rankings.length === 0 && rebalanceData.signals.length === 0 && (
              <EmptyState title="无调仓信号" description="当前持仓未产生明确的调仓信号。" />
            )}
          </div>
        )}

        {!rebalanceLoading && !rebalanceError && !rebalanceData && (
          <p className="mt-3 text-xs text-secondary-text">
            输入持仓列表（CODE:PRICE:SECTOR 格式），分析调仓信号和排名。
          </p>
        )}
      </SectionCard>
    </div>
  );
};

// ============ Sub-Components ============

const FunnelCard: React.FC<{
  label: string;
  value: number;
  color: string;
}> = ({ label, value, color }) => (
  <div className="rounded-xl border border-border/40 bg-surface/50 p-3 text-center">
    <p className="text-xs text-secondary-text">{label}</p>
    <p className={cn('mt-1 text-xl font-bold', color)}>{value}</p>
  </div>
);

const CandidateCard: React.FC<{
  candidate: CandidateItem;
}> = ({ candidate }) => {
  // A 股惯例：上涨用红色(danger)，下跌用绿色(success)
  const priceColor = candidate.changePct > 0 ? 'text-danger' : candidate.changePct < 0 ? 'text-success' : 'text-foreground';
  const score = candidate.factors?.compositeScore ?? 0;
  return (
    <Card variant="bordered" padding="sm">
      <div className="flex items-start justify-between gap-2">
        <div>
          <p className="text-sm font-semibold text-foreground">{candidate.name}</p>
          <p className="text-xs text-secondary-text">{candidate.code}</p>
        </div>
        <Badge variant={score >= 70 ? 'success' : score >= 50 ? 'warning' : 'default'}>
          {score.toFixed(1)}
        </Badge>
      </div>
      <div className="mt-3 grid grid-cols-2 gap-2 text-xs">
        <div>
          <span className="text-secondary-text">价格</span>
          <p className={cn('font-medium', priceColor)}>{candidate.price.toFixed(2)}</p>
        </div>
        <div>
          <span className="text-secondary-text">涨跌幅</span>
          <p className={cn('font-medium', priceColor)}>
            {candidate.changePct >= 0 ? '+' : ''}{candidate.changePct.toFixed(2)}%
          </p>
        </div>
        <div>
          <span className="text-secondary-text">均线排列</span>
          <p className="font-medium text-foreground">{candidate.maAlignment}</p>
        </div>
        <div>
          <span className="text-secondary-text">换手率</span>
          <p className="font-medium text-foreground">{candidate.turnoverRate.toFixed(2)}%</p>
        </div>
      </div>
    </Card>
  );
};

const SectorDurabilityRow: React.FC<{
  item: SectorDurabilityItem;
}> = ({ item }) => {
  const trendIcon = item.scoreTrend > 0.1 ? '↑' : item.scoreTrend < -0.1 ? '↓' : '→';
  const trendColor = item.scoreTrend > 0.1 ? 'text-success' : item.scoreTrend < -0.1 ? 'text-danger' : 'text-secondary-text';

  const classificationTooltip: Record<string, string> = {
    '主线': '连续5天+在榜且出现率≥60%，板块持续性最强，可作为核心配置方向',
    '强势轮动': '连续3天+在榜且出现率≥40%，或评分趋势强劲，属于高弹性板块',
    '轮动': '出现率≥30%，板块反复活跃但未形成主线，适合短线参与',
    '脉冲': '隔日上榜、持续≤2天，属一日游行情，不宜追高',
    '异动': '突然上榜、此前很少出现，可能为新主线启动信号，需持续观察',
    '退潮': '评分趋势持续向下，板块热度减退，建议回避',
    '未分类': '暂无明确分类，需结合市场整体判断，持续观察后续排名变化',
  };

  return (
    <tr className="border-b border-border/20 hover:bg-surface/50">
      <td className="py-2.5 pr-3 text-foreground">{item.name}</td>
      <td className="py-2.5 pr-3">
        <Tooltip content={classificationTooltip[item.classificationCn] || ''} side="top">
          <span className="cursor-help"><ClassificationBadge classification={item.classificationCn} /></span>
        </Tooltip>
      </td>
      <td className="py-2.5 pr-3 text-right text-foreground">
        <Tooltip
          content={`连续在板块排行榜前 30 名出现的交易日数。${item.consecutiveDays >= 5 ? '已达 5 天以上，配合出现率≥60% 可判定为主线' : item.consecutiveDays >= 3 ? '达到 3 天以上，配合出现率≥40% 有形成主线的潜力' : '持续性不足，暂未形成主线'}`}
          side="top"
        >
          <span className="cursor-help">{item.consecutiveDays}</span>
        </Tooltip>
      </td>
      <td className="py-2.5 pr-3 text-right text-foreground">
        <Tooltip
          content={`在回看期内进入板块排行榜前 3 名的总次数，次数越多说明板块反复活跃，非一日游脉冲行情`}
          side="top"
        >
          <span className="cursor-help">{item.top3Count}</span>
        </Tooltip>
      </td>
      <td className={cn('py-2.5 text-right font-medium', trendColor)}>
        <Tooltip
          content={item.scoreTrend > 0.1
            ? `评分呈上升趋势（${item.scoreTrend.toFixed(1)}），板块关注度在提升`
            : item.scoreTrend < -0.1
              ? `评分呈下降趋势（${item.scoreTrend.toFixed(1)}），板块热度在减退`
              : '评分平稳，无明显方向'}
          side="top"
        >
          <span className="cursor-help">{trendIcon}</span>
        </Tooltip>
      </td>
    </tr>
  );
};

const StopEventCard: React.FC<{
  event: StopEvent;
}> = ({ event }) => {
  const triggerColor = event.triggered ? 'bg-danger/10 text-danger border-danger/20' : 'bg-success/10 text-success border-success/20';
  const triggerText = event.triggered ? '已触发' : '未触发';
  return (
    <div className="rounded-xl border border-border/40 bg-surface/50 p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-2">
          <Shield className={cn('h-4 w-4', event.triggered ? 'text-danger' : 'text-success')} />
          <span className="text-sm font-medium text-foreground">{event.type}</span>
          <span className={cn('inline-flex items-center rounded-full border px-2 py-0.5 text-[10px] font-medium', triggerColor)}>
            {triggerText}
          </span>
        </div>
        <span className={cn(
          'text-sm font-semibold',
          event.pnlPct >= 0 ? 'text-success' : 'text-danger',
        )}>
          {event.pnlPct >= 0 ? '+' : ''}{event.pnlPct.toFixed(2)}%
        </span>
      </div>
      <p className="mt-2 text-xs text-secondary-text">{event.reason}</p>
    </div>
  );
};

const SignalCardView: React.FC<{
  signal: SignalCard;
}> = ({ signal }) => {
  return (
    <Card variant="bordered" padding="sm">
      <div className="flex items-start justify-between gap-2">
        <div>
          <p className="text-sm font-semibold text-foreground">{signal.name}</p>
          <p className="text-xs text-secondary-text">{signal.code}</p>
        </div>
        <SignalBadge signal={signal.signal} />
      </div>
      <p className="mt-2 text-xs text-secondary-text leading-relaxed">{signal.reason}</p>
    </Card>
  );
};

export default StockPickPage;
