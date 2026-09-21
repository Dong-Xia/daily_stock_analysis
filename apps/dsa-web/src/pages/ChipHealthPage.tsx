import { useEffect, useState } from 'react';
import { Info, Play, Plus, Save, Trash2 } from 'lucide-react';
import { Card, Button, EmptyState, Tooltip } from '../components/common';
import { cn } from '../utils/cn';
import {
  chipHealthApi,
  type ChipHealthRow,
  type ChipHealthStatus,
  type HoldingItem,
} from '../api/chipHealth';

interface EditRow {
  code: string;
  name: string;
  cost: string;
}

const LEVEL_META: Record<string, { label: string; cls: string }> = {
  '🔴': { label: '强烈减仓', cls: 'border-danger/40 bg-danger/10 text-danger' },
  '🟠': { label: '建议减仓', cls: 'border-orange-500/40 bg-orange-500/10 text-orange-400' },
  '🟡': { label: '警惕观察', cls: 'border-yellow-500/40 bg-yellow-500/10 text-yellow-300' },
  '⚪': { label: '假象勿卖', cls: 'border-border/60 bg-card text-secondary-text' },
  '🟢': { label: '可继续持有', cls: 'border-success/40 bg-success/10 text-success' },
  '—': { label: '无法判断', cls: 'border-border/40 bg-transparent text-secondary-text' },
};

function pct(x: number | null | undefined, signed = false): string {
  if (x === null || x === undefined || Number.isNaN(x)) return '—';
  const v = x * 100;
  return `${signed && v > 0 ? '+' : ''}${v.toFixed(0)}%`;
}

