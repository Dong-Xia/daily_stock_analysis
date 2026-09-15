import { create } from 'zustand';
import { marketReviewApi, type MarketReviewMeta, type MarketReviewReport } from '../api/marketReview';

// 报告正文请求序号：快速切换日期时，慢的旧响应不得覆盖新响应
// （与 stockPoolStore.historyRequestSeq 同一范式）
let contentRequestSeq = 0;

interface MarketReviewState {
  reports: MarketReviewMeta[];
  current: MarketReviewReport | null;
  currentIndex: number;
  isLoading: boolean;
  isLoadingContent: boolean;
  isGenerating: boolean;
  error: string | null;
  loaded: boolean;

  loadList: () => Promise<void>;
  loadContent: (date: string) => Promise<void>;
  generate: () => Promise<void>;
  selectReport: (meta: MarketReviewMeta, idx: number) => Promise<void>;
  goToPrev: () => void;
  goToNext: () => void;
}

export const useMarketReviewStore = create<MarketReviewState>((set, get) => ({
  reports: [],
  current: null,
  currentIndex: 0,
  isLoading: true,
  isLoadingContent: false,
  isGenerating: false,
  error: null,
  loaded: false,

  loadList: async () => {
    set({ isLoading: true, error: null });
    try {
      const data = await marketReviewApi.list();
      const state = get();
      set({ reports: data.reports, loaded: true });
      if (data.reports.length > 0 && !state.current) {
        set({ currentIndex: 0 });
        await get().loadContent(data.reports[0].date);
      } else {
        set({ isLoading: false });
      }
    } catch (err) {
      set({ error: err instanceof Error ? err.message : '加载失败', isLoading: false });
    }
  },

  loadContent: async (date: string) => {
    const requestId = ++contentRequestSeq;
    set({ isLoadingContent: true });
    try {
      const data = await marketReviewApi.getByDate(date);
      if (requestId !== contentRequestSeq) return;
      set({ current: data.report });
    } catch (err) {
      if (requestId !== contentRequestSeq) return;
      set({ error: err instanceof Error ? err.message : '加载报告失败' });
    } finally {
      if (requestId === contentRequestSeq) {
        set({ isLoadingContent: false, isLoading: false });
      }
    }
  },

  generate: async () => {
    set({ isGenerating: true, error: null });
    try {
      const data = await marketReviewApi.generate();
      set({ reports: data.reports });
      if (data.reports.length > 0) {
        set({ currentIndex: 0 });
        await get().loadContent(data.reports[0].date);
      } else {
        set({ current: null });
      }
    } catch (err) {
      set({ error: err instanceof Error ? err.message : '生成失败' });
    } finally {
      set({ isGenerating: false });
    }
  },

  selectReport: async (meta: MarketReviewMeta, idx: number) => {
    set({ currentIndex: idx, error: null });
    await get().loadContent(meta.date);
  },

  goToPrev: () => {
    const { currentIndex, reports } = get();
    const next = Math.min(currentIndex + 1, reports.length - 1);
    if (next !== currentIndex) {
      set({ currentIndex: next });
      get().loadContent(reports[next].date);
    }
  },

  goToNext: () => {
    const { currentIndex, reports } = get();
    const next = Math.max(currentIndex - 1, 0);
    if (next !== currentIndex) {
      set({ currentIndex: next });
      get().loadContent(reports[next].date);
    }
  },
}));
