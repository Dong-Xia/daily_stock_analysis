import apiClient from './index';
import { toCamelCase } from './utils';
import type {
  HotSectorChainResponse,
  MarketRegimeResponse,
  SectorRotationResponse,
  ScreenResponse,
  PositionSizeRequest,
  PositionSizeResponse,
  StopLossRequest,
  StopLossResponse,
  RebalanceResponse,
  FundamentalScreenResponse,
} from '../types/stockPick';

async function withRetry<T>(
  fn: () => Promise<T>,
  maxRetries: number = 1,
  delayMs: number = 2000,
  shouldRetry?: (error: unknown) => boolean,
): Promise<T> {
  let lastError: unknown;
  for (let attempt = 0; attempt <= maxRetries; attempt++) {
    try {
      return await fn();
    } catch (err) {
      lastError = err;
      if (attempt < maxRetries) {
        if (shouldRetry && !shouldRetry(err)) {
          break;
        }
        await new Promise((resolve) => setTimeout(resolve, delayMs));
      }
    }
  }
  throw lastError;
}

export const stockPickApi = {
  async getMarketRegime(): Promise<MarketRegimeResponse> {
    return withRetry(async () => {
      const response = await apiClient.get<Record<string, unknown>>(
        '/api/v1/stocks/market-regime',
      );
      return toCamelCase<MarketRegimeResponse>(response.data);
    });
  },

  async getSectorRotation(lookbackDays: number = 20): Promise<SectorRotationResponse> {
    return withRetry(async () => {
      const response = await apiClient.get<Record<string, unknown>>(
        '/api/v1/stocks/sector-rotation',
        { params: { lookback_days: lookbackDays }, timeout: 60000 },
      );
      return toCamelCase<SectorRotationResponse>(response.data);
    });
  },

  async screenStocks(sectorName: string, requireMaAlignment: boolean = true): Promise<ScreenResponse> {
    return withRetry(async () => {
      const response = await apiClient.post<Record<string, unknown>>(
        '/api/v1/stocks/screen',
        null,
        { params: { sector_name: sectorName, require_ma_alignment: requireMaAlignment }, timeout: 180000 },
      );
      return toCamelCase<ScreenResponse>(response.data);
    }, 1, 2000, (err) => {
      const axiosErr = err as { code?: string; response?: { status?: number } };
      if (axiosErr?.code === 'ECONNABORTED') return false;
      if (axiosErr?.response?.status === 504) return false;
      return true;
    });
  },

  async calculatePositionSize(request: PositionSizeRequest): Promise<PositionSizeResponse> {
    return withRetry(async () => {
      const response = await apiClient.post<Record<string, unknown>>(
        '/api/v1/stocks/position-size',
        request,
      );
      return toCamelCase<PositionSizeResponse>(response.data);
    });
  },

  async evaluateStopLoss(request: StopLossRequest): Promise<StopLossResponse> {
    return withRetry(async () => {
      const response = await apiClient.post<Record<string, unknown>>(
        '/api/v1/stocks/stop-loss',
        request,
      );
      return toCamelCase<StopLossResponse>(response.data);
    });
  },

  async rebalance(positions: string): Promise<RebalanceResponse> {
    return withRetry(async () => {
      const response = await apiClient.post<Record<string, unknown>>(
        '/api/v1/stocks/rebalance',
        null,
        { params: { positions } },
      );
      return toCamelCase<RebalanceResponse>(response.data);
    });
  },

  async hotSectorChain(): Promise<HotSectorChainResponse> {
    return withRetry(async () => {
      const response = await apiClient.post<Record<string, unknown>>(
        '/api/v1/stocks/hot-sector-chain',
        {},
        { timeout: 300000 },
      );
      return toCamelCase<HotSectorChainResponse>(response.data);
    }, 1, 2000, (err) => {
      const axiosErr = err as { code?: string; response?: { status?: number } };
      if (axiosErr?.code === 'ECONNABORTED') return false;
      if (axiosErr?.response?.status === 504) return false;
      return true;
    });
  },

  async fundamentalScreen(quarterDate?: string): Promise<FundamentalScreenResponse> {
    return withRetry(async () => {
      const response = await apiClient.get<Record<string, unknown>>(
        '/api/v1/stocks/fundamental',
        { params: { quarter_date: quarterDate || '' } },
      );
      return toCamelCase<FundamentalScreenResponse>(response.data);
    });
  },
};
