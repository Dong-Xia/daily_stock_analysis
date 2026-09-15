/**
 * Stock Pick Center type definitions.
 * Aligned with the /api/v1/stocks/* endpoints.
 */

// ============ Market Regime (Step 1) ============

export interface DimensionEvidence {
  dimension: string;
  score: number;
  signal: string;
  detail: string;
}

export interface MarketRegimeResponse {
  regime: string;
  regimeLabel: string;
  confidence: number;
  positionFactor: number;
  recommendation: string;
  evidence: DimensionEvidence[];
}

// ============ Sector Rotation (Step 2) ============

export interface SectorDurabilityItem {
  name: string;
  classificationCn: string;
  consecutiveDays: number;
  top3Count: number;
  top5Count: number;
  scoreTrend: number;
  currentRank: number;
  currentScore: number;
  avgScore: number;
  classification: string;
}

export interface SectorRotationResponse {
  analysisDate: string;
  lookbackDays: number;
  totalRankingDays: number;
  sectors: SectorDurabilityItem[];
  topMainLines: SectorDurabilityItem[];
  risingSectors: SectorDurabilityItem[];
  fadingSectors: SectorDurabilityItem[];
}

// ============ Stock Screening (Step 3) ============

export interface CandidateItem {
  code: string;
  name: string;
  price: number;
  changePct: number;
  maAlignment: string;
  turnoverRate: number;
  factors?: {
    compositeScore?: number;
    trendStrength?: number;
    rsScore?: number;
    volumeConfirmation?: number;
    biasFromMa5?: number;
    limitUpProximity?: number;
    sectorLeadership?: number;
  };
}

export interface ScreenResponse {
  totalConsidered: number;
  afterLiquidity: number;
  afterTrend: number;
  afterRanking: number;
  candidates: CandidateItem[];
  sectorName: string;
}

// ============ Position Sizing (Step 4) ============

export interface PositionSizeRequest {
  stockCode: string;
  entryPrice: number;
  stopLoss: number;
  accountEquity: number;
  marketRegimeFactor: number;
  signalConfidence: number;
}

export interface PositionSizeResponse {
  recommendedShares: number;
  recommendedPct: number;
  maxLoss: number;
  kellyFraction: number;
  rationale: string[];
}

// ============ Stop Loss (Step 5) ============

export interface StopLossRequest {
  stockCode: string;
  entryPrice: number;
  currentPrice: number;
  stopPrice: number;
}

export interface StopEvent {
  type: string;
  triggered: boolean;
  reason: string;
  pnlPct: number;
}

export interface StopLossResponse {
  events: StopEvent[];
}

// ============ Rebalance (Step 6) ============

export interface RankingItem {
  rank: number;
  code: string;
  name: string;
  pnlPct: number;
  rsRatio: number;
  percentile: number;
}

export type SignalType = 'BUY' | 'ADD' | 'HOLD' | 'REDUCE' | 'EXIT' | 'ROTATE';

export interface SignalCard {
  code: string;
  name: string;
  signal: SignalType;
  reason: string;
}

export interface RebalanceResponse {
  rankings: RankingItem[];
  signals: SignalCard[];
}

// ============ Fundamental Screener ============

export interface FundamentalCandidate {
  code: string;
  name: string;
  revenueYoy: number;
  profitYoy: number;
  netProfit: number;
  industry: string;
  announceDate: string;
  compositeScore: number;
}

export interface FundamentalScreenResponse {
  date: string;
  totalStocks: number;
  afterRevenueTest: number;
  afterProfitTest: number;
  afterNetProfitTest: number;
  criteria?: string;
  candidates: FundamentalCandidate[];
}

// ============ Hot Sector Chain (一键选股) ============

export interface HotSectorCandidate {
  code: string;
  name: string;
  price: number;
  changePct: number;
  compositeScore: number;
  maAlignment: string;
  turnoverRate: number;
  avgAmountYi: number;
}

export interface SectorPickResult {
  sectorName: string;
  classification: string;
  classificationCn: string;
  candidates: HotSectorCandidate[];
  success: boolean;
  errorMessage: string;
}

export interface HotSectorChainResponse {
  totalSectors: number;
  succeeded: number;
  failed: number;
  intervalSeconds: number;
  results: SectorPickResult[];
}
