import apiClient from './index';

export interface HoldingItem {
  code: string;
  name?: string;
  cost?: number | null;
}

export interface ChipHealthRow {
  code: string;
  name: string;
  data_date: string;
  close: number | null;
  cost: number | null;
  pnl: number | null;
  ret5: number | null;
  level: string; // 🔴/🟠/🟡/⚪/🟢/—
  verdict: string;
  profit: number | null;
  bottom: number | null;
  loss3: number | null;
  loss5: number | null;
  loss7: number | null;
  high_profit_risk: boolean;
}

export interface ChipHealthResult {
  generated_at: string;
  data_cutoff: string;
  count: number;
  results: ChipHealthRow[];
  skipped: { code: string; name: string; reason: string }[];
}

export interface ChipHealthStatus {
  data_dir: string;
  cache_exists: boolean;
  cache_mtime: string | null;
  holdings_count: number;
  holdings_file: string;
}

export const chipHealthApi = {
  async status(): Promise<ChipHealthStatus> {
    const response = await apiClient.get('/api/v1/chip-health/status');
    return response.data;
  },

  async getHoldings(): Promise<HoldingItem[]> {
    const response = await apiClient.get('/api/v1/chip-health/holdings');
    return response.data.holdings || [];
  },

  async saveHoldings(holdings: HoldingItem[]): Promise<number> {
    const response = await apiClient.put('/api/v1/chip-health/holdings', { holdings });
    return response.data.count;
  },

  async run(holdings?: HoldingItem[]): Promise<ChipHealthResult> {
    // 引擎需载入1GB缓存, 单独放宽超时
    const response = await apiClient.post(
      '/api/v1/chip-health/run',
      holdings ? { holdings } : {},
      { timeout: 300000 },
    );
    return response.data;
  },
};
