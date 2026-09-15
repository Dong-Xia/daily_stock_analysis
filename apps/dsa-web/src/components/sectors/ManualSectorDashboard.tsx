import React from 'react';
import type { HotSectorItem } from '../../types/sectors';
import type { MarketSentiment } from './MarketOverviewPanel';
import { MarketOverviewPanel } from './MarketOverviewPanel';
import { SectorLeaderboard } from './SectorLeaderboard';
import { LimitUpHeatmap } from './LimitUpHeatmap';
import { LadderVisualization } from './LadderVisualization';
import { SectorDetailCards } from './SectorDetailCards';

interface ParseMeta {
  rawCount?: number;
  validCount?: number;
  marketSentiment?: MarketSentiment;
}

interface Props {
  sectors: HotSectorItem[];
  parseInfo?: ParseMeta;
}

export const ManualSectorDashboard: React.FC<Props> = ({ sectors, parseInfo }) => {
  if (!sectors || sectors.length === 0) {
    return null;
  }

  return (
    <div className="space-y-6">
      <MarketOverviewPanel sentiment={parseInfo?.marketSentiment} />

      <div className="space-y-2">
        <h2 className="text-sm font-semibold text-foreground">涨幅 TOP5 板块</h2>
        <SectorLeaderboard sectors={sectors} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-5 gap-4">
        <div className="lg:col-span-2">
          <LimitUpHeatmap sectors={sectors} />
        </div>
        <div className="lg:col-span-3">
          <LadderVisualization sectors={sectors} />
        </div>
      </div>

      <div className="space-y-2">
        <h2 className="text-sm font-semibold text-foreground">龙头带动效应</h2>
        <SectorDetailCards sectors={sectors} />
      </div>
    </div>
  );
};
