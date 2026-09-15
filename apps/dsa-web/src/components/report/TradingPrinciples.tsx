import type React from 'react';
import { Info } from 'lucide-react';
import type { TradingAnnotations } from '../../types/analysis';
import { Card, Tooltip } from '../common';
import { getReportText, normalizeReportLanguage } from '../../utils/reportLanguage';

interface TradingPrinciplesProps {
  annotations?: TradingAnnotations;
  reportLanguage?: string;
}

const ALIGNMENT_EMOJI: Record<string, string> = {
  all_bullish: '🟢',
  all_bearish: '🔴',
  long_med_bullish_short_diverge: '🟡',
  long_bullish_med_diverge: '🟠',
  bearish_with_short_rebound: '🟡',
  mixed: '⚪',
};

const ALIGNMENT_TOOLTIP: Record<string, string> = {
  all_bullish: '全周期看涨 → 所有周期（大、中、小）均为上涨信号',
  all_bearish: '全周期看跌 → 所有周期均为下跌信号',
  long_med_bullish_short_diverge: '长中看涨、短周期背离 → 大周期、中周期看涨，但小周期出现背离（价格可能短期回调）',
  long_bullish_med_diverge: '长期看涨、中期背离 → 大周期看涨，但中周期出现背离（中期存在调整需求）',
  bearish_with_short_rebound: '看跌伴随短期反弹 → 整体趋势偏空，但小周期可能有短暂反弹',
  mixed: '信号混杂 / 无明确方向 → 各周期信号不一致，建议观望',
};

const HEAT_EMOJI: Record<string, string> = {
  '热门': '🔥',
  '活跃': '⚡',
  '中性': '➖',
  '冷门': '❄️',
  Hot: '🔥',
  Active: '⚡',
  Neutral: '➖',
  Cold: '❄️',
};

const HEAT_TOOLTIP: Record<string, string> = {
  '热门': '量比≥3 且换手率较高，资金高度关注，流动性好，适合顺势参与',
  '活跃': '温和放量且有一定涨幅，交易较活跃，可适当关注',
  '中性': '交投平稳，量价无明显异常，按常规策略操作',
  '冷门': '缩量且低换手，交投清淡，不易进出，建议回避',
  Hot: 'Volume ratio ≥3 with high turnover, strong capital attention, good liquidity',
  Active: 'Moderate volume increase with some gain, relatively active',
  Neutral: 'Normal trading, no significant volume or price anomalies',
  Cold: 'Low volume and turnover, illiquid, avoid',
};

const TREND_TOOLTIP: Record<string, string> = {
  '上升趋势确认': '多头排列 + MACD 看多 + 趋势强度≥60，趋势明确，可顺势操作',
  '上升趋势（待确认）': '多头排列但 MACD 或趋势强度未完全确认，需等待进一步信号再入场',
  '下降趋势': '空头排列，应回避或仅做超跌反弹，不宜追涨',
  '偏强震荡': '趋势强度≥50 但未形成多头排列，适合波段操作，高抛低吸',
  '偏弱震荡': '无明显趋势，建议观望，等待方向明确',
  'Up Trend Confirmed': 'Bullish MA alignment + MACD bullish + strength ≥60, clear uptrend',
  'Up Trend (Pending)': 'Bullish MA alignment but MACD/strength not confirmed, wait for signals',
  'Down Trend': 'Bearish MA alignment, avoid or mean-reversion only',
  'Bullish Consolidation': 'Strength ≥50 but no clear MA alignment, range-trading suitable',
  'Bearish Consolidation': 'No clear trend, wait for direction',
};

const getTrendStatusColor = (status: string): string => {
  if (status.includes('上升') || status.includes('Up Trend')) return 'var(--home-price-up)';
  if (status.includes('下降') || status.includes('Down Trend')) return 'var(--home-price-down)';
  return 'var(--home-strategy-take)';
};

