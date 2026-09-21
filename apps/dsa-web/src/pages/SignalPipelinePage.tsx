import type React from 'react';
import { useCallback, useEffect, useRef, useState } from 'react';
import { Activity, Calendar, CheckCircle2, Download, Info, Loader2, Play, XCircle } from 'lucide-react';
import { Card, Button, Badge, EmptyState, Drawer, Tooltip } from '../components/common';
import { cn } from '../utils/cn';
import {
  signalPipelineApi,
  pickBuyTomorrow,
  type PipelineStatus,
  type SignalResults,
  type SignalRow,
} from '../api/signalPipeline';
import { chipHealthApi, type ChipHealthResult } from '../api/chipHealth';
import { buyVerdict } from '../utils/buyVerdict';

function pct(x: number | null | undefined, signed = false): string {
  if (x === null || x === undefined || Number.isNaN(x)) return '—';
  const v = x * 100;
  return `${signed && v > 0 ? '+' : ''}${v.toFixed(0)}%`;
}

const TIMEFRAMES = [
  { key: 'daily', label: '日线' },
  { key: '5min', label: '5分钟' },
  { key: '15min', label: '15分钟' },
  { key: '30min', label: '30分钟' },
] as const;

const STATUS_ICONS: Record<string, React.ReactNode> = {
  done: <CheckCircle2 className="h-4 w-4 text-success" />,
  running: <Loader2 className="h-4 w-4 animate-spin text-cyan" />,
  failed: <XCircle className="h-4 w-4 text-danger" />,
  waiting: <div className="h-4 w-4 rounded-full border-2 border-border/50" />,
};

const STATUS_COLORS: Record<string, string> = {
  done: 'border-success/30 bg-success/5',
  running: 'border-cyan/30 bg-cyan/5',
  failed: 'border-danger/30 bg-danger/5',
  waiting: 'border-border/30 bg-transparent',
};

function today() {
  return new Date().toISOString().slice(0, 10);
}

