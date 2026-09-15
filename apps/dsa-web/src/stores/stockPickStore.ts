import { create } from 'zustand';
import { stockPickApi } from '../api/stockPick';
import { getParsedApiError, type ParsedApiError } from '../api/error';
import type {
  HotSectorChainResponse,
  MarketRegimeResponse,
  SectorRotationResponse,
  FundamentalScreenResponse,
  ScreenResponse,
  PositionSizeResponse,
  StopLossResponse,
  RebalanceResponse,
} from '../types/stockPick';

// 各类异步请求的序号守卫：慢的旧响应回来后若已有更新请求，则丢弃其结果
// （与 stockPoolStore.historyRequestSeq 同一范式）
const requestSeq: Record<string, number> = {};
const nextSeq = (key: string): number => {
  requestSeq[key] = (requestSeq[key] ?? 0) + 1;
  return requestSeq[key];
};
const isStale = (key: string, seq: number): boolean => requestSeq[key] !== seq;

interface StockPickState {
  // Step 1: Market Regime
  regimeLoading: boolean;
  regimeError: ParsedApiError | null;
  regimeData: MarketRegimeResponse | null;

  // Step 2: Sector Rotation
  lookbackDays: number;
  rotationLoading: boolean;
  rotationError: ParsedApiError | null;
  rotationData: SectorRotationResponse | null;

  // Step 3: Fundamental Screener
  fundQuarterDate: string;
  fundLoading: boolean;
  fundError: ParsedApiError | null;
  fundData: FundamentalScreenResponse | null;

  // Hot Sector Chain (一键选股)
  hotSectorLoading: boolean;
  hotSectorError: ParsedApiError | null;
  hotSectorData: HotSectorChainResponse | null;

  // Step 4: Stock Screening
  sectorName: string;
  screenLoading: boolean;
  screenError: ParsedApiError | null;
  screenData: ScreenResponse | null;

  // Step 5: Position Sizing
  posStockCode: string;
  posEntryPrice: string;
  posStopLoss: string;
  posAccountEquity: string;
  posRegimeFactor: string;
  posConfidence: string;
  posLoading: boolean;
  posError: ParsedApiError | null;
  posData: PositionSizeResponse | null;

  // Step 6: Stop Loss
  slStockCode: string;
  slEntryPrice: string;
  slCurrentPrice: string;
  slStopPrice: string;
  slLoading: boolean;
  slError: ParsedApiError | null;
  slData: StopLossResponse | null;

  // Step 7: Rebalance
  rebalancePositions: string;
  rebalanceLoading: boolean;
  rebalanceError: ParsedApiError | null;
  rebalanceData: RebalanceResponse | null;

  // Actions
  handleHotSectorChain: () => Promise<void>;
  handleMarketRegime: () => Promise<void>;
  setLookbackDays: (days: number) => void;
  handleRotation: () => Promise<void>;
  setFundQuarterDate: (date: string) => void;
  handleFundamental: () => Promise<void>;
  setSectorName: (name: string) => void;
  handleScreen: () => Promise<void>;
  setPosStockCode: (code: string) => void;
  setPosEntryPrice: (price: string) => void;
  setPosStopLoss: (sl: string) => void;
  setPosAccountEquity: (equity: string) => void;
  setPosRegimeFactor: (factor: string) => void;
  setPosConfidence: (confidence: string) => void;
  handlePositionSize: () => Promise<void>;
  setSlStockCode: (code: string) => void;
  setSlEntryPrice: (price: string) => void;
  setSlCurrentPrice: (price: string) => void;
  setSlStopPrice: (price: string) => void;
  handleStopLoss: () => Promise<void>;
  setRebalancePositions: (positions: string) => void;
  handleRebalance: () => Promise<void>;
}

