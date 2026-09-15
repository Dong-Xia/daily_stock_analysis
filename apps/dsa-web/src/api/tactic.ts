import apiClient from './index';
import { toCamelCase } from './utils';
import type { TripleVolumeResult } from '../types/tactic';

export interface OversoldCandidate {
  code: string;
  name: string;
  price: number;
  todayDropPct: number;
  nDayDropPct: number;
  biasFromMa5: number;
  turnoverRate: number;
  volume: number;
  passDrop: boolean;
  passBias: boolean;
  passVolume: boolean;
  passPosition: boolean;
  passSolidYin: boolean;
  passPanic: boolean;
  score: number;
}

export interface OversoldBounceResult {
  date: string;
  marketPanic: boolean;
  totalScanned: number;
  afterDetailed: number;
  candidates: OversoldCandidate[];
  elapsedSeconds: number;
}

export interface BottleneckAnalysis {
  sector: string;
  bottleneckDescription: string;
  bottleneckReason: string;
  keyTechnologies: string[];
  expansionCycle: string;
  substitutionRisk: string;
}

export interface CircuitBreaker {
  milestone: string;
  deadline: string;
  consequence: string;
}

export interface IndustryCandidate {
  code: string;
  name: string;
  marketCapYi: number;
  industry: string;
  subSector: string;
  grossMargin: number;
  grossMarginChange: number;
  capexGrowth: number;
  revenueYoy: number;
  profitYoy: number;
  institutionalCoverage: string;
  bottleneckMatch: string;
  redTeamReport: string;
  circuitBreakers: CircuitBreaker[];
  compositeScore: number;
}

export interface IndustryResearchResult {
  date: string;
  sector: string;
  bottleneck: BottleneckAnalysis | null;
  totalScanned: number;
  afterMarketCap: number;
  afterFinancial: number;
  candidates: IndustryCandidate[];
  elapsedSeconds: number;
}

export const tacticApi = {
  async tripleVolumeScreen(
    minVolumeRatio: number = 3.0,
    minChangePct: number = 5.0,
    minTurnoverRate: number = 3.0,
  ): Promise<TripleVolumeResult> {
    const response = await apiClient.post<Record<string, unknown>>(
      '/api/v1/stocks/triple-volume',
      null,
      {
        params: {
          min_volume_ratio: minVolumeRatio,
          min_change_pct: minChangePct,
          min_turnover_rate: minTurnoverRate,
        },
        timeout: 180000,
      },
    );
    return toCamelCase<TripleVolumeResult>(response.data);
  },

  async oversoldBounceScreen(
    lookbackDays: number = 5,
    minDropPct: number = 20.0,
    maxBiasPct: number = -8.0,
  ): Promise<OversoldBounceResult> {
    const response = await apiClient.post<Record<string, unknown>>(
      '/api/v1/stocks/oversold-bounce',
      null,
      {
        params: {
          lookback_days: lookbackDays,
          min_drop_pct: minDropPct,
          max_bias_pct: maxBiasPct,
        },
        timeout: 180000,
      },
    );
    return toCamelCase<OversoldBounceResult>(response.data);
  },

  async industryResearchScreen(
    sector: string,
    minMarketCapYi: number = 30.0,
    maxMarketCapYi: number = 500.0,
    minCompositeScore: number = 60.0,
  ): Promise<IndustryResearchResult> {
    const response = await apiClient.post<Record<string, unknown>>(
      '/api/v1/stocks/industry-research',
      null,
      {
        params: {
          sector: sector,
          min_market_cap_yi: minMarketCapYi,
          max_market_cap_yi: maxMarketCapYi,
          min_composite_score: minCompositeScore,
        },
        timeout: 120000,
      },
    );
    return toCamelCase<IndustryResearchResult>(response.data);
  },
};