export const TradingPrinciples: React.FC<TradingPrinciplesProps> = ({
  annotations,
  reportLanguage: lang,
}) => {
  const language = normalizeReportLanguage(lang);
  const text = getReportText(language);

  if (!annotations) return null;

  const { cycleStructure, cycleResonance, buyQuality, trendConfirmation, heatLabel } = annotations;
  const hasData = cycleStructure?.alignment || cycleResonance?.resonanceSummary || buyQuality?.qualityScore
    || trendConfirmation?.status || heatLabel?.label;
  if (!hasData) return null;

  return (
    <Card variant="bordered" padding="md" className="home-panel-card !overflow-visible">
      <div className="mb-4">
        <span className="label-uppercase inline-flex items-center gap-1.5">
          {text.tradingPrinciples || '交易原则'}
           <Tooltip
            contentClassName="max-w-[24rem]"
            content={
              <div className="space-y-2">
                <p className="font-medium">筛选原理</p>
                <p>交易原则基于AI对个股三个维度的技术面评估，判断当前是否适合交易：</p>
                <div className="space-y-3">
                  <div>
                    <span className="inline-flex items-center justify-center w-4.5 h-4.5 rounded bg-primary/15 text-primary text-[10px] font-bold mr-1">1</span>
                    <span className="font-medium">热度</span> — 通过换手率（成交活跃度）与动量趋势判断市场对该股的关注程度。
                    分四级：
                    <div className="text-xs space-y-1 pl-5 mt-1">
                      <p><span className="text-amber-500 font-medium">🔥 热门</span> — 量比≥3 且换手率较高，资金高度关注，流动性好，适合顺势参与</p>
                      <p><span className="text-yellow-500 font-medium">⚡ 活跃</span> — 温和放量且有一定涨幅，交易较活跃，可适当关注</p>
                      <p><span className="text-gray-400 font-medium">➖ 中性</span> — 交投平稳，量价无明显异常，按常规策略操作</p>
                      <p><span className="text-blue-400 font-medium">❄️ 冷门</span> — 缩量且低换手，交投清淡，不易进出，建议回避</p>
                    </div>
                  </div>
                  <div className="border-t border-border/20 pt-2">
                    <span className="inline-flex items-center justify-center w-4.5 h-4.5 rounded bg-primary/15 text-primary text-[10px] font-bold mr-1">2</span>
                    <span className="font-medium">周期结构</span> — 分别考察大周期（长期趋势）、中周期（中期走势）、小周期（短期波动）三个时间尺度的信号方向。
                    六种状态：
                    <div className="text-xs space-y-1 pl-5 mt-1.5">
                      <p><span className="text-success font-medium">🟢 全周期看涨</span> — 大中小周期均为上涨信号，趋势一致性最强</p>
                      <p><span className="text-danger font-medium">🔴 全周期看跌</span> — 所有周期均为下跌信号，应回避</p>
                      <p><span className="text-yellow-500 font-medium">🟡 长中看涨短背离</span> — 长中期看涨，但短期背离（可能回调），适合等待低吸</p>
                      <p><span className="text-orange-500 font-medium">🟠 长多中背离</span> — 长期看涨但中期调整中，需要等中期修复后再入场</p>
                      <p><span className="text-yellow-500 font-medium">🟡 空头短反弹</span> — 整体偏空，但短期可能有反弹，仅适合短线快进快出</p>
                      <p><span className="text-gray-400 font-medium">⚪ 信号混杂</span> — 各周期无明确方向，建议观望</p>
                    </div>
                  </div>
                  <div className="border-t border-border/20 pt-2">
                    <span className="inline-flex items-center justify-center w-4.5 h-4.5 rounded bg-primary/15 text-primary text-[10px] font-bold mr-1">3</span>
                    <span className="font-medium">趋势确认</span> — 基于均线排列（MA5/MA10/MA20/MA60）与 MACD 判断趋势状态，
                    同时检测乖离率（偏离均线过远有回调风险），给出信号强度评分。
                    <div className="text-xs space-y-1 pl-5 mt-1.5">
                      <p><span className="text-success font-medium">🟢 上升趋势确认</span> — 多头排列 + MACD 看多 + 趋势强度≥60，趋势明确</p>
                      <p><span className="text-yellow-500 font-medium">🟡 上升趋势（待确认）</span> — 多头排列但 MACD 或强度未确认，需等进一步信号</p>
                      <p><span className="text-danger font-medium">🔴 下降趋势</span> — 空头排列，应回避或仅做超跌反弹</p>
                      <p><span className="text-orange-500 font-medium">🟠 偏强震荡</span> — 趋势强度≥50 但未形成多头排列，适合波段操作</p>
                      <p><span className="text-gray-400 font-medium">⚪ 偏弱震荡</span> — 无明显趋势，建议观望</p>
                    </div>
                    <div className="text-xs mt-1.5 pl-5">
                      <span className="font-medium">乖离率预警：</span>
                      偏离 MA5 超过 5% → 追高风险；低于 -5% → 超跌反弹机会
                    </div>
                  </div>
                </div>
              </div>
            }
            side="top"
          >
            <span className="inline-flex h-5 w-5 cursor-help items-center justify-center rounded-full border border-border/60 text-xs font-bold text-cyan hover:border-cyan hover:bg-cyan/10 hover:text-cyan">
              <Info className="h-3.5 w-3.5" />
            </span>
          </Tooltip>
        </span>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {heatLabel?.label && (
          <div className="flex items-start gap-3">
            <Tooltip content={HEAT_TOOLTIP[heatLabel.label] || ''} side="top">
              <span className="text-2xl flex-shrink-0 cursor-help">
                {HEAT_EMOJI[heatLabel.label] || '➖'}
              </span>
            </Tooltip>
            <div className="space-y-0.5 min-w-0">
              <p className="text-sm font-medium text-foreground truncate">
                {text.heat || '热度'}: {heatLabel.label}
              </p>
              <p className="text-xs text-muted-text truncate">
                {[heatLabel.turnoverDesc, heatLabel.momentumDesc].filter(Boolean).join(' · ')}
              </p>
            </div>
          </div>
        )}

        {cycleStructure?.alignment && (
          <div className="flex items-start gap-3">
            <Tooltip content={ALIGNMENT_TOOLTIP[cycleStructure.alignment] || ''} side="top">
              <span className="text-2xl flex-shrink-0 cursor-help">
                {ALIGNMENT_EMOJI[cycleStructure.alignment] || '⚪'}
              </span>
            </Tooltip>
            <div className="space-y-0.5 min-w-0">
              <p className="text-sm font-medium text-foreground">
                {text.cycleStructure || '周期结构'}
              </p>
              <p className="text-xs text-muted-text">
                {[cycleStructure.longTerm, cycleStructure.mediumTerm, cycleStructure.shortTerm]
                  .filter(Boolean)
                  .join('｜')}
              </p>
            </div>
          </div>
        )}

        {trendConfirmation?.status && (
          <div className="flex items-start gap-3">
            <span
              className="text-sm font-bold flex-shrink-0 px-2 py-0.5 rounded"
              style={{
                backgroundColor: `${getTrendStatusColor(trendConfirmation.status)}15`,
                color: getTrendStatusColor(trendConfirmation.status),
              }}
            >
              {trendConfirmation.signalStrength || '—'}
            </span>
            <div className="space-y-0.5 min-w-0">
              <Tooltip
                content={(() => {
                  const s = trendConfirmation.status;
                  for (const [key, tip] of Object.entries(TREND_TOOLTIP)) {
                    if (s.includes(key)) return tip;
                  }
                  return '';
                })()}
                side="top"
              >
                <p className="text-sm font-medium text-foreground truncate cursor-help">
                  {trendConfirmation.status}
                </p>
              </Tooltip>
              {trendConfirmation.biasWarning && (
                <p className="text-xs text-muted-text truncate">
                  {trendConfirmation.biasWarning}
                </p>
              )}
            </div>
          </div>
        )}

        {cycleResonance?.resonanceSummary && (
          <div className="flex items-start gap-3">
            <span className="text-2xl flex-shrink-0">
              {cycleResonance.resonanceLevel?.includes('三级') ? '🎯'
                : cycleResonance.resonanceLevel?.includes('两级') ? '📊'
                : cycleResonance.resonanceLevel?.includes('背离') ? '⚠️'
                : '🔍'}
            </span>
            <div className="space-y-0.5 min-w-0">
              <p className="text-sm font-medium text-foreground">
                周期共振
                {cycleResonance.resonanceScore != null && (
                  <span className="ml-1 text-xs text-cyan">({cycleResonance.resonanceScore}/10)</span>
                )}
              </p>
              <p className="text-xs text-muted-text truncate">
                {[cycleResonance.weeklyTrend, cycleResonance.dailyStructure, cycleResonance.hourlySignal]
                  .filter(Boolean).join(' → ')}
              </p>
              <p className="text-xs text-secondary-text truncate">
                {cycleResonance.resonanceSummary}
              </p>
            </div>
          </div>
        )}

        {buyQuality?.qualityScore != null && (
          <div className="flex items-start gap-3">
            <span className="text-2xl flex-shrink-0">
              {buyQuality.qualityScore >= 8 ? '⭐' : buyQuality.qualityScore >= 6 ? '👍' : buyQuality.qualityScore >= 4 ? '👀' : '⏳'}
            </span>
            <div className="space-y-0.5 min-w-0 flex-1">
              <p className="text-sm font-medium text-foreground">
                买点质量: {buyQuality.qualityScore}/10
              </p>
              {buyQuality.qualityFactors?.length > 0 && (
                <div className="flex flex-wrap gap-1 mt-1">
                  {buyQuality.qualityFactors.map((f, i) => (
                    <span key={i}
                      className="rounded px-1.5 py-0.5 text-[11px] font-medium"
                      style={{
                        backgroundColor: f.status.includes('✅') ? 'var(--home-price-up)15' : f.status.includes('⚠️') ? 'var(--home-strategy-take)15' : 'var(--surface)',
                        color: f.status.includes('✅') ? 'var(--home-price-up)' : f.status.includes('⚠️') ? 'var(--home-strategy-take)' : 'var(--text-secondary)',
                      }}
                    >
                      {f.name}
                    </span>
                  ))}
                </div>
              )}
              {buyQuality.qualityFactors?.length > 0 && (
                <div className="mt-1 space-y-0.5">
                  {buyQuality.qualityFactors.map((f, i) => (
                    <p key={i} className="text-[11px] text-muted-text">
                      {f.status} {f.name}{f.detail ? `: ${f.detail}` : ''}
                    </p>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </Card>
  );
};