export const useStockPickStore = create<StockPickState>((set, get) => ({
  // Initial state
  regimeLoading: false,
  regimeError: null,
  regimeData: null,

  lookbackDays: 20,
  rotationLoading: false,
  rotationError: null,
  rotationData: null,

  fundQuarterDate: '',
  fundLoading: false,
  fundError: null,
  fundData: null,

  hotSectorLoading: false,
  hotSectorError: null,
  hotSectorData: null,

  sectorName: '',
  screenLoading: false,
  screenError: null,
  screenData: null,

  posStockCode: '',
  posEntryPrice: '',
  posStopLoss: '',
  posAccountEquity: '',
  posRegimeFactor: '',
  posConfidence: '',
  posLoading: false,
  posError: null,
  posData: null,

  slStockCode: '',
  slEntryPrice: '',
  slCurrentPrice: '',
  slStopPrice: '',
  slLoading: false,
  slError: null,
  slData: null,

  rebalancePositions: '',
  rebalanceLoading: false,
  rebalanceError: null,
  rebalanceData: null,

  // Actions
  handleHotSectorChain: async () => {
    const seq = nextSeq('hotSector');
    set({ hotSectorLoading: true, hotSectorError: null, hotSectorData: null });
    try {
      const data = await stockPickApi.hotSectorChain();
      if (isStale('hotSector', seq)) return;
      set({ hotSectorData: data });
    } catch (err) {
      if (isStale('hotSector', seq)) return;
      set({ hotSectorError: getParsedApiError(err) });
    } finally {
      if (!isStale('hotSector', seq)) set({ hotSectorLoading: false });
    }
  },

  handleMarketRegime: async () => {
    const seq = nextSeq('regime');
    set({ regimeLoading: true, regimeError: null });
    try {
      const data = await stockPickApi.getMarketRegime();
      if (isStale('regime', seq)) return;
      set({ regimeData: data });
    } catch (err) {
      if (isStale('regime', seq)) return;
      set({ regimeError: getParsedApiError(err) });
    } finally {
      if (!isStale('regime', seq)) set({ regimeLoading: false });
    }
  },

  setLookbackDays: (days) => set({ lookbackDays: days }),

  handleRotation: async () => {
    const { lookbackDays } = get();
    const seq = nextSeq('rotation');
    set({ rotationLoading: true, rotationError: null });
    try {
      const data = await stockPickApi.getSectorRotation(lookbackDays);
      if (isStale('rotation', seq)) return;
      set({ rotationData: data });
    } catch (err) {
      if (isStale('rotation', seq)) return;
      set({ rotationError: getParsedApiError(err) });
    } finally {
      if (!isStale('rotation', seq)) set({ rotationLoading: false });
    }
  },

  setFundQuarterDate: (date) => set({ fundQuarterDate: date }),

  handleFundamental: async () => {
    const { fundQuarterDate } = get();
    const seq = nextSeq('fundamental');
    set({ fundLoading: true, fundError: null });
    try {
      const data = await stockPickApi.fundamentalScreen(fundQuarterDate || undefined);
      if (isStale('fundamental', seq)) return;
      set({ fundData: data });
    } catch (err) {
      if (isStale('fundamental', seq)) return;
      set({ fundError: getParsedApiError(err) });
    } finally {
      if (!isStale('fundamental', seq)) set({ fundLoading: false });
    }
  },

  setSectorName: (name) => set({ sectorName: name }),

  handleScreen: async () => {
    const { sectorName } = get();
    if (!sectorName.trim()) return;
    const seq = nextSeq('screen');
    set({ screenLoading: true, screenError: null });
    try {
      let data = await stockPickApi.screenStocks(sectorName.trim(), true);
      if (isStale('screen', seq)) return;  // 等待期间用户已切换板块/重新点击
      if (data.candidates.length === 0) {
        data = await stockPickApi.screenStocks(sectorName.trim(), false);
        if (isStale('screen', seq)) return;
      }
      set({ screenData: data });
    } catch (err) {
      if (isStale('screen', seq)) return;
      set({ screenError: getParsedApiError(err) });
    } finally {
      if (!isStale('screen', seq)) set({ screenLoading: false });
    }
  },

  setPosStockCode: (code) => set({ posStockCode: code }),
  setPosEntryPrice: (price) => set({ posEntryPrice: price }),
  setPosStopLoss: (sl) => set({ posStopLoss: sl }),
  setPosAccountEquity: (equity) => set({ posAccountEquity: equity }),
  setPosRegimeFactor: (factor) => set({ posRegimeFactor: factor }),
  setPosConfidence: (confidence) => set({ posConfidence: confidence }),

  handlePositionSize: async () => {
    const state = get();
    if (!state.posStockCode.trim() || !state.posEntryPrice || !state.posStopLoss || !state.posAccountEquity) return;
    const seq = nextSeq('positionSize');
    set({ posLoading: true, posError: null });
    try {
      const data = await stockPickApi.calculatePositionSize({
        stockCode: state.posStockCode.trim(),
        entryPrice: Number(state.posEntryPrice),
        stopLoss: Number(state.posStopLoss),
        accountEquity: Number(state.posAccountEquity),
        marketRegimeFactor: Number(state.posRegimeFactor) || 1.0,
        signalConfidence: Number(state.posConfidence) || 0.5,
      });
      if (isStale('positionSize', seq)) return;
      set({ posData: data });
    } catch (err) {
      if (isStale('positionSize', seq)) return;
      set({ posError: getParsedApiError(err) });
    } finally {
      if (!isStale('positionSize', seq)) set({ posLoading: false });
    }
  },

  setSlStockCode: (code) => set({ slStockCode: code }),
  setSlEntryPrice: (price) => set({ slEntryPrice: price }),
  setSlCurrentPrice: (price) => set({ slCurrentPrice: price }),
  setSlStopPrice: (price) => set({ slStopPrice: price }),

  handleStopLoss: async () => {
    const state = get();
    if (!state.slStockCode.trim() || !state.slEntryPrice || !state.slCurrentPrice || !state.slStopPrice) return;
    const seq = nextSeq('stopLoss');
    set({ slLoading: true, slError: null });
    try {
      const data = await stockPickApi.evaluateStopLoss({
        stockCode: state.slStockCode.trim(),
        entryPrice: Number(state.slEntryPrice),
        currentPrice: Number(state.slCurrentPrice),
        stopPrice: Number(state.slStopPrice),
      });
      if (isStale('stopLoss', seq)) return;
      set({ slData: data });
    } catch (err) {
      if (isStale('stopLoss', seq)) return;
      set({ slError: getParsedApiError(err) });
    } finally {
      if (!isStale('stopLoss', seq)) set({ slLoading: false });
    }
  },

  setRebalancePositions: (positions) => set({ rebalancePositions: positions }),

  handleRebalance: async () => {
    const { rebalancePositions } = get();
    if (!rebalancePositions.trim()) return;
    const seq = nextSeq('rebalance');
    set({ rebalanceLoading: true, rebalanceError: null });
    try {
      const data = await stockPickApi.rebalance(rebalancePositions.trim());
      if (isStale('rebalance', seq)) return;
      set({ rebalanceData: data });
    } catch (err) {
      if (isStale('rebalance', seq)) return;
      set({ rebalanceError: getParsedApiError(err) });
    } finally {
      if (!isStale('rebalance', seq)) set({ rebalanceLoading: false });
    }
  },
}));
