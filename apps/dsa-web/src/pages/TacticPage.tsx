import type React from 'react';
import { useEffect, useState } from 'react';
import { Check, ChevronDown, ChevronUp, Code as CodeIcon, Copy, Play, TrendingUp, X as XIcon } from 'lucide-react';
import { Badge, SectionCard } from '../components/common';
import { tacticApi, type OversoldBounceResult, type OversoldCandidate, type IndustryResearchResult } from '../api/tactic';
import { getParsedApiError, type ParsedApiError } from '../api/error';
import type { TripleVolumeResult, TripleVolumeCandidate } from '../types/tactic';
import { cn } from '../utils/cn';

const CodeBlock: React.FC<{ title: string; code: string; lang?: string }> = ({ title, code, lang }) => {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    await navigator.clipboard.writeText(code);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="group relative rounded-2xl border border-border/40 bg-surface/50 overflow-hidden">
      <div className="flex items-center justify-between border-b border-border/30 px-4 py-2.5">
        <div className="flex items-center gap-2">
          <CodeIcon className="h-4 w-4 text-cyan" />
          <span className="text-xs font-medium text-foreground">{title}</span>
          {lang && (
            <Badge variant="default" size="sm" className="text-[10px]">{lang}</Badge>
          )}
        </div>
        <button
          type="button"
          onClick={handleCopy}
          className="flex items-center gap-1.5 rounded-lg border border-border/40 bg-card/60 px-2.5 py-1 text-xs text-secondary-text opacity-0 transition-all hover:bg-hover hover:text-foreground group-hover:opacity-100"
        >
          {copied ? (
            <>
              <Check className="h-3 w-3 text-success" />
              已复制
            </>
          ) : (
            <>
              <Copy className="h-3 w-3" />
              复制
            </>
          )}
        </button>
      </div>
      <pre className="overflow-x-auto p-4 text-sm font-mono leading-relaxed text-secondary-text whitespace-pre">
        {code}
      </pre>
    </div>
  );
};

const RuleItem: React.FC<{ index: number; text: string }> = ({ index, text }) => (
  <li className="flex items-start gap-3 py-2">
    <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-cyan/10 text-xs font-semibold text-cyan">
      {index}
    </span>
    <span className="text-sm text-foreground leading-relaxed pt-0.5">{text}</span>
  </li>
);

const Collapsible: React.FC<{ title: string; defaultOpen?: boolean; children: React.ReactNode }> = ({
  title,
  defaultOpen = false,
  children,
}) => {
  const [open, setOpen] = useState(defaultOpen);

  return (
    <div className="rounded-2xl border border-border/40 overflow-hidden">
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="flex w-full items-center justify-between bg-surface/50 px-5 py-3.5 text-left transition-colors hover:bg-hover/30"
      >
        <span className="text-sm font-semibold text-foreground">{title}</span>
        {open ? (
          <ChevronUp className="h-4 w-4 text-secondary-text" />
        ) : (
          <ChevronDown className="h-4 w-4 text-secondary-text" />
        )}
      </button>
      {open && <div className="border-t border-border/40 p-5">{children}</div>}
    </div>
  );
};

const TONG_DA_XIN_FORMULA = `{三倍量战法 选股公式}
五日均量:=MA(V,5);
三倍量:=V>=五日均量*3;
涨幅达标:=C/REF(C,1)>=1.05;
换手达标:=DYNAINFO(37)>=3;
低位区间:=(HHV(C,60)-LLV(C,60))/LLV(C,60)<=0.5;
均线多头:=MA(C,5)>MA(C,10) AND MA(C,10)>MA(C,20);
实体阳线:=O<C;

三倍量选股:三倍量 AND 涨幅达标 AND 换手达标 AND 低位区间 AND 均线多头 AND 实体阳线;`;

const TONG_DA_XIN_SUB = `{三倍量副图}
五日均量:MA(V,5),COLORYELLOW;
三倍量线:五日均量*3,COLORMAGENTA;
放量信号:V>=五日均量*3,VOLSTICK;
DRAWICON(放量信号,V*0.8,1);`;

const TONG_HUA_SHUN_FORMULA = `五日均量=MA(VOL,5);
三倍量=VOL>=五日均量*3;
涨幅=C/REF(C,1)>=1.05;
换手=HSL>=3;
低位=(HHV(C,60)-LLV(C,60))/LLV(C,60)<=0.5;
多头=MA(C,5)>MA(C,10)&&MA(C,10)>MA(C,20);
阳线=OPEN<C;

选股:三倍量&&涨幅&&换手&&低位&&多头&&阳线;`;

const ADVANCED_FORMULA = `{最强三倍量突破}
V>=MA(V,5)*3 AND C>REF(HHV(C,20),1) AND C/REF(C,1)>1.06;`;

const FILTER_CONDITIONS = [
  '成交量大于3倍5日均量',
  '当日涨幅≥5% 中大阳线',
  '换手率≥3% 有真实资金',
  '60天内涨幅不超50% 避开高位出货',
  '5/10/20日线多头排列',
  '只选实体阳线，剔除冲高回落假放量',
];

const USAGE_RULES = [
  '盘后选股：每天收盘筛选，不盘中乱选',
  '选出后只做缩量回踩5日线低吸',
  '止损：三倍量阳线最低价跌破离场',
  '高位涨停巨量直接排除',
];

const ConditionCheck: React.FC<{ passed: boolean; label: string }> = ({ passed, label }) => (
  <span className={`inline-flex items-center gap-1 text-xs ${passed ? 'text-success' : 'text-muted-text'}`}>
    {passed ? <Check className="h-3 w-3" /> : <XIcon className="h-3 w-3" />}
    {label}
  </span>
);

const ResultRow: React.FC<{ c: TripleVolumeCandidate }> = ({ c }) => (
  <tr className="border-b border-border/30 hover:bg-hover/20 transition-colors">
    <td className="px-3 py-2.5">
      <div className="flex flex-col">
        <span className="text-sm font-medium text-foreground">{c.code}</span>
        <span className="text-xs text-muted-text">{c.name}</span>
      </div>
    </td>
    <td className="px-3 py-2.5 text-sm tabular-nums text-foreground">{c.price.toFixed(2)}</td>
    <td className="px-3 py-2.5">
      <span className={`text-sm tabular-nums font-medium ${c.changePct >= 0 ? 'text-danger' : 'text-success'}`}>
        {c.changePct >= 0 ? '+' : ''}{c.changePct.toFixed(2)}%
      </span>
    </td>
    <td className="px-3 py-2.5 text-sm tabular-nums text-foreground">{c.turnoverRate.toFixed(1)}%</td>
    <td className="px-3 py-2.5 text-sm tabular-nums text-foreground">
      <span className={c.volumeRatio >= 3 ? 'text-warning font-medium' : ''}>{c.volumeRatio.toFixed(1)}x</span>
    </td>
    <td className="px-3 py-2.5">
      <div className="flex flex-wrap gap-1">
        <ConditionCheck passed={c.passVolume} label="量" />
        <ConditionCheck passed={c.passChange} label="涨" />
        <ConditionCheck passed={c.passTurnover} label="换" />
        <ConditionCheck passed={c.passPosition} label="位" />
        <ConditionCheck passed={c.passMaAlignment} label="线" />
        <ConditionCheck passed={c.passSolidYang} label="阳" />
      </div>
    </td>
    <td className="px-3 py-2.5 text-center">
      <Badge variant={c.score >= 5 ? 'success' : c.score >= 3 ? 'info' : 'warning'} size="sm" glow={c.score >= 5}>
        {c.score}/6
      </Badge>
    </td>
  </tr>
);

