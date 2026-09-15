import apiClient from './index';
import { toCamelCase } from './utils';
import type {
  XinfaListResponse,
  XinfaEntryItem,
  XinfaCategorySummaryResponse,
  XinfaCreateRequest,
  XinfaUpdateRequest,
} from '../types/xinfa';

export const xinfaApi = {
  async list(params?: {
    category?: string;
    keyword?: string;
    stockCode?: string;
    isStarred?: boolean;
    page?: number;
    pageSize?: number;
  }): Promise<XinfaListResponse> {
    const response = await apiClient.get<Record<string, unknown>>('/api/v1/xinfa', { params });
    return toCamelCase<XinfaListResponse>(response.data);
  },

  async get(id: number): Promise<XinfaEntryItem> {
    const response = await apiClient.get<Record<string, unknown>>(`/api/v1/xinfa/${id}`);
    return toCamelCase<XinfaEntryItem>(response.data);
  },

  async create(data: XinfaCreateRequest): Promise<XinfaEntryItem> {
    const response = await apiClient.post<Record<string, unknown>>('/api/v1/xinfa', data);
    return toCamelCase<XinfaEntryItem>(response.data);
  },

  async update(id: number, data: XinfaUpdateRequest): Promise<{ success: boolean }> {
    const response = await apiClient.put<{ success: boolean }>(`/api/v1/xinfa/${id}`, data);
    return response.data;
  },

  async delete(id: number): Promise<{ success: boolean }> {
    const response = await apiClient.delete<{ success: boolean }>(`/api/v1/xinfa/${id}`);
    return response.data;
  },

  async getCategories(): Promise<XinfaCategorySummaryResponse> {
    const response = await apiClient.get<Record<string, unknown>>('/api/v1/xinfa/categories');
    return toCamelCase<XinfaCategorySummaryResponse>(response.data);
  },

  async getStarred(limit?: number): Promise<XinfaListResponse> {
    const response = await apiClient.get<Record<string, unknown>>('/api/v1/xinfa/starred', {
      params: { limit },
    });
    return toCamelCase<XinfaListResponse>(response.data);
  },
};
