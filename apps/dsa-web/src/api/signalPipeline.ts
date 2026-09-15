import apiClient from './index';
import type { HoldingItem } from './chipHealth';

/** 日线信号链状态机产出的「明日买入」标签 */
export const BUY_TOMORROW_STATUS = '今日回踩完成→明日买入';
export const BUY_TOMORROW_STATUS_R2 = '二次放量确认→明日买入';
export const BUY_TOMORROW_STATUSES: string[] = [BUY_TOMORROW_STATUS, BUY_TOMORROW_STATUS_R2];

/**
 * 从信号链结果行中筛出「明日买入」标的（R1 回踩完成 + R2 二次放量确认），转为筹码体检持仓清单。
 * cost 置空（候选尚未持仓，体检不显示浮盈）。
 */
export function pickBuyTomorrow(rows: SignalRow[]): HoldingItem[] {
  return rows
    .filter((r) => BUY_TOMORROW_STATUSES.includes(r['信号状态']))
    .map((r) => ({
      code: String(r['股票代码']).trim().padStart(6, '0'),
      name: String(r['股票名称'] ?? '').trim(),
      cost: null,
    }));
}

export interface PipelineStatus {
  running: boolean;
  date: string;
  step: number;
  total: number;
  label: string;
  state: string;
  detail: string;
}

export interface SignalRow {
  '股票代码': string;
  '股票名称': string;
  '信号状态': string;
  '信号类型': string;
  '信号日期': string;
  '最新收盘价': string;
  'NX_A上轨': string;
  'NX_B下轨': string;
  'MA5': string;
  'MA20': string;
  '金叉后N日': string;
  '满足520': string;
  '5日主力净流入': string;
  '当日主力净流入': string;
  '当日主力占比': string;
  [key: string]: string;
}

export interface SignalResults {
  date: string;
  timeframe: string;
  timeframe_label: string;
  count: number;
  rows: SignalRow[];
}

export const signalPipelineApi = {
  async run(date: string): Promise<{ message: string; date: string }> {
    const response = await apiClient.post('/api/v1/signal-pipeline/run', { date });
    return response.data;
  },

  async status(): Promise<PipelineStatus> {
    const response = await apiClient.get('/api/v1/signal-pipeline/status');
    // 只转换外层 snake_case → camelCase, 不动 rows 里的中文 key
    const d = response.data;
    return {
      running: d.running,
      date: d.date,
      step: d.step,
      total: d.total,
      label: d.label,
      state: d.state,
      detail: d.detail,
    };
  },

  async results(date: string, timeframe: string): Promise<SignalResults> {
    const response = await apiClient.get('/api/v1/signal-pipeline/results', {
      params: { date, timeframe },
    });
    // 不用 toCamelCase — 中文 key 需要原样保留
    return response.data as SignalResults;
  },

  downloadUrl(date: string): string {
    return `/api/v1/signal-pipeline/download?date=${date}`;
  },
};