type TabKey = 'triple-volume' | 'multi-cycle' | 'intraday-t0' | 'oversold-bounce' | 'industry-research';

const TABS: { key: TabKey; label: string; desc: string }[] = [
  { key: 'triple-volume', label: '三倍量战法', desc: '放量突破选股' },
  { key: 'oversold-bounce', label: '超跌反弹战法', desc: '恐慌超跌出击' },
  { key: 'industry-research', label: '产业链研究', desc: '逆向拆解选股' },
  { key: 'multi-cycle', label: '周期共振买卖点', desc: '多周期 + 量价确认' },
  { key: 'intraday-t0', label: '分时做T格子战法', desc: '红黄线乖离修复' },
];

const TacticPage: React.FC = () => {
  const [activeTab, setActiveTab] = useState<TabKey>('triple-volume');

  useEffect(() => {
    if (activeTab === 'multi-cycle') {
      document.title = '周期共振买卖点 - DSA';
    } else if (activeTab === 'intraday-t0') {
      document.title = '分时做T格子战法 - DSA';
    } else if (activeTab === 'oversold-bounce') {
      document.title = '超跌反弹战法 - DSA';
    } else if (activeTab === 'industry-research') {
      document.title = '产业链研究战法 - DSA';
    } else {
      document.title = '三倍量战法 - DSA';
    }
  }, [activeTab]);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<ParsedApiError | null>(null);
  const [result, setResult] = useState<TripleVolumeResult | null>(null);
  const [minVolumeRatio, setMinVolumeRatio] = useState(3.0);
  const [minChangePct, setMinChangePct] = useState(5.0);
  const [minTurnoverRate, setMinTurnoverRate] = useState(3.0);

  const [oversoldLoading, setOversoldLoading] = useState(false);
  const [oversoldError, setOversoldError] = useState<ParsedApiError | null>(null);
  const [oversoldResult, setOversoldResult] = useState<OversoldBounceResult | null>(null);
  const [oversoldDays, setOversoldDays] = useState(5);
  const [oversoldMinDropPct, setOversoldMinDropPct] = useState(20.0);
  const [oversoldMaxBiasPct, setOversoldMaxBiasPct] = useState(-8.0);

  const [researchLoading, setResearchLoading] = useState(false);
  const [researchError, setResearchError] = useState<ParsedApiError | null>(null);
  const [researchResult, setResearchResult] = useState<IndustryResearchResult | null>(null);
  const [researchSector, setResearchSector] = useState('');
  const [researchMinMarketCap, setResearchMinMarketCap] = useState(30.0);
  const [researchMaxMarketCap, setResearchMaxMarketCap] = useState(500.0);
  const [researchMinScore, setResearchMinScore] = useState(60.0);

  const handleRun = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await tacticApi.tripleVolumeScreen(minVolumeRatio, minChangePct, minTurnoverRate);
      setResult(data);
    } catch (err) {
      setError(getParsedApiError(err));
    } finally {
      setLoading(false);
    }
  };

  const handleOversoldRun = async () => {
    setOversoldLoading(true);
    setOversoldError(null);
    try {
      const data = await tacticApi.oversoldBounceScreen(oversoldDays, oversoldMinDropPct, oversoldMaxBiasPct);
      setOversoldResult(data);
    } catch (err) {
      setOversoldError(getParsedApiError(err));
    } finally {
      setOversoldLoading(false);
    }
  };

  const handleResearchRun = async () => {
    if (!researchSector.trim()) return;
    setResearchLoading(true);
    setResearchError(null);
    try {
      const data = await tacticApi.industryResearchScreen(
        researchSector.trim(),
        researchMinMarketCap,
        researchMaxMarketCap,
        researchMinScore,
      );
      setResearchResult(data);
    } catch (err) {
      setResearchError(getParsedApiError(err));
    } finally {
      setResearchLoading(false);
    }
  };

  return (
    <div className="min-h-full flex flex-col rounded-[1.5rem] bg-transparent">
      <header className="flex-shrink-0 border-b border-border/40 px-4 py-4 sm:px-6">
        <div className="flex max-w-5xl flex-wrap items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-[linear-gradient(135deg,var(--color-cyan),var(--color-purple))] shadow-[0_8px_24px_var(--nav-brand-shadow)]">
            <TrendingUp className="h-5 w-5 text-white" />
          </div>
          <div>
            <h1 className="text-lg font-semibold text-foreground">战法</h1>
            <p className="text-xs text-secondary-text">实战策略库 · 量化选股 · 买卖点指南</p>
          </div>
        </div>
        <nav className="mt-4 flex gap-1" aria-label="战法标签">
          {TABS.map((tab) => (
            <button
              key={tab.key}
              type="button"
              onClick={() => setActiveTab(tab.key)}
              className={cn(
                'rounded-xl px-4 py-2.5 text-left transition-colors',
                activeTab === tab.key
                  ? 'bg-cyan/10 border border-cyan/20 text-foreground'
                  : 'border border-transparent text-secondary-text hover:bg-hover hover:text-foreground'
              )}
            >
              <div className="text-sm font-semibold">{tab.label}</div>
              <div className="text-[11px] text-muted-text">{tab.desc}</div>
            </button>
          ))}
        </nav>
      </header>

      <main className="flex-1 overflow-y-auto p-4 sm:p-6">
        {activeTab === 'triple-volume' ? (
          <div className="mx-auto max-w-4xl space-y-5">
          <SectionCard title="运行选股" subtitle="RUN SCREENING">
            <div className="flex flex-wrap items-end gap-3">
              <div className="flex flex-col gap-1">
                <label className="text-xs text-muted-text">量比倍数</label>
                <input
                  type="number"
                  min={2}
                  max={5}
                  step={0.5}
                  value={minVolumeRatio}
                  onChange={(e) => setMinVolumeRatio(parseFloat(e.target.value) || 3)}
                  className="input-surface input-focus-glow h-9 w-20 rounded-xl border bg-transparent px-3 text-sm text-center tabular-nums"
                />
              </div>
              <div className="flex flex-col gap-1">
                <label className="text-xs text-muted-text">最低涨幅(%)</label>
                <input
                  type="number"
                  min={3}
                  max={10}
                  step={0.5}
                  value={minChangePct}
                  onChange={(e) => setMinChangePct(parseFloat(e.target.value) || 5)}
                  className="input-surface input-focus-glow h-9 w-20 rounded-xl border bg-transparent px-3 text-sm text-center tabular-nums"
                />
              </div>
              <div className="flex flex-col gap-1">
                <label className="text-xs text-muted-text">最低换手(%)</label>
                <input
                  type="number"
                  min={1}
                  max={10}
                  step={0.5}
                  value={minTurnoverRate}
                  onChange={(e) => setMinTurnoverRate(parseFloat(e.target.value) || 3)}
                  className="input-surface input-focus-glow h-9 w-20 rounded-xl border bg-transparent px-3 text-sm text-center tabular-nums"
                />
              </div>
              <button
                type="button"
                onClick={handleRun}
                disabled={loading}
                className="btn-primary flex items-center gap-2 h-9 px-4 text-sm"
              >
                {loading ? (
                  <>
                    <div className="h-4 w-4 animate-spin rounded-full border-2 border-white/20 border-t-white" />
                    筛选中...
                  </>
                ) : (
                  <>
                    <Play className="h-4 w-4" />
                    运行选股
                  </>
                )}
              </button>
            </div>

            {error && (
              <div className="mt-3 rounded-xl border border-danger/30 bg-danger/8 px-3 py-2">
                <p className="text-xs text-danger">{error.message || '选股失败，请稍后重试'}</p>
              </div>
            )}

            {result && (
              <div className="mt-4 space-y-3">
                <div className="flex flex-wrap items-center gap-3 text-xs text-secondary-text">
                  <span>扫描 <strong className="text-foreground">{result.totalScanned}</strong> 只</span>
                  <span className="text-border/60">→</span>
                  <span>预筛通过 <strong className="text-foreground">{result.afterPrescreen}</strong> 只</span>
                  <span className="text-border/60">→</span>
                  <span>最终入选 <strong className="text-cyan">{result.afterDetailed}</strong> 只</span>
                  <span className="text-muted-text ml-auto">耗时 {result.elapsedSeconds}s</span>
                </div>

                {result.candidates.length > 0 ? (
                  <div className="rounded-2xl border border-border/40 overflow-hidden">
                    <div className="overflow-x-auto">
                      <table className="w-full text-sm">
                        <thead className="bg-surface/50 border-b border-border/40">
                          <tr className="text-left">
                            <th className="px-3 py-2.5 text-xs font-medium text-muted-text">股票</th>
                            <th className="px-3 py-2.5 text-xs font-medium text-muted-text">现价</th>
                            <th className="px-3 py-2.5 text-xs font-medium text-muted-text">涨幅</th>
                            <th className="px-3 py-2.5 text-xs font-medium text-muted-text">换手</th>
                            <th className="px-3 py-2.5 text-xs font-medium text-muted-text">量比</th>
                            <th className="px-3 py-2.5 text-xs font-medium text-muted-text">条件</th>
                            <th className="px-3 py-2.5 text-xs font-medium text-muted-text text-center">评分</th>
                          </tr>
                        </thead>
                        <tbody>
                          {result.candidates.map((c) => (
                            <ResultRow key={c.code} c={c} />
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                ) : (
                  <div className="rounded-2xl border border-dashed border-border/60 px-4 py-8 text-center">
                    <p className="text-sm text-muted-text">未筛选出符合条件的股票</p>
                    <p className="mt-1 text-xs text-secondary-text">可尝试降低筛选门槛</p>
                  </div>
                )}
              </div>
            )}

            {!result && !loading && !error && (
              <p className="mt-3 text-xs text-muted-text">
                点击「运行选股」扫描全A股市场，实时筛选符合三倍量战法的股票。
                建议收盘后运行，盘中数据可能存在延迟。
              </p>
            )}
          </SectionCard>

          <SectionCard title="策略概述" subtitle="TRIPLE VOLUME BREAKOUT">
            <p className="text-sm text-secondary-text leading-relaxed">
              三倍量战法是基于成交量放量突破的短线选股策略。核心逻辑是识别当日成交量放大至5日均量3倍以上、
              同时满足涨幅、换手、位置、均线等多维度条件的强势突破个股。该策略无未来函数，盘后选股，次日低吸，
              实战胜率较高。
            </p>
            <div className="mt-4 flex flex-wrap gap-2">
              {['无未来函数', '盘后选股', '次日低吸', '严格止损'].map((tag) => (
                <Badge key={tag} variant="info" size="sm">{tag}</Badge>
              ))}
            </div>
          </SectionCard>

          <SectionCard title="过滤条件" subtitle="BUILT-IN FILTERS">
            <ul className="space-y-1">
              {FILTER_CONDITIONS.map((condition, i) => (
                <RuleItem key={i} index={i + 1} text={condition} />
              ))}
            </ul>
          </SectionCard>

          <SectionCard title="实战规则" subtitle="USAGE RULES">
            <ul className="space-y-1">
              {USAGE_RULES.map((rule, i) => (
                <RuleItem key={i} index={i + 1} text={rule} />
              ))}
            </ul>
            <div className="mt-4 rounded-xl border border-warning/20 bg-warning/5 px-4 py-3">
              <p className="text-xs text-warning leading-relaxed">
                ⚠️ 风险提示：该策略仅供学习研究，不构成投资建议。股市有风险，投资需谨慎。
                三倍量启动往往是主力资金异动信号，但需结合大盘环境和个股基本面综合判断。
              </p>
            </div>
          </SectionCard>

          <div className="space-y-3">
            <div className="flex items-center gap-2">
              <CodeIcon className="h-4 w-4 text-cyan" />
              <h2 className="text-sm font-semibold text-foreground">选股公式</h2>
            </div>

            <CodeBlock title="通达信主选股公式" lang="通达信" code={TONG_DA_XIN_FORMULA} />

            <Collapsible title="通达信副图指标（看盘专用）">
              <CodeBlock title="三倍量副图" lang="通达信" code={TONG_DA_XIN_SUB} />
            </Collapsible>

            <Collapsible title="同花顺通用版本">
              <CodeBlock title="同花顺选股公式" lang="同花顺" code={TONG_HUA_SHUN_FORMULA} />
            </Collapsible>

            <Collapsible title="进阶精简版（只抓最强突破）">
              <div className="space-y-3">
                <p className="text-xs text-secondary-text">
                  精简版仅保留最核心条件：三倍量 + 突破20日新高 + 涨幅6%以上，适合快速扫描最强突破标的。
                </p>
                <CodeBlock title="最强三倍量突破" lang="通达信" code={ADVANCED_FORMULA} />
              </div>
            </Collapsible>
          </div>
        </div>
        ) : activeTab === 'oversold-bounce' ? (
          <div className="mx-auto max-w-4xl space-y-5">
          <SectionCard title="运行选股" subtitle="OVERSOLD BOUNCE SCREENING">
            <div className="flex flex-wrap items-end gap-3">
              <div className="flex flex-col gap-1">
                <label className="text-xs text-muted-text">回看天数</label>
                <input
                  type="number"
                  min={3}
                  max={10}
                  step={1}
                  value={oversoldDays}
                  onChange={(e) => setOversoldDays(parseInt(e.target.value) || 5)}
                  className="input-surface input-focus-glow h-9 w-20 rounded-xl border bg-transparent px-3 text-sm text-center tabular-nums"
                />
              </div>
              <div className="flex flex-col gap-1">
                <label className="text-xs text-muted-text">最低跌幅(%)</label>
                <input
                  type="number"
                  min={10}
                  max={40}
                  step={5}
                  value={oversoldMinDropPct}
                  onChange={(e) => setOversoldMinDropPct(parseFloat(e.target.value) || 20)}
                  className="input-surface input-focus-glow h-9 w-20 rounded-xl border bg-transparent px-3 text-sm text-center tabular-nums"
                />
              </div>
              <div className="flex flex-col gap-1">
                <label className="text-xs text-muted-text">5日线乖离(%)</label>
                <input
                  type="number"
                  min={-15}
                  max={-5}
                  step={1}
                  value={oversoldMaxBiasPct}
                  onChange={(e) => setOversoldMaxBiasPct(parseFloat(e.target.value) || -8)}
                  className="input-surface input-focus-glow h-9 w-20 rounded-xl border bg-transparent px-3 text-sm text-center tabular-nums"
                />
              </div>
              <button
                type="button"
                onClick={handleOversoldRun}
                disabled={oversoldLoading}
                className="btn-primary flex items-center gap-2 h-9 px-4 text-sm"
              >
                {oversoldLoading ? (
                  <>
                    <div className="h-4 w-4 animate-spin rounded-full border-2 border-white/20 border-t-white" />
                    筛选中...
                  </>
                ) : (
                  <>
                    <Play className="h-4 w-4" />
                    运行选股
                  </>
                )}
              </button>
            </div>

            {oversoldError && (
              <div className="mt-3 rounded-xl border border-danger/30 bg-danger/8 px-3 py-2">
                <p className="text-xs text-danger">{oversoldError.message || '选股失败，请稍后重试'}</p>
              </div>
            )}

            {oversoldResult && (
              <div className="mt-4 space-y-3">
                <div className="flex flex-wrap items-center gap-3 text-xs text-secondary-text">
                  <span>大盘状态: <strong className={oversoldResult.marketPanic ? 'text-danger' : 'text-success'}>{oversoldResult.marketPanic ? '恐慌' : '正常'}</strong></span>
                  <span className="text-border/60">→</span>
                  <span>扫描 <strong className="text-foreground">{oversoldResult.totalScanned}</strong> 只</span>
                  <span className="text-border/60">→</span>
                  <span>最终入选 <strong className="text-cyan">{oversoldResult.afterDetailed}</strong> 只</span>
                  <span className="text-muted-text ml-auto">耗时 {oversoldResult.elapsedSeconds}s</span>
                </div>

                {oversoldResult.candidates && oversoldResult.candidates.length > 0 ? (
                  <div className="rounded-2xl border border-border/40 overflow-hidden">
                    <div className="overflow-x-auto">
                      <table className="w-full text-sm">
                        <thead className="bg-surface/50 border-b border-border/40">
                          <tr className="text-left">
                            <th className="px-3 py-2.5 text-xs font-medium text-muted-text">股票</th>
                            <th className="px-3 py-2.5 text-xs font-medium text-muted-text">现价</th>
                            <th className="px-3 py-2.5 text-xs font-medium text-muted-text">今日跌幅</th>
                            <th className="px-3 py-2.5 text-xs font-medium text-muted-text">N日跌幅</th>
                            <th className="px-3 py-2.5 text-xs font-medium text-muted-text">5日线乖离</th>
                            <th className="px-3 py-2.5 text-xs font-medium text-muted-text">换手</th>
                            <th className="px-3 py-2.5 text-xs font-medium text-muted-text text-center">评分</th>
                          </tr>
                        </thead>
                        <tbody>
                          {oversoldResult.candidates.map((c: OversoldCandidate) => (
                            <tr key={c.code} className="border-b border-border/30 hover:bg-hover/20 transition-colors">
                              <td className="px-3 py-2.5">
                                <div className="flex flex-col">
                                  <span className="text-sm font-medium text-foreground">{c.code}</span>
                                  <span className="text-xs text-muted-text">{c.name}</span>
                                </div>
                              </td>
                              <td className="px-3 py-2.5 text-sm tabular-nums text-foreground">{c.price.toFixed(2)}</td>
                              <td className="px-3 py-2.5">
                                <span className="text-sm tabular-nums font-medium text-danger">{c.todayDropPct.toFixed(2)}%</span>
                              </td>
                              <td className="px-3 py-2.5">
                                <span className="text-sm tabular-nums font-medium text-danger">{c.nDayDropPct.toFixed(2)}%</span>
                              </td>
                              <td className="px-3 py-2.5">
                                <span className={`text-sm tabular-nums font-medium ${c.biasFromMa5 < -5 ? 'text-danger' : 'text-foreground'}`}>{c.biasFromMa5.toFixed(2)}%</span>
                              </td>
                              <td className="px-3 py-2.5 text-sm tabular-nums text-foreground">{c.turnoverRate.toFixed(1)}%</td>
                              <td className="px-3 py-2.5 text-center">
                                <Badge variant={c.score >= 5 ? 'success' : c.score >= 3 ? 'info' : 'warning'} size="sm" glow={c.score >= 5}>
                                  {c.score}/6
                                </Badge>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                ) : (
                  <div className="rounded-2xl border border-dashed border-border/60 px-4 py-8 text-center">
                    <p className="text-sm text-muted-text">未筛选出符合条件的股票</p>
                    <p className="mt-1 text-xs text-secondary-text">可尝试放宽筛选门槛</p>
                  </div>
                )}
              </div>
            )}

            {!oversoldResult && !oversoldLoading && !oversoldError && (
              <p className="mt-3 text-xs text-muted-text">
                超跌反弹战法：当大盘恐慌（连续下跌+大阴线+远离5日线）与板块超跌共振时出击。
                选股条件：近期跌幅大、远离5日线、换手率放大（恐慌盘）。
              </p>
            )}
          </SectionCard>

          <SectionCard title="策略概述" subtitle="OVERSOLD BOUNCE STRATEGY">
            <p className="text-sm text-secondary-text leading-relaxed">
              超跌反弹战法基于恐慌情绪的极端释放后的均值回归。核心逻辑是识别大盘恐慌与板块超跌的共振时刻，
              在恐慌盘杀出时低吸被错杀的优质标的。该战法的本质是"别人恐惧时我贪婪"的量化实现。
            </p>
            <div className="mt-4 flex flex-wrap gap-2">
              {['恐慌择时', '乖离率', '放量杀跌', '快进快出'].map((tag) => (
                <Badge key={tag} variant="info" size="sm">{tag}</Badge>
              ))}
            </div>
          </SectionCard>

          <SectionCard title="出击条件" subtitle="ENTRY CONDITIONS">
            <ul className="space-y-1">
              {[
                '大盘：连续下跌3天以上，当日大阴线（跌幅>1.5%），指数远离5日线（乖离率<-2%）',
                '板块：超跌板块连续下跌后，再次出现集体性大幅杀跌',
                '个股：N日累计跌幅>20%，当日继续下跌，换手率放大（恐慌盘涌出）',
                '量价：放量杀跌后缩量企稳，或出现长下影线（买方试探）',
              ].map((rule, i) => (
                <RuleItem key={i} index={i + 1} text={rule} />
              ))}
            </ul>
          </SectionCard>

          <SectionCard title="实战规则" subtitle="USAGE RULES">
            <ul className="space-y-1">
              {[
                '有赚钱效应时做热点为主，有恐慌效应时做超跌为主',
                '外围通常只影响开盘，可利用外围大跌做反向操作（低开高走）',
                '超跌反弹是短线行为，目标位5%-15%，到位即走',
                '止损：跌破前低或反弹后再次放量下跌立即离场',
                '仓位：单只不超过总资金20%，分批建仓',
              ].map((rule, i) => (
                <RuleItem key={i} index={i + 1} text={rule} />
              ))}
            </ul>
            <div className="mt-4 rounded-xl border border-warning/20 bg-warning/5 px-4 py-3">
              <p className="text-xs text-warning leading-relaxed">
                ⚠️ 风险提示：超跌反弹是高风险操作，本质是接飞刀。只有在大盘恐慌+板块超跌共振时才可出击。
                如果大盘持续阴跌（非恐慌），则不宜使用此战法。该策略仅供学习研究，不构成投资建议。
              </p>
            </div>
          </SectionCard>

          <SectionCard title="市场状态判断" subtitle="MARKET STATE JUDGMENT">
            <p className="text-xs text-muted-text mb-3">
              根据赚钱效应和恐慌效应决定策略：有赚钱效应做热点，有恐慌效应做超跌。
            </p>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="bg-surface/50 border-b border-border/40">
                  <tr className="text-left">
                    <th className="px-3 py-2.5 text-xs font-medium text-muted-text">市场状态</th>
                    <th className="px-3 py-2.5 text-xs font-medium text-muted-text">特征</th>
                    <th className="px-3 py-2.5 text-xs font-medium text-muted-text">策略</th>
                  </tr>
                </thead>
                <tbody>
                  {[
                    ['赚钱效应强', '涨停数多、连板高度高、板块普涨', '做热点板块龙头'],
                    ['恐慌效应强', '跌停数多、板块普跌、放量杀跌', '做超跌反弹'],
                    ['震荡市', '涨跌互现、无明确方向', '轻仓观望或做T'],
                  ].map(([state, feature, strategy], i) => (
                    <tr key={i} className="border-b border-border/30 hover:bg-hover/10">
                      <td className="px-3 py-2.5 font-medium text-foreground">{state}</td>
                      <td className="px-3 py-2.5 text-secondary-text">{feature}</td>
                      <td className="px-3 py-2.5">
                        <Badge variant={i === 1 ? 'danger' : i === 0 ? 'success' : 'info'} size="sm">{strategy}</Badge>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </SectionCard>

          </div>
        ) : activeTab === 'industry-research' ? (
          <div className="mx-auto max-w-4xl space-y-5">
          <SectionCard title="产业链研究选股" subtitle="INDUSTRY RESEARCH SCREENING">
            <p className="text-xs text-muted-text mb-3">
              输入行业名称，AI将逆向拆解产业链BOM，锁定"扩产周期长、技术门槛高、不可替代"的瓶颈环节，筛选中小盘隐形冠军。
            </p>
            <div className="flex flex-wrap items-end gap-3">
              <div className="flex flex-col gap-1 min-w-[160px]">
                <label className="text-xs text-muted-text">行业名称</label>
                <input
                  type="text"
                  placeholder="如：半导体、新能源、医药"
                  value={researchSector}
                  onChange={(e) => setResearchSector(e.target.value)}
                  className="input-surface input-focus-glow h-9 w-full rounded-xl border bg-transparent px-3 text-sm"
                />
              </div>
              <div className="flex flex-col gap-1">
                <label className="text-xs text-muted-text">最低市值(亿)</label>
                <input
                  type="number"
                  min={10}
                  max={100}
                  step={10}
                  value={researchMinMarketCap}
                  onChange={(e) => setResearchMinMarketCap(parseFloat(e.target.value) || 30)}
                  className="input-surface input-focus-glow h-9 w-20 rounded-xl border bg-transparent px-3 text-sm text-center tabular-nums"
                />
              </div>
              <div className="flex flex-col gap-1">
                <label className="text-xs text-muted-text">最高市值(亿)</label>
                <input
                  type="number"
                  min={100}
                  max={1000}
                  step={50}
                  value={researchMaxMarketCap}
                  onChange={(e) => setResearchMaxMarketCap(parseFloat(e.target.value) || 500)}
                  className="input-surface input-focus-glow h-9 w-20 rounded-xl border bg-transparent px-3 text-sm text-center tabular-nums"
                />
              </div>
              <div className="flex flex-col gap-1">
                <label className="text-xs text-muted-text">最低评分</label>
                <input
                  type="number"
                  min={30}
                  max={90}
                  step={5}
                  value={researchMinScore}
                  onChange={(e) => setResearchMinScore(parseFloat(e.target.value) || 60)}
                  className="input-surface input-focus-glow h-9 w-20 rounded-xl border bg-transparent px-3 text-sm text-center tabular-nums"
                />
              </div>
              <button
                type="button"
                onClick={handleResearchRun}
                disabled={researchLoading || !researchSector.trim()}
                className="btn-primary flex items-center gap-2 h-9 px-4 text-sm"
              >
                {researchLoading ? (
                  <>
                    <div className="h-4 w-4 animate-spin rounded-full border-2 border-white/20 border-t-white" />
                    研究中...
                  </>
                ) : (
                  <>
                    <Play className="h-4 w-4" />
                    开始研究
                  </>
                )}
              </button>
            </div>

            {researchError && (
              <div className="mt-3 rounded-xl border border-danger/30 bg-danger/8 px-3 py-2">
                <p className="text-xs text-danger">{researchError.message || '研究失败，请稍后重试'}</p>
              </div>
            )}

            {researchResult && (
              <div className="mt-4 space-y-4">
                {/* 瓶颈分析 */}
                {researchResult.bottleneck && (
                  <div className="rounded-xl border border-cyan/20 bg-cyan/[0.04] p-4">
                    <div className="flex items-center gap-2 mb-3">
                      <div className="h-2 w-2 rounded-full bg-cyan" />
                      <h3 className="text-sm font-semibold text-foreground">瓶颈环节识别</h3>
                    </div>
                    <p className="text-sm text-secondary-text leading-relaxed">{researchResult.bottleneck.bottleneckDescription}</p>
                    <div className="mt-3 grid grid-cols-1 gap-2 sm:grid-cols-2">
                      <div className="text-xs">
                        <span className="text-muted-text">瓶颈原因：</span>
                        <span className="text-foreground">{researchResult.bottleneck.bottleneckReason}</span>
                      </div>
                      <div className="text-xs">
                        <span className="text-muted-text">扩产周期：</span>
                        <span className="text-foreground">{researchResult.bottleneck.expansionCycle}</span>
                      </div>
                      <div className="text-xs">
                        <span className="text-muted-text">替代风险：</span>
                        <span className="text-foreground">{researchResult.bottleneck.substitutionRisk}</span>
                      </div>
                      <div className="text-xs">
                        <span className="text-muted-text">关键技术：</span>
                        <span className="text-foreground">{researchResult.bottleneck.keyTechnologies.join('、')}</span>
                      </div>
                    </div>
                  </div>
                )}

                {/* 统计概览 */}
                <div className="flex flex-wrap items-center gap-3 text-xs text-secondary-text">
                  <span>行业: <strong className="text-foreground">{researchResult.sector}</strong></span>
                  <span className="text-border/60">→</span>
                  <span>筛选 <strong className="text-foreground">{researchResult.totalScanned}</strong> 只</span>
                  <span className="text-border/60">→</span>
                  <span>市值过滤 <strong className="text-foreground">{researchResult.afterMarketCap}</strong> 只</span>
                  <span className="text-border/60">→</span>
                  <span>最终入选 <strong className="text-cyan">{researchResult.afterFinancial}</strong> 只</span>
                  <span className="text-muted-text ml-auto">耗时 {researchResult.elapsedSeconds}s</span>
                </div>

                {/* 候选标的 */}
                {researchResult.candidates.length > 0 ? (
                  <div className="space-y-4">
                    {researchResult.candidates.map((c) => (
                      <div key={c.code} className="rounded-xl border border-border/40 bg-surface/30 p-4">
                        {/* 标题行 */}
                        <div className="flex items-center justify-between mb-3">
                          <div className="flex items-center gap-3">
                            <div>
                              <div className="flex items-center gap-2">
                                <span className="text-sm font-semibold text-foreground">{c.name}</span>
                                <span className="text-xs text-muted-text">{c.code}</span>
                              </div>
                              <div className="text-xs text-secondary-text mt-0.5">{c.industry} · {c.subSector}</div>
                            </div>
                          </div>
                          <div className="flex items-center gap-2">
                            <span className="text-xs text-muted-text">市值 {c.marketCapYi}亿</span>
                            <Badge variant={c.compositeScore >= 80 ? 'success' : c.compositeScore >= 60 ? 'info' : 'warning'} size="sm" glow={c.compositeScore >= 80}>
                              {c.compositeScore}分
                            </Badge>
                          </div>
                        </div>

                        {/* 财务指标 */}
                        <div className="grid grid-cols-2 gap-2 sm:grid-cols-4 mb-3">
                          <div className="text-xs">
                            <span className="text-muted-text">毛利率</span>
                            <div className="font-medium text-foreground">{c.grossMargin}%</div>
                            <div className={c.grossMarginChange > 0 ? 'text-success' : 'text-secondary-text'}>
                              {c.grossMarginChange > 0 ? '+' : ''}{c.grossMarginChange}pp
                            </div>
                          </div>
                          <div className="text-xs">
                            <span className="text-muted-text">CapEx增速</span>
                            <div className={`font-medium ${c.capexGrowth > 30 ? 'text-success' : 'text-foreground'}`}>
                              {c.capexGrowth > 0 ? '+' : ''}{c.capexGrowth}%
                            </div>
                          </div>
                          <div className="text-xs">
                            <span className="text-muted-text">营收同比</span>
                            <div className={`font-medium ${c.revenueYoy > 20 ? 'text-success' : 'text-foreground'}`}>
                              {c.revenueYoy > 0 ? '+' : ''}{c.revenueYoy}%
                            </div>
                          </div>
                          <div className="text-xs">
                            <span className="text-muted-text">利润同比</span>
                            <div className={`font-medium ${c.profitYoy > 30 ? 'text-success' : 'text-foreground'}`}>
                              {c.profitYoy > 0 ? '+' : ''}{c.profitYoy}%
                            </div>
                          </div>
                        </div>

                        {/* 瓶颈匹配度 */}
                        <div className="text-xs mb-2">
                          <span className="text-muted-text">瓶颈匹配：</span>
                          <span className="text-secondary-text">{c.bottleneckMatch}</span>
                        </div>

                        {/* 机构覆盖 */}
                        <div className="text-xs mb-2">
                          <span className="text-muted-text">机构覆盖：</span>
                          <span className="text-secondary-text">{c.institutionalCoverage}</span>
                        </div>

                        {/* 红队报告 */}
                        <div className="rounded-lg border border-danger/20 bg-danger/5 p-3 mb-3">
                          <div className="flex items-center gap-1.5 mb-2">
                            <div className="h-1.5 w-1.5 rounded-full bg-danger" />
                            <span className="text-xs font-medium text-danger">AI红队测试报告</span>
                          </div>
                          <p className="text-xs text-secondary-text leading-relaxed whitespace-pre-wrap">{c.redTeamReport}</p>
                        </div>

                        {/* 熔断机制 */}
                        {c.circuitBreakers.length > 0 && (
                          <div className="rounded-lg border border-warning/20 bg-warning/5 p-3">
                            <div className="flex items-center gap-1.5 mb-2">
                              <div className="h-1.5 w-1.5 rounded-full bg-warning" />
                              <span className="text-xs font-medium text-warning">熔断机制（未来6个月）</span>
                            </div>
                            <div className="space-y-1.5">
                              {c.circuitBreakers.map((cb, i) => (
                                <div key={i} className="flex items-start gap-2 text-xs">
                                  <span className="text-muted-text shrink-0">{cb.deadline}</span>
                                  <span className="text-foreground">{cb.milestone}</span>
                                  <span className="text-danger shrink-0">→ {cb.consequence}</span>
                                </div>
                              ))}
                            </div>
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="rounded-2xl border border-dashed border-border/60 px-4 py-8 text-center">
                    <p className="text-sm text-muted-text">未筛选出符合条件的标的</p>
                    <p className="mt-1 text-xs text-secondary-text">可尝试放宽市值范围或降低评分门槛</p>
                  </div>
                )}
              </div>
            )}

            {!researchResult && !researchLoading && !researchError && (
              <div className="mt-4 space-y-3">
                <div className="rounded-xl border border-border/40 bg-surface/30 p-4">
                  <h3 className="text-sm font-semibold text-foreground mb-2">方法论解析</h3>
                  <div className="space-y-2 text-xs text-secondary-text">
                    <p><strong className="text-foreground">逆向拆解BOM</strong> — 从终端产品逆向拆解到原材料/设备，识别"扩产慢、门槛高、不可替代"的瓶颈环节</p>
                    <p><strong className="text-foreground">锁定非对称标的</strong> — 在瓶颈环节中找30-500亿市值、机构低覆盖的隐形冠军</p>
                    <p><strong className="text-foreground">穿透财务拐点</strong> — 毛利率因供需失衡出现爆发性拐点、CapEx秘密爬坡</p>
                    <p><strong className="text-foreground">AI红队测试</strong> — 从技术替代、客户自研、供应链断裂三个维度做空验证</p>
                    <p><strong className="text-foreground">熔断机制</strong> — 未来6个月关键里程碑，未达标强制清仓</p>
                  </div>
                </div>
                <p className="text-xs text-muted-text">
                  输入行业名称（如"半导体"、"新能源"、"医药"），AI将自动完成产业链分析和标的筛选。
                </p>
              </div>
            )}
          </SectionCard>

          </div>
        ) : activeTab === 'multi-cycle' ? (
          <div className="mx-auto max-w-4xl space-y-5">

            <SectionCard title="核心理念" subtitle="CORE PHILOSOPHY">
              <p className="text-sm text-secondary-text leading-relaxed">
                周期共振买卖点战法不是去"猜底"或"猜顶"，而是<strong className="text-foreground">等待市场在不同时间周期上同时发出确认信号</strong>，在共振点入场。
                核心原则：<strong className="text-cyan">大周期定方向，中周期找结构，小周期找入场。</strong>
                你不是在预测转折，而是在"跟随"趋势的延续或衰竭。
              </p>
            </SectionCard>

            <SectionCard title="三级周期框架" subtitle="MULTI-CYCLE FRAMEWORK">
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="bg-surface/50 border-b border-border/40">
                    <tr className="text-left">
                      <th className="px-3 py-2.5 text-xs font-medium text-muted-text">周期</th>
                      <th className="px-3 py-2.5 text-xs font-medium text-muted-text">角色</th>
                      <th className="px-3 py-2.5 text-xs font-medium text-muted-text">看什么</th>
                      <th className="px-3 py-2.5 text-xs font-medium text-muted-text">举例（日线操作）</th>
                    </tr>
                  </thead>
                  <tbody>
                    {[
                      ['大周期 (周线/月线)', '定方向', '趋势方向、关键支撑阻力区', '周线 MA20 ↑ → 只做多'],
                      ['中周期 (日线)', '找结构', '回调 / 反弹结构是否完成', '日线回踩 MA20 不破 → 结构完好'],
                      ['小周期 (60m/30m)', '找入场', '止跌 / 止涨确认信号', '60m 放量阳线 + 不再创新低'],
                    ].map(([cycle, role, check, example], i) => (
                      <tr key={i} className="border-b border-border/30 hover:bg-hover/10">
                        <td className="px-3 py-2.5 font-medium text-foreground">{cycle}</td>
                        <td className="px-3 py-2.5 text-cyan">{role}</td>
                        <td className="px-3 py-2.5 text-secondary-text leading-relaxed">{check}</td>
                        <td className="px-3 py-2.5 text-xs text-muted-text">{example}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <div className="mt-4 rounded-xl bg-surface/40 border border-border/40 p-4">
                <p className="text-xs text-secondary-text leading-relaxed font-mono whitespace-pre-wrap">
                  {'大周期（周线）：趋势向上 ✓\n    ↓\n中周期（日线）：回调到支撑区，缩量\n    ↓\n小周期（60m）：放量阳线 + 不再创新低\n    ↓\n入场 ← 止损设在回调低点下方'}
                </p>
              </div>
            </SectionCard>

            <SectionCard title="成交量确认" subtitle="VOLUME CONFIRMATION">
              <p className="text-xs text-muted-text mb-3">
                价格可以骗人，成交量很难骗——量价关系是买卖点最重要的辅助判断。
              </p>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="bg-surface/50 border-b border-border/40">
                    <tr className="text-left">
                      <th className="px-3 py-2.5 text-xs font-medium text-muted-text">场景</th>
                      <th className="px-3 py-2.5 text-xs font-medium text-muted-text">量价</th>
                      <th className="px-3 py-2.5 text-xs font-medium text-muted-text">含义</th>
                      <th className="px-3 py-2.5 text-xs font-medium text-muted-text">操作</th>
                    </tr>
                  </thead>
                  <tbody>
                    {[
                      ['上涨放量', '价↑ 量↑', '健康，资金在进', '持有/加仓'],
                      ['上涨缩量', '价↑ 量↓', '衰竭，追高危险', '减仓/观望'],
                      ['下跌缩量', '价↓ 量↓', '正常回调，抛压不大', '等待止跌信号'],
                      ['下跌放量', '价↓ 量↑', '恐慌出货，勿接飞刀', '远离'],
                      ['回调缩量后放量阳', '缩→放', '⭐ 最佳买点信号', '买入'],
                    ].map(([scene, volume, meaning, action], i) => (
                      <tr key={i} className="border-b border-border/30 hover:bg-hover/10">
                        <td className="px-3 py-2.5 font-medium text-foreground">{scene}</td>
                        <td className="px-3 py-2.5 text-cyan tabular-nums">{volume}</td>
                        <td className="px-3 py-2.5 text-secondary-text">{meaning}</td>
                        <td className="px-3 py-2.5">
                          <Badge variant={action.includes('买') ? 'success' : action.includes('卖') || action.includes('离') ? 'danger' : 'info'} size="sm">{action}</Badge>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </SectionCard>

            <SectionCard title="关键位置 + 价格行为" subtitle="PRICE ACTION AT KEY LEVELS">
              <ul className="space-y-1">
                {[
                  '前高 / 前低：突破前高回踩不破 → 买点；跌破前低反弹无力 → 卖点',
                  '均线支撑：MA20 / MA60 是机构常用的参考线，缩量回踩是低吸机会',
                  '放量 K 线的高低点：大阳线底部、大阴线顶部是“聪明钱的痕迹”',
                  'Pin Bar（长影线反转）：支撑区出现长下影线 → 买方进场信号',
                  '乖离率动态使用：强势趋势中放宽（5%→8%），震荡市中收紧（3%→5%）',
                ].map((text, i) => (
                  <RuleItem key={i} index={i + 1} text={text} />
                ))}
              </ul>
            </SectionCard>

            <SectionCard title="大盘 + 板块环境确认" subtitle="MARKET & SECTOR CONTEXT">
              <p className="text-sm text-secondary-text leading-relaxed mb-3">
                个股买点再好，如果板块和大盘都在跌，成功率大打折扣。最优买点 =
                大盘 + 板块 + 个股三者共振。
              </p>
              <ul className="space-y-1">
                {[
                  '大盘处于上升趋势 → 个股买点有效性 ↑',
                  '板块领涨 / 主线板块 → 个股买点有效性 ↑',
                  '北向资金 / 主力资金持续流入该板块 → 买点可信度 ↑',
                  '筹码集中度上升 → 支撑位买入更可靠；集中度下降 → 卖点提前',
                ].map((text, i) => (
                  <RuleItem key={i} index={i + 1} text={text} />
                ))}
              </ul>
            </SectionCard>

            <SectionCard title="买入确认清单" subtitle="BUY CHECKLIST">
              <p className="text-xs text-muted-text mb-3">
                以下 6 条全部满足 = 高置信度买点。用清单代替直觉，用规则代替情绪。
              </p>
              <ul className="space-y-1">
                {[
                  '大周期趋势向上（周线 MA20 ↑）',
                  '中周期出现回调 / 整理结构',
                  '小周期出现止跌信号（放量阳线 / Pin Bar / 不再创新低）',
                  '成交量缩量后放量',
                  '乖离率在合理范围（不追高）',
                  '板块和大盘不拖后腿',
                ].map((text, i) => (
                  <RuleItem key={i} index={i + 1} text={text} />
                ))}
              </ul>
            </SectionCard>

            <SectionCard title="卖出确认清单" subtitle="SELL CHECKLIST">
              <p className="text-xs text-muted-text mb-3">
                触发任意 2 条 = 考虑卖出。买在确认处，卖在纪律处。
              </p>
              <ul className="space-y-1">
                {[
                  '大周期趋势转弱（MA 死叉）',
                  '反弹到压力区缩量无力',
                  '小周期出现放量阴线破位',
                  '止损触发（纪律性离场）',
                  '目标价位到达（有计划地止盈）',
                ].map((text, i) => (
                  <RuleItem key={i} index={i + 1} text={text} />
                ))}
              </ul>
              <div className="mt-4 rounded-xl border border-warning/20 bg-warning/5 px-4 py-3">
                <p className="text-xs text-warning leading-relaxed">
                  ⚠️ 核心心法：本质上，买点是"等"出来的，不是"找"出来的。
                  90% 的时间在等待共振信号出现，10% 的时间执行。买在确认处，卖在纪律处，其余时间——等。
                </p>
              </div>
            </SectionCard>

          </div>
        ) : (
          <div className="mx-auto max-w-4xl space-y-5">

            <SectionCard title="核心理念" subtitle="CORE PHILOSOPHY">
              <p className="text-sm text-secondary-text leading-relaxed">
                分时做T格子战法不是去"猜涨跌"，而是<strong className="text-foreground">利用分时图红黄线的乖离修复规律</strong>，
                在偏离均价线时做高抛低吸。核心原则：
                <strong className="text-cyan">红黄三格内不动，过三格出手，五格冲高观望，回落均线接回。</strong>
              </p>
              <div className="mt-4 flex flex-wrap gap-2">
                {['日内T+0', '乖离修复', '格子量化', '严格纪律'].map((tag) => (
                  <Badge key={tag} variant="info" size="sm">{tag}</Badge>
                ))}
              </div>
            </SectionCard>

            <SectionCard title="格子定义" subtitle="GRID DEFINITION">
              <p className="text-xs text-muted-text mb-3">
                0轴到涨停板分为10个格子。手机端无法调格子时，直接看涨幅数字代替。
              </p>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="bg-surface/50 border-b border-border/40">
                    <tr className="text-left">
                      <th className="px-3 py-2.5 text-xs font-medium text-muted-text">格子</th>
                      <th className="px-3 py-2.5 text-xs font-medium text-muted-text">涨幅</th>
                      <th className="px-3 py-2.5 text-xs font-medium text-muted-text">含义</th>
                    </tr>
                  </thead>
                  <tbody>
                    {[
                      ['1 格', '涨 1%', '小区间震荡'],
                      ['3 格', '涨 3%', '红黄线分水岭，过此线考虑操作'],
                      ['5 格', '涨 5%', 'T+0 黄金信号区'],
                      ['10 格', '涨 10%', '涨停'],
                    ].map(([grid, pct, meaning], i) => (
                      <tr key={i} className="border-b border-border/30 hover:bg-hover/10">
                        <td className="px-3 py-2.5 font-medium text-foreground">{grid}</td>
                        <td className="px-3 py-2.5 text-cyan tabular-nums">{pct}</td>
                        <td className="px-3 py-2.5 text-secondary-text">{meaning}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </SectionCard>

            <SectionCard title="四大铁律" subtitle="FOUR CORE RULES">
              <ul className="space-y-1">
                {[
                  '规则1 — 红黄三格不动弹，横盘乱动准完蛋：黄红线距离 ≤ 3 格时，属于小区间震荡，差价不够手续费，不动等信号',
                  '规则2 — 红黄过三格出手，乖离修复肉就有：红线向上/下甩开黄线超 3 格，且离 0 轴超 5 格 → 黄金做T信号。涨超 5 格卖出，跌超 5 格买入',
                  '规则3 — 5格冲高先观望，小心涨停吃大亏：红线离 0 轴超 5 格且向上冲 → 可能奔涨停。6 格以上不做T，宁可看着不乱动',
                  '规则4 — 回落均线是买点，纪律执行成本减：高抛或低吸后，等红线回到黄线附近再做反向操作，这是不被反杀的关键节奏',
                ].map((text, i) => (
                  <RuleItem key={i} index={i + 1} text={text} />
                ))}
              </ul>
            </SectionCard>

            <SectionCard title="实战操作流程" subtitle="OPERATION FLOW">
              <div className="rounded-xl bg-surface/40 border border-border/40 p-4">
                <p className="text-xs text-secondary-text leading-relaxed font-mono whitespace-pre-wrap">
                  {'步骤1：打开分时图，看红黄线位置\n    ↓\n步骤2：计算红黄线的格子差（涨幅差值）\n    ↓\n步骤3：差值 ≤ 3 格？ → 不动，等信号\n    差值 > 3 格？ → 查看离 0 轴距离\n    ↓\n步骤4：离 0 轴 ≥ 5 格？ → 做T黄金信号\n    离 0 轴 ≥ 6 格？ → 不做T，防涨停/跌停\n    ↓\n步骤5：执行高抛或低吸\n    等待红线回到黄线附近 → 反向操作'}
                </p>
              </div>
            </SectionCard>

            <SectionCard title="量价配合确认" subtitle="VOLUME CONFIRMATION">
              <p className="text-xs text-muted-text mb-3">
                分时做 T 不能只看格子，还要看分时成交量的配合，否则容易被假突破骗线。
              </p>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="bg-surface/50 border-b border-border/40">
                    <tr className="text-left">
                      <th className="px-3 py-2.5 text-xs font-medium text-muted-text">分时特征</th>
                      <th className="px-3 py-2.5 text-xs font-medium text-muted-text">量能</th>
                      <th className="px-3 py-2.5 text-xs font-medium text-muted-text">操作</th>
                    </tr>
                  </thead>
                  <tbody>
                    {[
                      ['上涨放量 + 远离黄线', '价↑ 量↑', '高抛信号可信 ✓'],
                      ['上涨缩量 + 远离黄线', '价↑ 量↓', '假突破，不急于高抛'],
                      ['下跌放量 + 远离黄线', '价↓ 量↑', '恐慌盘，等缩量止跌再低吸'],
                      ['下跌缩量 + 远离黄线', '价↓ 量↓', '低吸信号可信 ✓'],
                      ['回踩黄线放量', '回踩 量↑', '支撑有效，接回仓位'],
                    ].map(([scene, volume, action], i) => (
                      <tr key={i} className="border-b border-border/30 hover:bg-hover/10">
                        <td className="px-3 py-2.5 font-medium text-foreground">{scene}</td>
                        <td className="px-3 py-2.5 text-cyan">{volume}</td>
                        <td className="px-3 py-2.5 text-secondary-text">{action}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </SectionCard>

            <SectionCard title="适用条件 & 禁忌" subtitle="CONDITIONS & TABOOS">
              <ul className="space-y-1">
                {[
                  '当日振幅 ≥ 3% — 振幅太小做 T 无法覆盖手续费',
                  '标的有足够流动性 — 日均成交额 > 1 亿',
                  '不适用场景：开盘 30 分钟内（价格不稳定）、尾盘 15 分钟（隔夜风险）',
                  '趋势股优于震荡股 — 单边上涨/下跌趋势中做 T 容易踏空或深套',
                  '底仓 + T 仓严格分离 — 做 T 部分当日必须平仓，不隔夜',
                ].map((text, i) => (
                  <RuleItem key={i} index={i + 1} text={text} />
                ))}
              </ul>
              <div className="mt-4 rounded-xl border border-warning/20 bg-warning/5 px-4 py-3">
                <p className="text-xs text-warning leading-relaxed">
                  ⚠️ 风险提示：做 T 需要极高的盘感和纪律性。新手建议先用模拟盘练习，熟练后再实盘。
                  做 T 的本质是降低持仓成本，不是增加仓位。严禁把做 T 变成追涨杀跌。
                  如果在AI分析中使用此战法，请在 `buy_reason` 或 `sell_reason` 中注明"分时做T格子战法"及具体规则编号。
                </p>
              </div>
            </SectionCard>

          </div>
        )}
      </main>
    </div>
  );
};

export default TacticPage;
