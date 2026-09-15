import apiClient from './index';

export interface MarketReviewMeta {
  date: string;
  date_formatted: string;
  filename: string;
}

export interface MarketReviewReport {
  meta: MarketReviewMeta;
  content: string;
}

export interface MarketReviewListResponse {
  reports: MarketReviewMeta[];
  total: number;
}

export interface MarketReviewSingleResponse {
  report: MarketReviewReport;
}

export interface MarketReviewGenerateResponse {
  success: boolean;
  report: string;
  reports: MarketReviewMeta[];
}

export const marketReviewApi = {
  list: async (): Promise<MarketReviewListResponse> => {
    const response = await apiClient.get('/api/v1/market-review/list');
    return response.data as MarketReviewListResponse;
  },

  latest: async (): Promise<MarketReviewSingleResponse> => {
    const response = await apiClient.get('/api/v1/market-review/latest');
    return response.data as MarketReviewSingleResponse;
  },

  getByDate: async (date: string): Promise<MarketReviewSingleResponse> => {
    const response = await apiClient.get(`/api/v1/market-review/${date}`);
    return response.data as MarketReviewSingleResponse;
  },

  generate: async (): Promise<MarketReviewGenerateResponse> => {
    const response = await apiClient.post('/api/v1/market-review/generate');
    return response.data as MarketReviewGenerateResponse;
  },
};
