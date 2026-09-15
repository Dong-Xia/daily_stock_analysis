import React from 'react';
import {
  BarChart3,
  TrendingUp,
  TrendingDown,
  ArrowUp,
  ArrowDown,
  Flame,
  X,
  Wallet,
} from 'lucide-react';
import { Card } from '../common/Card';
import { StatCard } from '../common/StatCard';
import { cn } from '../../utils/cn';

export interface MarketSentiment {
  indices?: Array<{
    name: string;
    changePct: number;
    value: number;
  }>;
  marketSummary?: {
    upCount?: number;
    downCount?: number;
    limitUpCount?: number;
    limitDownCount?: number;
  };
  capitalFlow?: {
    direction?: string;
    amount?: number;
    unit?: string;
  };
}

interface Props {
  sentiment?: MarketSentiment;
}

function formatIndexChange(changePct: number): string {
  const safe = changePct ?? 0;
  const sign = safe >= 0 ? '+' : '';
  return `${sign}${safe.toFixed(2)}%`;
}

function parseChangeTone(changePct: number): 'success' | 'danger' | 'default' {
  const safe = changePct ?? 0;
  if (safe > 0) return 'danger';
  if (safe < 0) return 'success';
  return 'default';
}

export const MarketOverviewPanel: React.FC<Props> = ({ sentiment }) => {
  if (!sentiment) return null;

  const { indices, marketSummary, capitalFlow } = sentiment;
  const hasIndices = indices && indices.length > 0;
  const hasSummary = marketSummary && Object.keys(marketSummary).length > 0;
  const hasFlow = capitalFlow && Object.keys(capitalFlow).length > 0;

  if (!hasIndices && !hasSummary && !hasFlow) return null;

  return (
    <div className="space-y-3">
      <h2 className="text-sm font-semibold text-foreground flex items-center gap-2">
        <BarChart3 className="h-4 w-4 text-cyan" />
        市场情绪
      </h2>

      {hasIndices && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {indices!.map((idx) => {
            const tone = parseChangeTone(idx.changePct);
            const Icon = (idx.changePct ?? 0) >= 0 ? TrendingUp : TrendingDown;
            return (
              <StatCard
                key={idx.name}
                label={idx.name}
                value={(idx.value ?? 0).toFixed(2)}
                hint={
                  <span
                    className={cn(
                      tone === 'success' && 'text-success',
                      tone === 'danger' && 'text-danger',
                      tone === 'default' && 'text-secondary-text'
                    )}
                  >
                    {formatIndexChange(idx.changePct)}
                  </span>
                }
                icon={<Icon className="h-4 w-4" />}
                tone={tone}
              />
            );
          })}
        </div>
      )}

      {hasSummary && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <StatCard
            label="上涨家数"
            value={marketSummary!.upCount ?? 0}
            icon={<ArrowUp className="h-4 w-4" />}
            tone="success"
          />
          <StatCard
            label="下跌家数"
            value={marketSummary!.downCount ?? 0}
            icon={<ArrowDown className="h-4 w-4" />}
            tone="danger"
          />
          <StatCard
            label="涨停家数"
            value={marketSummary!.limitUpCount ?? 0}
            icon={<Flame className="h-4 w-4" />}
            tone="warning"
          />
          <StatCard
            label="跌停家数"
            value={marketSummary!.limitDownCount ?? 0}
            icon={<X className="h-4 w-4" />}
            tone="danger"
          />
        </div>
      )}

      {hasFlow && (
        <Card
          variant="default"
          padding="sm"
          className={cn(
            'border-l-4',
            capitalFlow!.direction === '流入'
              ? 'border-l-success'
              : 'border-l-danger'
          )}
        >
          <div className="flex items-center gap-2 mb-2">
            <Wallet className="h-4 w-4 text-cyan" />
            <span className="text-sm font-semibold text-foreground">资金流向</span>
          </div>
          <div className="space-y-1">
            <p className="text-sm text-foreground">
              主力资金净{capitalFlow!.direction}
              <span
                className={cn(
                  'font-semibold',
                  capitalFlow!.direction === '流入' ? 'text-danger' : 'text-success'
                )}
              >
                {capitalFlow!.amount ?? 0}
                {capitalFlow!.unit ?? '亿元'}
              </span>
            </p>
          </div>
        </Card>
      )}
    </div>
  );
};
