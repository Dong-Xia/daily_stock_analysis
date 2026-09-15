import React, { useState } from 'react';
import { Star, Link, Zap, Sparkles, Flame } from 'lucide-react';
import { Card } from '../common/Card';
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

interface Props {
  sectors: HotSectorItem[];
}

export const SectorDetailCards: React.FC<Props> = ({ sectors }) => {
  if (sectors.length === 0) return null;

  const topSectors = [...sectors]
    .sort((a, b) => b.score - a.score)
    .slice(0, 6);

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
      {topSectors.map((sector) => (
        <SectorDetailCard key={sector.name} sector={sector} />
      ))}
    </div>
  );
};

const SectorDetailCard: React.FC<{ sector: HotSectorItem }> = ({ sector }) => {
  const [isEffectExpanded, setIsEffectExpanded] = useState(false);
  const [isCatalystExpanded, setIsCatalystExpanded] = useState(false);

  const related = sector.relatedStocks ?? [];
  const showRelated = related.slice(0, 8);
  const remaining = related.length - 8;

  const effectSummary = sector.effectSummary ?? '';
  const isEffectLong = effectSummary.length > 100;
  const displayedEffect = isEffectExpanded || !isEffectLong
    ? effectSummary
    : `${effectSummary.slice(0, 100)}...`;

  const catalyst = sector.catalyst ?? '';
  const isCatalystLong = catalyst.length > 100;
  const displayedCatalyst = isCatalystExpanded || !isCatalystLong
    ? catalyst
    : `${catalyst.slice(0, 100)}...`;

  return (
    <Card variant="default" padding="md">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-base font-bold text-foreground">{sector.name}</h3>
        <Badge variant="warning">
          <Flame className="h-3 w-3" />
          {sector.limitUpCount}
        </Badge>
      </div>

      {sector.leader && (
        <div className="mb-4">
          <div className="flex items-center gap-1.5 mb-2">
            <Star className="h-3.5 w-3.5 text-cyan" />
            <span className="text-xs font-medium text-secondary-text">核心龙头</span>
          </div>
          <div className="bg-cyan/5 border border-cyan/20 rounded-lg px-3 py-2 flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-foreground">{sector.leader.name}</p>
              <p className="text-xs text-secondary-text font-mono">{sector.leader.code}</p>
            </div>
            {sector.leader.consecutiveLimitUpDays > 0 && (
              <Badge variant="info" size="sm">
                {sector.leader.consecutiveLimitUpDays}连板
              </Badge>
            )}
          </div>
        </div>
      )}

      {related.length > 0 && (
        <div className="mb-4">
          <div className="flex items-center gap-1.5 mb-2">
            <Link className="h-3.5 w-3.5 text-cyan" />
            <span className="text-xs font-medium text-secondary-text">联动标的</span>
          </div>
          <div className="flex flex-wrap gap-1.5">
            {showRelated.map((stock) => (
              <Badge key={stock.code} variant="default" size="sm">
                {stock.name}
              </Badge>
            ))}
            {remaining > 0 && (
              <Badge variant="default" size="sm">
                +{remaining}
              </Badge>
            )}
          </div>
        </div>
      )}

      {effectSummary && (
        <div className="mb-4">
          <div className="flex items-center gap-1.5 mb-2">
            <Zap className="h-3.5 w-3.5 text-cyan" />
            <span className="text-xs font-medium text-secondary-text">效应总结</span>
          </div>
          <div className="text-sm text-secondary-text bg-surface rounded-lg p-3 border border-border/40">
            <p>{displayedEffect}</p>
            {isEffectLong && (
              <button
                type="button"
                onClick={() => setIsEffectExpanded((v) => !v)}
                className="mt-1 text-xs text-cyan hover:underline"
              >
                {isEffectExpanded ? '收起' : '展开'}
              </button>
            )}
          </div>
        </div>
      )}

      {catalyst && (
        <div>
          <div className="flex items-center gap-1.5 mb-2">
            <Sparkles className="h-3.5 w-3.5 text-cyan" />
            <span className="text-xs font-medium text-secondary-text">催化逻辑</span>
          </div>
          <div className="text-sm text-secondary-text bg-surface rounded-lg p-3 border border-border/40">
            <p>{displayedCatalyst}</p>
            {isCatalystLong && (
              <button
                type="button"
                onClick={() => setIsCatalystExpanded((v) => !v)}
                className="mt-1 text-xs text-cyan hover:underline"
              >
                {isCatalystExpanded ? '收起' : '展开'}
              </button>
            )}
          </div>
        </div>
      )}
    </Card>
  );
};
