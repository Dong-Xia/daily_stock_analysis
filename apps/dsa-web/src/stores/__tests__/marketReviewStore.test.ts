import { beforeEach, describe, expect, it, vi } from 'vitest';
import { marketReviewApi, type MarketReviewSingleResponse } from '../../api/marketReview';
import { useMarketReviewStore } from '../marketReviewStore';

vi.mock('../../api/marketReview', () => ({
  marketReviewApi: {
    list: vi.fn(),
    getByDate: vi.fn(),
    generate: vi.fn(),
  },
}));

function deferred() {
  let resolve!: (v: MarketReviewSingleResponse) => void;
  let reject!: (e: unknown) => void;
  const promise = new Promise<MarketReviewSingleResponse>((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
}

const reportFor = (date: string): MarketReviewSingleResponse => ({
  report: { meta: { date, date_formatted: date, filename: `${date}.md` }, content: `content-${date}` },
});

describe('marketReviewStore loadContent 竞态守卫', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useMarketReviewStore.setState({
      reports: [], current: null, currentIndex: 0,
      isLoading: true, isLoadingContent: false, isGenerating: false,
      error: null, loaded: false,
    });
  });

  it('快速切换日期时，慢的旧响应不得覆盖新响应', async () => {
    const d1 = deferred();
    const d2 = deferred();
    vi.mocked(marketReviewApi.getByDate)
      .mockImplementationOnce(() => d1.promise)
      .mockImplementationOnce(() => d2.promise);

    const p1 = useMarketReviewStore.getState().loadContent('2026-09-10');
    const p2 = useMarketReviewStore.getState().loadContent('2026-09-11');

    // 新请求先返回
    d2.resolve(reportFor('2026-09-11'));
    await p2;
    expect(useMarketReviewStore.getState().current?.content).toBe('content-2026-09-11');

    // 旧请求后返回 → 应被丢弃
    d1.resolve(reportFor('2026-09-10'));
    await p1;
    expect(useMarketReviewStore.getState().current?.content).toBe('content-2026-09-11');
    expect(useMarketReviewStore.getState().isLoadingContent).toBe(false);
  });

  it('旧请求失败不得污染新请求的结果与错误位', async () => {
    const d1 = deferred();
    const d2 = deferred();
    vi.mocked(marketReviewApi.getByDate)
      .mockImplementationOnce(() => d1.promise)
      .mockImplementationOnce(() => d2.promise);

    const p1 = useMarketReviewStore.getState().loadContent('2026-09-10');
    const p2 = useMarketReviewStore.getState().loadContent('2026-09-11');
    d2.resolve(reportFor('2026-09-11'));
    await p2;

    d1.reject(new Error('network'));
    await p1;
    expect(useMarketReviewStore.getState().current?.content).toBe('content-2026-09-11');
    expect(useMarketReviewStore.getState().error).toBeNull();
  });

  it('单次请求正常写入结果', async () => {
    vi.mocked(marketReviewApi.getByDate).mockResolvedValueOnce(reportFor('2026-09-09'));
    await useMarketReviewStore.getState().loadContent('2026-09-09');
    expect(useMarketReviewStore.getState().current?.content).toBe('content-2026-09-09');
  });
});
