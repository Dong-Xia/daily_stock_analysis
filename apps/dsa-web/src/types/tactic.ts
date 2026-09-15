export interface TripleVolumeCandidate {
  code: string;
  name: string;
  price: number;
  changePct: number;
  turnoverRate: number;
  volume: number;
  volumeRatio: number;
  avgVol5: number;
  ma5: number;
  ma10: number;
  ma20: number;
  openPrice: number;
  closePrice: number;
  range60dPct: number;
  passVolume: boolean;
  passChange: boolean;
  passTurnover: boolean;
  passPosition: boolean;
  passMaAlignment: boolean;
  passSolidYang: boolean;
  score: number;
}

export interface TripleVolumeResult {
  date: string;
  totalScanned: number;
  afterPrescreen: number;
  afterDetailed: number;
  candidates: TripleVolumeCandidate[];
  elapsedSeconds: number;
}
