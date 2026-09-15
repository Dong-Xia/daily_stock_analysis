import React, { useMemo } from 'react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  ResponsiveContainer,
  Cell,
  LabelList,
} from 'recharts';
import { Card } from '../common/Card';

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

interface LimitUpHeatmapProps {
  sectors: HotSectorItem[];
}

function getBarColor(limitUpCount: number): string {
  if (limitUpCount >= 10) return 'hsl(190,100%,50%)';
  if (limitUpCount >= 5) return 'hsl(37,92%,50%)';
  return 'hsl(224,12%,42%)';
}

function truncateName(name: string, maxLength: number): string {
  if (name.length <= maxLength) return name;
  return name.slice(0, maxLength);
}

export const LimitUpHeatmap: React.FC<LimitUpHeatmapProps> = ({ sectors }) => {
  const chartData = useMemo(() => {
    return [...sectors]
      .sort((a, b) => b.limitUpCount - a.limitUpCount)
      .slice(0, 8)
      .map((s) => ({
        ...s,
        shortName: truncateName(s.name, 8),
      }));
  }, [sectors]);

  if (!sectors || sectors.length === 0) {
    return null;
  }

  return (
    <Card variant="default" padding="md" title="涨停热力图">
      <div className="w-full h-[300px]">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart
            data={chartData}
            layout="vertical"
            margin={{ top: 4, right: 24, bottom: 4, left: 4 }}
          >
            <CartesianGrid
              strokeDasharray="3 3"
              stroke="hsl(var(--border))"
              horizontal={false}
            />
            <XAxis
              type="number"
              dataKey="limitUpCount"
              tick={{ fill: 'hsl(var(--secondary-text))', fontSize: 12 }}
              axisLine={{ stroke: 'hsl(var(--border))' }}
              tickLine={{ stroke: 'hsl(var(--border))' }}
            />
            <YAxis
              type="category"
              dataKey="shortName"
              tick={{ fill: 'hsl(var(--secondary-text))', fontSize: 12 }}
              axisLine={{ stroke: 'hsl(var(--border))' }}
              tickLine={{ stroke: 'hsl(var(--border))' }}
              width={80}
            />
            <Bar dataKey="limitUpCount" radius={[0, 4, 4, 0]} barSize={24}>
              <LabelList
                dataKey="limitUpCount"
                position="insideRight"
                fill="hsl(var(--foreground))"
                fontSize={12}
                fontWeight={600}
              />
              {chartData.map((entry, index) => (
                <Cell key={`cell-${index}`} fill={getBarColor(entry.limitUpCount)} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </Card>
  );
};
