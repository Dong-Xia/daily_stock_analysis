import apiClient from './index';
import { toCamelCase } from './utils';
import type { HotSectorsResponse, SectorRankingsResponse, ManualSectorInput, ManualSectorParseResponse, ScraperBoardDataResponse } from '../types/sectors';

async function withRetry<T>(
  fn: () => Promise<T>,
  maxRetries: number = 1,
  delayMs: number = 2000,
): Promise<T> {
  let lastError: unknown;
  for (let attempt = 0; attempt <= maxRetries; attempt++) {
    try {
      return await fn();
    } catch (err) {
      lastError = err;
      if (attempt < maxRetries) {
        await new Promise((resolve) => setTimeout(resolve, delayMs));
      }
    }
  }
  throw lastError;
}

export const sectorsApi = {
  async getHotSectors(params?: {
    market?: string;
    limit?: number;
    minLimitUp?: number;
    date?: string;
  }): Promise<HotSectorsResponse> {
    return withRetry(async () => {
      const response = await apiClient.get<Record<string, unknown>>('/api/v1/sectors/hot', {
        params,
      });
      return toCamelCase<HotSectorsResponse>(response.data);
    });
  },

  async getAvailableDates(): Promise<string[]> {
    const response = await apiClient.get<string[]>('/api/v1/sectors/available-dates');
    return response.data;
  },

  async getSectorRankings(params?: {
    market?: string;
    limit?: number;
  }): Promise<SectorRankingsResponse> {
    return withRetry(async () => {
      const response = await apiClient.get<Record<string, unknown>>('/api/v1/sectors/rankings', {
        params,
      });
      return toCamelCase<SectorRankingsResponse>(response.data);
    });
  },

  async parseManualSectors(request: ManualSectorInput): Promise<ManualSectorParseResponse> {
    return withRetry(async () => {
      const response = await apiClient.post<Record<string, unknown>>('/api/v1/sectors/parse-manual', request);
      return toCamelCase<ManualSectorParseResponse>(response.data);
    });
  },

  async triggerAnalysis(): Promise<HotSectorsResponse> {
    return withRetry(async () => {
      const response = await apiClient.post<Record<string, unknown>>('/api/v1/sectors/trigger-analysis', {
        limit: 20,
        minLimitUp: 1,
      });
      return toCamelCase<HotSectorsResponse>(response.data);
    });
  },

  async getScraperBoardData(params?: { date?: string }): Promise<ScraperBoardDataResponse> {
    const response = await apiClient.get<Record<string, unknown>>('/api/v1/sectors/scraper-board-data', {
      params,
    });
    return toCamelCase<ScraperBoardDataResponse>(response.data);
  },

  async triggerScraper(params?: { date?: string }): Promise<ScraperBoardDataResponse> {
    const response = await apiClient.post<Record<string, unknown>>('/api/v1/sectors/trigger-scraper', null, {
      params,
    });
    return toCamelCase<ScraperBoardDataResponse>(response.data);
  },

  async getScraperAvailableDates(): Promise<string[]> {
    const response = await apiClient.get<string[]>('/api/v1/sectors/scraper-available-dates');
    return response.data;
  },
};
