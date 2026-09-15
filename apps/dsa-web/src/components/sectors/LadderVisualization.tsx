import React from 'react';
import { Card } from '../common/Card';
import { Badge } from '../common/Badge';
import { cn } from '../../utils/cn';

interface HotSectorItem {
  name: string;
  changePct: number;
  limitUpCount: number;
  score: number;
  catalyst?: string;
  effectSummary?: string;
  relatedStocks?: { code: string; name: string }[];
  leader: { name: string; code: string; consecutiveLimitUpDays: number } | null;
  ladder: { days: number; stockCode: string; stockName: string }[];
}

interface Props {
  sectors: HotSectorItem[];
}

export const LadderVisualization: React.FC<Props> = ({ sectors }) => {
  const stockMap = new Map<
    string,
    { days: number; stockName: string; score: number }
  >();

  for (const sector of sectors) {
    for (const item of sector.ladder) {
      const existing = stockMap.get(item.stockCode);
      if (!existing || item.days > existing.days) {
        stockMap.set(item.stockCode, {
          days: item.days,
          stockName: item.stockName,
          score: sector.score,
        });
      } else if (item.days === existing.days && sector.score > existing.score) {
        stockMap.set(item.stockCode, {
          days: item.days,
          stockName: item.stockName,
          score: sector.score,
        });
      }
    }
  }

  if (stockMap.size === 0) return null;

  const rungsMap = new Map<number, { stockCode: string; stockName: string; score: number }[]>();
  for (const [stockCode, data] of stockMap.entries()) {
    const arr = rungsMap.get(data.days) ?? [];
    arr.push({ stockCode, stockName: data.stockName, score: data.score });
    rungsMap.set(data.days, arr);
  }

  const sortedDays = Array.from(rungsMap.keys()).sort((a, b) => b - a);
  const rungs = sortedDays.map((days) => ({
    days,
    stocks: (rungsMap.get(days) ?? []).sort((a, b) => b.score - a.score),
  }));

  return (
    <Card variant="default" padding="md" title="连板梯队" subtitle="市场高度板 → 低位板">
      <div className="space-y-0">
        {rungs.map((rung, rungIndex) => (
          <React.Fragment key={rung.days}>
            {rungIndex > 0 && (
              <div className="w-px h-4 bg-border/40 mx-auto" />
            )}
            <div className="rounded-r-lg">
              <div className="border-l-4 border-cyan pl-3 py-2 bg-cyan/5">
                <p className="text-sm font-semibold text-cyan">
                  {rung.days}连板
                </p>
              </div>
              <div className="flex flex-wrap gap-2 mt-2">
                {rung.stocks.map((stock) => (
                  <div
                    key={stock.stockCode}
                    className={cn(
                      'bg-surface border border-border/40 rounded-lg px-3 py-2',
                      'flex items-center gap-2',
                    )}
                  >
                    <div>
                      <p className="text-sm font-medium text-foreground">
                        {stock.stockName}
                      </p>
                      <p className="text-xs text-secondary-text font-mono">
                        {stock.stockCode}
                      </p>
                    </div>
                    <Badge variant="info" size="sm">
                      {rung.days}板
                    </Badge>
                  </div>
                ))}
              </div>
            </div>
          </React.Fragment>
        ))}
      </div>
    </Card>
  );
};
