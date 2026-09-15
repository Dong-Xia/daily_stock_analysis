import React, { useState, useMemo } from 'react';
import { Flame, ChevronDown, ChevronUp } from 'lucide-react';
import { cn } from '../../utils/cn';
import { Badge } from '../common/Badge';

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

interface SectorLeaderboardProps {
  sectors: HotSectorItem[];
}

const RANK_STYLES: Record<number, string> = {
  1: 'bg-cyan/20 text-cyan border-cyan/30',
  2: 'bg-purple/20 text-purple border-purple/30',
};

function getRankStyle(rank: number): string {
  return RANK_STYLES[rank] ?? 'bg-elevated text-secondary-text border-border/40';
}

function truncateText(text: string, maxLength: number): string {
  if (text.length <= maxLength) return text;
  return text.slice(0, maxLength);
}

export const SectorLeaderboard: React.FC<SectorLeaderboardProps> = ({ sectors }) => {
  const [expandedIndex, setExpandedIndex] = useState<number | null>(null);

  const topSectors = useMemo(() => {
    return [...sectors].sort((a, b) => b.score - a.score).slice(0, 5);
  }, [sectors]);

  if (!sectors || sectors.length === 0) {
    return null;
  }

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5 gap-3">
      {topSectors.map((sector, index) => {
        const rank = index + 1;
        const isExpanded = expandedIndex === index;
        const catalystText = sector.catalyst ?? '';
        const shouldTruncate = catalystText.length > 60;
        const displayCatalyst = isExpanded ? catalystText : truncateText(catalystText, 60);

        return (
          <div
            key={sector.name}
            className={cn(
              'terminal-card rounded-2xl p-4 flex flex-col gap-3',
              'hover:border-cyan/30 transition-colors cursor-pointer'
            )}
          >
            <div className="flex items-center gap-2">
              <span
                className={cn(
                  'inline-flex items-center justify-center w-6 h-6 rounded-md border text-xs font-bold',
                  getRankStyle(rank)
                )}
              >
                {rank}
              </span>
              <span className="text-base font-bold text-foreground truncate">
                {sector.name}
              </span>
            </div>

            <div className="flex items-center gap-2 flex-wrap">
              <span
                className={cn(
                  'text-lg font-semibold',
                  sector.changePct >= 0 ? 'text-danger' : 'text-success'
                )}
              >
                {sector.changePct >= 0 ? '+' : ''}
                {(sector.changePct ?? 0).toFixed(2)}%
              </span>
              <Badge variant="warning" size="sm">
                <Flame className="w-3 h-3" />
                <span>{sector.limitUpCount}</span>
              </Badge>
            </div>

            {catalystText && (
              <div className="flex-1">
                <p className="text-xs text-secondary-text leading-relaxed">
                  {displayCatalyst}
                  {shouldTruncate && !isExpanded && '…'}
                </p>
                {shouldTruncate && (
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      setExpandedIndex(isExpanded ? null : index);
                    }}
                    className="mt-1 inline-flex items-center gap-0.5 text-xs text-cyan hover:underline"
                  >
                    {isExpanded ? (
                      <>
                        收起 <ChevronUp className="w-3 h-3" />
                      </>
                    ) : (
                      <>
                        展开 <ChevronDown className="w-3 h-3" />
                      </>
                    )}
                  </button>
                )}
              </div>
            )}

            <div className="mt-auto pt-2 border-t border-border/40">
              <span className="text-xs text-muted-text">评分 </span>
              <span className="text-sm text-cyan font-mono">{sector.score}</span>
            </div>
          </div>
        );
      })}
    </div>
  );
};