export default function SignalPipelinePage() {
  const [date, setDate] = useState(today());
  const [running, setRunning] = useState(false);
  const [status, setStatus] = useState<PipelineStatus | null>(null);
  const [activeTab, setActiveTab] = useState<string>('daily');
  const [results, setResults] = useState<SignalResults | null>(null);
  const [loadingResults, setLoadingResults] = useState(false);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  // 轮询回调用 ref 读取最新 tab/日期加载函数，避免闭包捕获挂载时的旧值
  const activeTabRef = useRef<string>('daily');
  const loadResultsRef = useRef<(tf: string) => Promise<void>>(async () => {});
  useEffect(() => { activeTabRef.current = activeTab; }, [activeTab]);

  // 明日买入标的 · 就地筹码体检
  const [buyRunning, setBuyRunning] = useState(false);
  const [buyResult, setBuyResult] = useState<ChipHealthResult | null>(null);
  const [buyError, setBuyError] = useState('');
  const [buyOpen, setBuyOpen] = useState(false);

  // 轮询状态
  const startPolling = useCallback(() => {
    if (pollRef.current) clearInterval(pollRef.current);
    pollRef.current = setInterval(async () => {
      try {
        const s = await signalPipelineApi.status();
        setStatus(s);
        if (!s.running && s.state === 'done') {
          if (pollRef.current) clearInterval(pollRef.current);
          setRunning(false);
          loadResultsRef.current(activeTabRef.current);
        } else if (!s.running && s.state === 'failed') {
          if (pollRef.current) clearInterval(pollRef.current);
          setRunning(false);
        }
      } catch {
        // ignore
      }
    }, 3000);
  }, []);

  // 启动流水线
  const handleRun = async () => {
    try {
      setRunning(true);
      setStatus(null);
      setResults(null);
      await signalPipelineApi.run(date);
      startPolling();
    } catch (err: any) {
      setRunning(false);
      const msg = err?.response?.data?.detail || err.message;
      setStatus({ running: false, date, step: 0, total: 5, label: '', state: 'failed', detail: msg });
    }
  };

  // 清除买入体检状态（切换时段/重新运行/换日期时）
  const clearBuy = () => {
    setBuyResult(null);
    setBuyError('');
    setBuyOpen(false);
  };

  // 加载结果
  const loadResults = async (tf: string) => {
    setLoadingResults(true);
    clearBuy();
    try {
      const r = await signalPipelineApi.results(date, tf);
      setResults(r);
    } catch {
      setResults(null);
    } finally {
      setLoadingResults(false);
    }
  };

  useEffect(() => { loadResultsRef.current = loadResults; });

  // 切换 tab
  const handleTabChange = (tf: string) => {
    setActiveTab(tf);
    loadResults(tf);
  };

  // 初始化: 检查状态 + 加载结果
  useEffect(() => {
    signalPipelineApi.status().then((s) => {
      setStatus(s);
      if (s.running) {
        setRunning(true);
        startPolling();
      }
    }).catch(() => {});
    loadResults('daily');
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // 清理轮询
  useEffect(() => {
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, []);

  // 明日买入候选（仅日线）
  const buyList = activeTab === 'daily' && results ? pickBuyTomorrow(results.rows) : [];

  const handleBuyCheck = async () => {
    setBuyRunning(true);
    setBuyError('');
    setBuyResult(null);
    setBuyOpen(true);
    try {
      const r = await chipHealthApi.run(buyList);
      setBuyResult(r);
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } }; message?: string });
      setBuyError(detail?.response?.data?.detail || detail?.message || '体检失败');
    } finally {
      setBuyRunning(false);
    }
  };

  // 计算步骤状态
  const steps = getStepStates(status);

  return (
    <div className="mx-auto max-w-6xl space-y-4 p-4 lg:p-6">
      {/* 标题 */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="inline-flex items-center gap-1.5 text-xl font-bold text-foreground">
            信号链筛选
            <Tooltip
              contentClassName="max-w-[26rem]"
              side="bottom"
              content={
                <div className="space-y-2">
                  <p className="font-medium">信号链筛选策略</p>
                  <p>收盘后全市场按 MRMC 通道（蓝色梯子）+ DX 系战法信号独立筛选，日线 / 5 / 15 / 30 分钟四段并行；所有跟踪均从战法信号日起算。</p>
                  <div className="space-y-3">
                    <div>
                      <span className="font-medium">核心指标：</span>
                      <div className="text-xs space-y-1.5 pl-3 mt-1">
                        <p><strong>蓝色梯子</strong> — 上边缘 <span className="text-cyan">SA</span>（EMA-high-24）与下边缘 <span className="text-cyan">SB</span>（EMA-low-23）构成通道，跟踪主力资金的进出足迹</p>
                        <p><strong>DX/DXX/DXDX 信号</strong> — MRMC 战法触发点，一切状态跟踪的起点；信号后 <span className="text-cyan">≤5 个交易日</span>收盘突破 SA 才进入活跃轨道，否则作废</p>
                      </div>
                    </div>
                    <div className="border-t border-border/20 pt-2">
                      <span className="font-medium">两条买入规则（日线，2026-09 定稿）：</span>
                      <div className="text-xs space-y-1.5 pl-3 mt-1">
                        <p><strong>① 回踩完成 → 明日买入</strong> — 突破后缩量回踩下轨（量 ≤ 突破日 <span className="text-cyan">72%</span>、最低触及 SB）→ <span className="text-cyan">连续两日</span>温和放量（1.1–2.5×MA5 量）收阳且收盘收复 SB，两日中至少一天贴轨</p>
                        <p><strong>② 二次放量确认 → 明日买入</strong> — 起量突破（≥<span className="text-cyan">1.5×</span>MA5 量）→ 缩量回梯内（≤60% 且收盘 &lt; SA）→ 二次起量（≥1.2×收阳过前收）→ <span className="text-cyan">次日量能持续</span>（≥80% 且不破前日最低）</p>
                        <p><strong>失效线</strong> — 跟踪期收盘跌破 <span className="text-cyan">SB×0.97</span>（深度破位）立即作废；两规则同日满足时 ① 优先</p>
                      </div>
                    </div>
                    <div className="border-t border-border/20 pt-2">
                      <span className="font-medium">结果增强列：</span>
                      <div className="text-xs space-y-1.5 pl-3 mt-1">
                        <p><span className="text-cyan font-medium">主力资金流</span> — 东财个股 5 日累计/当日净流入与净占比、所属板块资金方向，用于验证量价信号的资金成色</p>
                        <p><span className="text-cyan font-medium">520 金叉</span> — MA5/MA20 多空关系与金叉后天数，作为趋势侧交叉确认</p>
                      </div>
                    </div>
                    <div className="border-t border-border/20 pt-2">
                      <p className="text-[11px] text-secondary-text leading-relaxed">
                        <strong>核心理念</strong>：缩量回踩下轨被接住是"深洗盘买点"，回调后二次放量是"二波进攻买点"。口径经过三年全市场回放收紧（历史胜率显著优于单日触轨即买的旧版），信号少而精——多数交易日没有买点是设计使然，中间态（回踩中/等二次起量）即明日候选前瞻清单。
                      </p>
                    </div>
                  </div>
                </div>
              }
            >
              <span className="inline-flex h-5 w-5 cursor-help items-center justify-center rounded-full border border-border/60 text-xs font-bold text-cyan hover:border-cyan hover:bg-cyan/10 hover:text-cyan">
                <Info className="h-3.5 w-3.5" />
              </span>
            </Tooltip>
          </h1>
          <p className="mt-1 text-sm text-secondary-text">
            多时段 MRMC 信号链独立筛选 — 日线 / 5分钟 / 15分钟 / 30分钟
          </p>
        </div>
      </div>

      {/* 控制栏 */}
      <Card padding="md">
        <div className="flex flex-wrap items-center gap-4">
          <div className="flex items-center gap-2">
            <Calendar className="h-4 w-4 text-secondary-text" />
            <input
              type="date"
              value={date}
              onChange={(e) => setDate(e.target.value)}
              disabled={running}
              className="rounded-lg border border-border/50 bg-card px-3 py-2 text-sm text-foreground outline-none focus:border-cyan/50 disabled:opacity-50"
            />
          </div>
          <Button
            variant="primary"
            size="md"
            isLoading={running}
            loadingText="筛选中..."
            onClick={handleRun}
            disabled={running}
          >
            <Play className="h-4 w-4" />
            运行流水线
          </Button>
          <a
            href={signalPipelineApi.downloadUrl(date)}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-2 rounded-xl border border-border/70 bg-card px-4 py-2 text-sm text-foreground shadow-soft-card transition-all hover:bg-hover"
          >
            <Download className="h-4 w-4" />
            下载 Excel
          </a>
        </div>
      </Card>

      {/* 步骤进度 */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
        {steps.map((step) => (
          <div
            key={step.num}
            className={cn(
              'flex items-center gap-2 rounded-xl border p-3 transition-all',
              STATUS_COLORS[step.state],
            )}
          >
            {STATUS_ICONS[step.state]}
            <div className="min-w-0 flex-1">
              <p className="truncate text-xs font-medium text-foreground">{step.label}</p>
              {step.detail && (
                <p className="truncate text-[10px] text-secondary-text">{step.detail}</p>
              )}
            </div>
          </div>
        ))}
      </div>

      {/* Tab 切换 */}
      <div className="flex gap-1 rounded-xl border border-border/30 bg-card p-1">
        {TIMEFRAMES.map((tf) => (
          <button
            key={tf.key}
            onClick={() => handleTabChange(tf.key)}
            className={cn(
              'flex-1 rounded-lg px-4 py-2 text-sm font-medium transition-all',
              activeTab === tf.key
                ? 'bg-primary-gradient text-primary-foreground shadow-lg shadow-cyan/20'
                : 'text-secondary-text hover:bg-hover hover:text-foreground',
            )}
          >
            {tf.label}
          </button>
        ))}
      </div>

      {/* 明日买入标的 · 筹码体检入口（仅日线且存在回踩完成标的时） */}
      {activeTab === 'daily' && buyList.length > 0 && (
        <Card padding="md">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h2 className="text-sm font-semibold text-foreground">
                🎯 {buyList.length} 只「明日买入」标的 · 筹码体检
              </h2>
              <p className="mt-0.5 text-xs text-secondary-text">
                用底部筹码流失排查诱多/派发陷阱，作为明日买入前的二次确认（体检约 30-60 秒）
              </p>
              {buyError && <p className="mt-1 text-xs text-danger">{buyError}</p>}
            </div>
            <Button
              variant="primary"
              size="md"
              isLoading={buyRunning}
              loadingText="体检中..."
              onClick={handleBuyCheck}
              disabled={buyRunning}
            >
              <Activity className="h-4 w-4" />
              开始体检
            </Button>
          </div>
        </Card>
      )}

      {/* 结果表格 */}
      <Card padding="none">
        {loadingResults ? (
          <div className="flex items-center justify-center py-16">
            <Loader2 className="h-6 w-6 animate-spin text-cyan" />
            <span className="ml-2 text-sm text-secondary-text">加载中...</span>
          </div>
        ) : !results || results.count === 0 ? (
          <EmptyState
            title="暂无数据"
            description={running ? '流水线运行中, 请等待完成后查看' : '点击"运行流水线"开始筛选'}
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border/30">
                  <th className="px-4 py-3 text-left text-xs font-medium text-secondary-text">代码</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-secondary-text">名称</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-secondary-text">信号状态</th>
                  <th className="px-4 py-3 text-right text-xs font-medium text-secondary-text">收盘价</th>
                  <th className="px-4 py-3 text-right text-xs font-medium text-secondary-text">满足520</th>
                  <th className="px-4 py-3 text-right text-xs font-medium text-secondary-text">A上轨</th>
                  <th className="px-4 py-3 text-right text-xs font-medium text-secondary-text">B下轨</th>
                    <th className="px-4 py-3 text-right text-xs font-medium text-secondary-text">5日主力</th>
                    <th className="px-4 py-3 text-right text-xs font-medium text-secondary-text">当日主力</th>
                    <th className="px-4 py-3 text-right text-xs font-medium text-secondary-text">主力占比%</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-secondary-text">所属板块</th>
                    <th className="px-4 py-3 text-right text-xs font-medium text-secondary-text">板块主力</th>
                </tr>
              </thead>
              <tbody>
                {results.rows.map((row, i) => (
                  <SignalRow key={row['股票代码'] + i} row={row} />
                ))}
              </tbody>
            </table>
          </div>
        )}
        {results && results.count > 0 && (
          <div className="border-t border-border/30 px-4 py-2 text-xs text-secondary-text">
            共 {results.count} 只
          </div>
        )}
      </Card>

      {/* 体检结果抽屉 */}
      <Drawer isOpen={buyOpen} onClose={() => setBuyOpen(false)} title="明日买入标的 · 筹码体检" width="max-w-6xl">
        {buyRunning ? (
          <div className="flex items-center justify-center gap-2 py-16 text-sm text-secondary-text">
            <Loader2 className="h-5 w-5 animate-spin text-cyan" /> 筹码引擎载入中（约 30-60 秒）...
          </div>
        ) : buyError && !buyResult ? (
          <EmptyState title="体检失败" description={buyError} />
        ) : !buyResult || buyResult.results.length === 0 ? (
          <EmptyState
            title="无有效结果"
            description={buyResult?.skipped?.length
              ? `候选均无法计算（跳过 ${buyResult.skipped.length} 只），请检查数据缓存`
              : '暂无可计算标的'}
          />
        ) : (
          <div className="space-y-4">
            <div className="flex flex-wrap gap-2 text-xs text-secondary-text">
              <span>行情截止 <span className="text-foreground">{buyResult.data_cutoff || '—'}</span></span>
              <span>共 {buyResult.results.length} 只</span>
              {buyResult.skipped?.length > 0 && <span>跳过 {buyResult.skipped.length}</span>}
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border/40 text-left text-xs text-secondary-text">
                    <th className="py-2 pr-3 font-medium">买入决策</th>
                    <th className="py-2 pr-3 font-medium">代码/名称</th>
                    <th className="py-2 pr-3 font-medium">收盘</th>
                    <th className="py-2 pr-3 font-medium">获利比例</th>
                    <th className="py-2 pr-3 font-medium">底筹</th>
                    <th className="py-2 pr-3 font-medium">流失3/5/7日</th>
                    <th className="py-2 font-medium">引擎结论</th>
                  </tr>
                </thead>
                <tbody>
                  {buyResult.results.map((x) => {
                    const bv = buyVerdict(x.level, x.high_profit_risk);
                    return (
                      <tr key={x.code} className="border-b border-border/20">
                        <td className="py-2 pr-3">
                          <span className={cn('inline-block rounded-lg border px-2 py-0.5 text-xs font-medium', bv.cls)}>
                            {x.level} {bv.label}
                          </span>
                        </td>
                        <td className="py-2 pr-3">
                          <div className="font-medium text-foreground">{x.name || '—'}</div>
                          <div className="text-xs text-secondary-text">{x.code}</div>
                        </td>
                        <td className="py-2 pr-3 text-foreground">{x.close ?? '—'}</td>
                        <td className={cn('py-2 pr-3', x.high_profit_risk ? 'font-medium text-danger' : 'text-foreground')}>
                          {pct(x.profit)}{x.high_profit_risk && ' ⚠️'}
                        </td>
                        <td className="py-2 pr-3 text-foreground">{pct(x.bottom)}</td>
                        <td className="py-2 pr-3 text-xs text-secondary-text">
                          {pct(x.loss3, true)} / {pct(x.loss5, true)} / {pct(x.loss7, true)}
                        </td>
                        <td className="py-2 text-xs text-secondary-text">{x.verdict}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
            <p className="text-[11px] text-secondary-text">
              仅供参考，不构成投资建议。红/橙=底筹连降疑似派发（诱多风险），绿/白=筹码稳定可正常买。
            </p>
          </div>
        )}
      </Drawer>
    </div>
  );
}

// ── 行组件 ──
function SignalRow({ row }: { row: SignalRow }) {
  const statusColor = getStatusColor(row['信号状态']);
  const satisfy520 = row['满足520'] === 'True' || row['满足520'] === 'true';

  return (
    <tr className="border-b border-border/10 transition-colors hover:bg-hover/50">
      <td className="px-4 py-2.5 font-mono text-xs text-foreground">{row['股票代码']}</td>
      <td className="px-4 py-2.5 text-sm text-foreground">{row['股票名称']}</td>
      <td className="px-4 py-2.5">
        <Badge variant={statusColor} size="sm">
          {row['信号状态']}
        </Badge>
      </td>
      <td className="px-4 py-2.5 text-right font-mono text-xs text-foreground">
        {row['最新收盘价']}
      </td>
      <td className="px-4 py-2.5 text-right">
        {satisfy520 ? (
          <span className="text-success">✓</span>
        ) : (
          <span className="text-secondary-text/40">—</span>
        )}
      </td>
      <td className="px-4 py-2.5 text-right font-mono text-xs text-foreground">
        {row['NX_A上轨'] || '—'}
      </td>
      <td className="px-4 py-2.5 text-right font-mono text-xs text-foreground">
        {row['NX_B下轨'] || '—'}
      </td>
      <td className="px-4 py-2.5 text-right font-mono text-xs text-foreground">
        {row['5日主力净流入']}
      </td>
      <td className="px-4 py-2.5 text-right font-mono text-xs text-foreground">
        {row['当日主力净流入']}
      </td>
      <td className="px-4 py-2.5 text-right font-mono text-xs text-foreground">
        {row['当日主力占比']}
      </td>
      <td className="px-4 py-2.5 text-sm text-foreground">
        {row['所属板块'] || ''}
      </td>
      <td className="px-4 py-2.5 text-right font-mono text-xs text-foreground">
        {row['板块主力净流入'] || ''}
      </td>
    </tr>
  );
}

// ── 工具函数 ──
function getStatusColor(status: string): 'success' | 'warning' | 'danger' | 'info' | 'default' {
  if (status.includes('回踩完成')) return 'success';
  if (status.includes('二次放量确认')) return 'success';
  if (status.includes('回踩中')) return 'warning';
  if (status.includes('突破')) return 'info';
  if (status.includes('等待')) return 'default';
  return 'default';
}

type StepState = { num: number; label: string; state: string; detail: string };

function getStepStates(status: PipelineStatus | null): StepState[] {
  const labels = ['抓取K线', '重建缓存', '信号筛选', '资金流', '520金叉'];
  return labels.map((label, i) => {
    const num = i + 1;
    if (!status) return { num, label, state: 'waiting', detail: '' };
    if (status.step > num) return { num, label, state: 'done', detail: '' };
    if (status.step === num) {
      return { num, label, state: status.state, detail: status.detail };
    }
    return { num, label, state: 'waiting', detail: '' };
  });
}
