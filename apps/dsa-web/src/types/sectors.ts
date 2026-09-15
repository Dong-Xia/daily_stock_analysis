/**
 * Sector-related type definitions
 */

export interface SectorStockItem {
  code: string;
  name: string;
  changePct: number;
  price: number;
  isLimitUp: boolean;
  consecutiveLimitUpDays: number;
}

export interface LimitUpLadderItem {
  days: number;
  stockCode: string;
  stockName: string;
}

export interface RelatedStockItem {
  code: string;
  name: string;
}

export interface HotSectorItem {
  name: string;
  changePct: number;
  limitUpCount: number;
  limitUpStocks: SectorStockItem[];
  ladder: LimitUpLadderItem[];
  leader: SectorStockItem | null;
  leaderCorrelation: number;
  score: number;
  catalyst?: string;
  effectSummary?: string;
  relatedStocks?: RelatedStockItem[];
}

export interface HotSectorsResponse {
  date: string;
  sectors: HotSectorItem[];
  total: number;
  cacheStatus: 'ready' | 'warming_up' | 'empty';
}

export interface SectorRankingItem {
  name: string;
  changePct: number;
}

export interface SectorRankingsResponse {
  market: string;
  top: SectorRankingItem[];
  bottom: SectorRankingItem[];
}

export interface ManualSectorInput {
  text: string;
  date?: string;
}

export interface ManualSectorParseResponse {
  date: string;
  sectors: HotSectorItem[];
  total: number;
  parseInfo?: Record<string, unknown>;
}

export interface ScraperSectorRankingItem {
  code: string;
  name: string;
  changePct: number;
  rankType: string;
  leader: string;
}

export interface ScraperLimitUpItem {
  code: string;
  name: string;
  price: number;
  changePct: number;
  consecutiveDays: number;
  industry: string;
}

export interface ScraperBoardDataResponse {
  date: string;
  sectorRankings: ScraperSectorRankingItem[];
  limitUpPool: ScraperLimitUpItem[];
  sectorStocks: ScraperSectorDetailItem[];
}

export interface ScraperSectorStockItem {
  code: string;
  name: string;
  changePct: number;
  price: number;
}

export interface ScraperSectorDetailItem {
  sectorCode: string;
  sectorName: string;
  sectorChangePct: number;
  limitUpCount: number;
  limitDownCount: number;
  limitUpStocks: ScraperSectorStockItem[];
  limitDownStocks: ScraperSectorStockItem[];
}