export default function ChipHealthPage() {
  const [status, setStatus] = useState<ChipHealthStatus | null>(null);
  const [rows, setRows] = useState<EditRow[]>([]);
  const [result, setResult] = useState<{ results: ChipHealthRow[]; skipped: { code: string; name: string; reason: string }[]; data_cutoff: string } | null>(null);
  const [running, setRunning] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    chipHealthApi.status().then(setStatus).catch(() => {});
    chipHealthApi.getHoldings()
      .then((hs) => setRows(hs.length ? hs.map((h) => ({ code: h.code, name: h.name || '', cost: h.cost != null ? String(h.cost) : '' })) : []))
      .catch(() => {});
  }, []);

  const validRows = (): EditRow[] => rows.filter((r) => r.code.trim());

  const toPayload = (rs: EditRow[]): HoldingItem[] => rs.map((r) => ({
    code: r.code.trim().padStart(6, '0'),
    name: r.name.trim(),
    cost: r.cost.trim() ? Number(r.cost) : null,
  }));

  const handleSave = async () => {
    setSaving(true);
    setError('');
    try {
      const n = await chipHealthApi.saveHoldings(toPayload(validRows()));
      setStatus((s) => (s ? { ...s, holdings_count: n } : s));
    } catch (err: any) {
      setError(`保存失败: ${err?.response?.data?.detail || err.message}`);
    } finally {
      setSaving(false);
    }
  };

  const handleRun = async () => {
    const rs = validRows();
    if (!rs.length) {
      setError('请先填写持仓代码');
      return;
    }
    setRunning(true);
    setError('');
    setResult(null);
    try {
      await chipHealthApi.saveHoldings(toPayload(rs));
      const r = await chipHealthApi.run(toPayload(rs));
      setResult(r);
      setStatus((s) => (s ? { ...s, holdings_count: r.count + r.skipped.length } : s));
    } catch (err: any) {
      setError(`体检失败: ${err?.response?.data?.detail || err.message}`);
    } finally {
      setRunning(false);
    }
  };

  const setRow = (i: number, patch: Partial<EditRow>) =>
    setRows((prev) => prev.map((r, j) => (j === i ? { ...r, ...patch } : r)));

  const counts = ['🔴', '🟠', '🟡', '⚪', '🟢'].map((lv) => ({
    lv,
    n: result ? result.results.filter((x) => x.level === lv).length : 0,
  }));

  return (
    <div className="mx-auto max-w-6xl space-y-4 p-4 lg:p-6">
      {/* 标题 */}
      <div>
        <h1 className="inline-flex items-center gap-1.5 text-xl font-bold text-foreground">
          持仓筹码体检
          <Tooltip
            contentClassName="max-w-[26rem]"
            side="bottom"
            content={
              <div className="space-y-2">
                <p className="font-medium">筹码体检策略</p>
                <p>用本地 3 年日线重建筹码分布，聚焦<strong>底部筹码的多日连续流失</strong>——底部筹码是主力压舱石，主力真走货它一定先漏。判定规则经 2023–2026 历史回测验证。</p>
                <div className="space-y-3">
                  <div>
                    <span className="font-medium">五档灯语（信号后 3 日下跌概率为回测值）：</span>
                    <div className="text-xs space-y-1.5 pl-3 mt-1">
                      <p><span className="text-cyan">🔴</span> <strong>底筹连降 7 日且累计流失 &gt;18%</strong> — 61.0%，主力派发，减仓</p>
                      <p><span className="text-cyan">🟠</span> <strong>连降 5 日且累计流失 &gt;15%</strong> — 60.6%，高危，减仓</p>
                      <p><span className="text-cyan">🟡</span> <strong>连降 3 日且累计流失 &gt;8%</strong> — 58.4%，先警示</p>
                      <p><span className="text-cyan">⚪</span> <strong>3 日流失 &gt;8% 但非逐日</strong>（骤减又回补）— 量化做 T 假象，随后均值 <span className="text-cyan">+0.89%</span>，勿卖</p>
                      <p><span className="text-cyan">🟢</span> <strong>底筹稳定或增加</strong> — 继续持有</p>
                    </div>
                  </div>
                  <div className="border-t border-border/20 pt-2">
                    <span className="font-medium">算法与细节：</span>
                    <div className="text-xs space-y-1.5 pl-3 mt-1">
                      <p>通达信式三角分布 + 换手率日级衰减；"连降 N 日"即口诀<strong>"单日筹码不要信，连看两三辨真假"</strong>的量化版</p>
                      <p>获利比例 &gt;90% 额外标记高位风险 ⚠️；成交量单位按每票历史量级自动校正</p>
                    </div>
                  </div>
                  <div className="border-t border-border/20 pt-2">
                    <span className="font-medium">买入前体检（信号链联动）：</span>
                    <p className="text-xs pl-3 mt-1">对"明日买入"候选票用同一引擎反向排查诱多/派发：🟢 技术+筹码双确认 · ⚪ 正常买 · 🟡 轻仓观察 · 🟠 诱多风险谨慎 · 🔴 放弃买入</p>
                  </div>
                  <div className="border-t border-border/20 pt-2">
                    <p className="text-[11px] text-secondary-text leading-relaxed">
                      <strong>定位与局限</strong>：该体系价值在<strong>避雷/砍尾部</strong>而非高胜率择时；股本以最新总市值近似（小流通盘次新股换手会高估）；结果仅供参考，不构成投资建议。
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
          基于本地3年日线的筹码引擎 — 底部筹码多日流失检测（🔴连降7日&gt;18% / 🟠5日&gt;15% / 🟡3日&gt;8%），
          ⚪为量化做T假象（勿卖）。规则依据2023-2026回测，仅供参考不构成投资建议。
        </p>
      </div>

      {/* 数据状态 */}
      {status && (
        <Card padding="sm">
          <div className="flex flex-wrap items-center gap-x-6 gap-y-1 text-xs text-secondary-text">
            <span>数据目录: <code className="text-foreground">{status.data_dir}</code></span>
            <span>指标缓存: {status.cache_exists
              ? <span className="text-success">已就绪（更新于 {status.cache_mtime}）</span>
              : <span className="text-danger">缺失（请先跑收盘流水线）</span>}</span>
            {result?.data_cutoff && <span>行情截止: <span className="text-foreground">{result.data_cutoff}</span></span>}
          </div>
        </Card>
      )}

      {/* 持仓清单编辑 */}
      <Card padding="md">
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-sm font-semibold text-foreground">
            持仓清单 {status && `（已保存 ${status.holdings_count} 只）`}
          </h2>
          <button
            onClick={() => setRows((p) => [...p, { code: '', name: '', cost: '' }])}
            className="inline-flex items-center gap-1 rounded-lg border border-border/50 px-2.5 py-1 text-xs text-foreground transition-colors hover:bg-hover"
          >
            <Plus className="h-3.5 w-3.5" /> 添加一行
          </button>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border/40 text-left text-xs text-secondary-text">
                <th className="py-2 pr-3 font-medium">代码 *</th>
                <th className="py-2 pr-3 font-medium">名称</th>
                <th className="py-2 pr-3 font-medium">成本价(可空)</th>
                <th className="w-10 py-2" />
              </tr>
            </thead>
            <tbody>
              {rows.length === 0 && (
                <tr>
                  <td colSpan={4} className="py-6 text-center text-sm text-secondary-text">
                    暂无持仓，点击「添加一行」录入（代码如 600519）
                  </td>
                </tr>
              )}
              {rows.map((r, i) => (
                <tr key={i} className="border-b border-border/20">
                  <td className="py-1.5 pr-3">
                    <input
                      value={r.code}
                      onChange={(e) => setRow(i, { code: e.target.value })}
                      placeholder="6位代码"
                      className="w-28 rounded-lg border border-border/50 bg-card px-2 py-1.5 text-sm text-foreground outline-none focus:border-cyan/50"
                    />
                  </td>
                  <td className="py-1.5 pr-3">
                    <input
                      value={r.name}
                      onChange={(e) => setRow(i, { name: e.target.value })}
                      placeholder="自动补全"
                      className="w-32 rounded-lg border border-border/50 bg-card px-2 py-1.5 text-sm text-foreground outline-none focus:border-cyan/50"
                    />
                  </td>
                  <td className="py-1.5 pr-3">
                    <input
                      value={r.cost}
                      onChange={(e) => setRow(i, { cost: e.target.value })}
                      placeholder="可空"
                      className="w-24 rounded-lg border border-border/50 bg-card px-2 py-1.5 text-sm text-foreground outline-none focus:border-cyan/50"
                    />
                  </td>
                  <td className="py-1.5">
                    <button
                      onClick={() => setRows((p) => p.filter((_, j) => j !== i))}
                      className="rounded p-1 text-secondary-text transition-colors hover:text-danger"
                      aria-label="删除该行"
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="mt-4 flex flex-wrap items-center gap-3">
          <Button
            variant="primary"
            size="md"
            isLoading={running}
            loadingText="体检中（约30-60秒）..."
            onClick={handleRun}
            disabled={running || saving}
          >
            <Play className="h-4 w-4" />
            保存并开始体检
          </Button>
          <Button variant="secondary" size="md" isLoading={saving} loadingText="保存中" onClick={handleSave} disabled={running || saving}>
            <Save className="h-4 w-4" />
            仅保存清单
          </Button>
          {error && <span className="text-sm text-danger">{error}</span>}
        </div>
      </Card>

      {/* 结果 */}
      {result && (
        <>
          <div className="flex flex-wrap gap-2">
            {counts.map(({ lv, n }) => (
              <span
                key={lv}
                className={cn(
                  'rounded-lg border px-3 py-1.5 text-xs font-medium',
                  n > 0 ? LEVEL_META[lv]?.cls : 'border-border/30 text-secondary-text opacity-60',
                )}
              >
                {lv} {LEVEL_META[lv]?.label} × {n}
              </span>
            ))}
            {result.skipped.length > 0 && (
              <span className="rounded-lg border border-border/30 px-3 py-1.5 text-xs text-secondary-text">
                跳过 {result.skipped.length}（{result.skipped.map((s) => s.code).join(' ')}）
              </span>
            )}
          </div>

          {result.results.length === 0 ? (
            <EmptyState title="无有效结果" description="所有持仓均无法计算，请检查代码或数据缓存" />
          ) : (
            <Card padding="md">
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-border/40 text-left text-xs text-secondary-text">
                      <th className="py-2 pr-3 font-medium">判定</th>
                      <th className="py-2 pr-3 font-medium">代码/名称</th>
                      <th className="py-2 pr-3 font-medium">收盘</th>
                      <th className="py-2 pr-3 font-medium">浮盈</th>
                      <th className="py-2 pr-3 font-medium">获利比例</th>
                      <th className="py-2 pr-3 font-medium">底筹</th>
                      <th className="py-2 pr-3 font-medium">流失3/5/7日</th>
                      <th className="py-2 font-medium">结论</th>
                    </tr>
                  </thead>
                  <tbody>
                    {result.results.map((x) => (
                      <tr key={x.code} className="border-b border-border/20">
                        <td className="py-2 pr-3">
                          <span className={cn('inline-block rounded-lg border px-2 py-0.5 text-xs font-medium', LEVEL_META[x.level]?.cls)}>
                            {x.level} {LEVEL_META[x.level]?.label}
                          </span>
                        </td>
                        <td className="py-2 pr-3">
                          <div className="font-medium text-foreground">{x.name || '—'}</div>
                          <div className="text-xs text-secondary-text">{x.code} · 数据{x.data_date}</div>
                        </td>
                        <td className="py-2 pr-3 text-foreground">{x.close ?? '—'}</td>
                        <td className={cn('py-2 pr-3', x.pnl != null && x.pnl < 0 ? 'text-danger' : 'text-success')}>
                          {x.pnl != null ? pct(x.pnl, true) : '—'}
                        </td>
                        <td className={cn('py-2 pr-3', x.high_profit_risk ? 'font-medium text-danger' : 'text-foreground')}>
                          {pct(x.profit)}{x.high_profit_risk && ' ⚠️'}
                        </td>
                        <td className="py-2 pr-3 text-foreground">{pct(x.bottom)}</td>
                        <td className="py-2 pr-3 text-xs text-secondary-text">
                          {pct(x.loss3, true)} / {pct(x.loss5, true)} / {pct(x.loss7, true)}
                        </td>
                        <td className="py-2 text-xs text-foreground">{x.verdict}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Card>
          )}
        </>
      )}
    </div>
  );
}
