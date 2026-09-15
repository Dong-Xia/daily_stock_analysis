// 筹码体检结果 → 买入语义文案转译（仅展示层，底层引擎数值不变）
// 供「信号链回踩完成标的 · 就地筹码体检」使用：把持仓视角的
// 🔴/🟠/🟡/⚪/🟢 减仓判定改写为明日买入决策语义。

export interface BuyVerdict {
  label: string; // 买入语义结论文案（含获利盘风险后缀）
  cls: string; // 徽章配色
}

interface LevelMeta {
  buy: string;
  cls: string;
}

const LEVEL_META: Record<string, LevelMeta> = {
  '🟢': { buy: '技术+筹码双确认 · 可买', cls: 'border-success/40 bg-success/10 text-success' },
  '⚪': { buy: '量化做T假象 · 可正常买', cls: 'border-border/60 bg-card text-secondary-text' },
  '🟡': { buy: '筹码不稳 · 轻仓/观察', cls: 'border-yellow-500/40 bg-yellow-500/10 text-yellow-300' },
  '🟠': { buy: '底筹连降 · 诱多风险，谨慎', cls: 'border-orange-500/40 bg-orange-500/10 text-orange-400' },
  '🔴': { buy: '主力派发 · 放弃明日买入', cls: 'border-danger/40 bg-danger/10 text-danger' },
  '—': { buy: '数据不足 · 无法判断', cls: 'border-border/40 bg-transparent text-secondary-text' },
};

const FALLBACK: LevelMeta = { buy: '无法判断', cls: 'border-border/40 bg-transparent text-secondary-text' };

/**
 * 把筹码引擎档位转译为买入语义文案。
 * @param level 引擎输出档位 emoji（🔴/🟠/🟡/⚪/🟢/—）
 * @param highProfitRisk 获利比例>90%（追加诱多风险提示）
 */
export function buyVerdict(level: string, highProfitRisk = false): BuyVerdict {
  const meta = LEVEL_META[level] ?? FALLBACK;
  const label = highProfitRisk ? `${meta.buy}｜⚠️获利盘>90%` : meta.buy;
  return { label, cls: meta.cls };
}
