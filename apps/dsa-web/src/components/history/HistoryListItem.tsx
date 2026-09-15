import type React from 'react';
import { Badge } from '../common';
import type { HistoryItem } from '../../types/analysis';
import { getSentimentColor } from '../../types/analysis';
import { formatDateTime } from '../../utils/format';
import { truncateStockName, isStockNameTruncated } from '../../utils/stockName';

const HEAT_STYLES: Record<string, { emoji: string; color: string }> = {
  '热门': { emoji: '🔥', color: '#f59e0b' },
  '活跃': { emoji: '⚡', color: '#eab308' },
  '中性': { emoji: '', color: '#9ca3af' },
  '冷门': { emoji: '❄️', color: '#60a5fa' },
  Hot: { emoji: '🔥', color: '#f59e0b' },
  Active: { emoji: '⚡', color: '#eab308' },
  Neutral: { emoji: '', color: '#9ca3af' },
  Cold: { emoji: '❄️', color: '#60a5fa' },
};

const getTrendTag = (status?: string): { label: string; color: string } | null => {
  if (!status) return null;
  if (status.includes('上升') || status.includes('Up Trend'))
    return { label: status.slice(0, 4), color: 'var(--home-price-up)' };
  if (status.includes('下降') || status.includes('Down Trend'))
    return { label: status.slice(0, 4), color: 'var(--home-price-down)' };
  return { label: status.slice(0, 4), color: '#9ca3af' };
};

interface HistoryListItemProps {
  item: HistoryItem;
  isViewing: boolean; // Indicates if this report is currently being viewed in the right panel
  isChecked: boolean; // Indicates if the checkbox is checked for bulk operations
  isDeleting: boolean;
  onToggleChecked: (recordId: number) => void;
  onClick: (recordId: number) => void;
}

const getOperationBadgeLabel = (advice?: string) => {
  const normalized = advice?.trim();
  if (!normalized) {
    return '情绪';
  }
  if (normalized.includes('减仓')) {
    return '减仓';
  }
  if (normalized.includes('卖')) {
    return '卖出';
  }
  if (normalized.includes('观望') || normalized.includes('等待')) {
    return '观望';
  }
  if (normalized.includes('买') || normalized.includes('布局')) {
    return '买入';
  }
  return normalized.split(/[，。；、\s]/)[0] || '建议';
};

export const HistoryListItem: React.FC<HistoryListItemProps> = ({
  item,
  isViewing,
  isChecked,
  isDeleting,
  onToggleChecked,
  onClick,
}) => {
  const sentimentColor = item.sentimentScore !== undefined ? getSentimentColor(item.sentimentScore) : null;
  const stockName = item.stockName || item.stockCode;
  const isTruncated = isStockNameTruncated(stockName);

  return (
    <div className="flex items-start gap-2 group">
      <div className="pt-5">
        <input
          type="checkbox"
          checked={isChecked}
          onChange={() => onToggleChecked(item.id)}
          disabled={isDeleting}
          className="h-3.5 w-3.5 cursor-pointer rounded border-subtle-hover bg-transparent accent-primary focus:ring-primary/30 disabled:opacity-50"
        />
      </div>
      <button
        type="button"
        onClick={() => onClick(item.id)}
        className={`home-history-item flex-1 text-left p-2.5 group/item ${
          isViewing ? 'home-history-item-selected' : ''
        }`}
      >
        <div className={`flex items-center gap-2.5 relative z-10${isTruncated ? ' group-hover/item:z-20' : ''}`}>
          {sentimentColor && (
            <div
              className="w-1 h-8 rounded-full flex-shrink-0"
              style={{
                backgroundColor: sentimentColor,
                boxShadow: `0 0 10px ${sentimentColor}40`,
              }}
            />
          )}
          <div className="flex-1 min-w-0">
            <div className="flex items-start justify-between gap-2">
              <div className="min-w-0 flex-1">
                <span className="truncate text-sm font-semibold text-foreground tracking-tight">
                  <span className="group-hover/item:hidden">
                    {truncateStockName(stockName)}
                  </span>
                  <span className="hidden group-hover/item:inline">
                    {stockName}
                  </span>
                </span>
              </div>
              {sentimentColor && (
                <Badge
                  variant="default"
                  size="sm"
                  className={`home-history-sentiment-badge shrink-0 shadow-none text-[11px] font-semibold leading-none transition-opacity duration-200${isTruncated ? ' group-hover/item:opacity-80' : ''}`}
                  style={{
                    color: sentimentColor,
                    borderColor: `${sentimentColor}30`,
                    backgroundColor: `${sentimentColor}10`,
                  }}
                >
                  {getOperationBadgeLabel(item.operationAdvice)} {item.sentimentScore}
                </Badge>
              )}
            </div>
            <div className="flex items-center gap-2 mt-1">
              <span className="text-[11px] text-secondary-text font-mono">
                {item.stockCode}
              </span>
              <span className="w-1 h-1 rounded-full bg-subtle-hover" />
              <span className="text-[11px] text-muted-text">
                {formatDateTime(item.createdAt)}
              </span>
            </div>
            {(item.heatLabel || item.trendStatus) && (
              <div className="flex items-center gap-1.5 mt-1.5">
                {item.heatLabel && (
                  <span
                    className="text-[10px] px-1.5 py-0.5 rounded font-medium"
                    style={{
                      color: HEAT_STYLES[item.heatLabel]?.color || '#9ca3af',
                      backgroundColor: `${HEAT_STYLES[item.heatLabel]?.color || '#9ca3af'}10`,
                    }}
                  >
                    {HEAT_STYLES[item.heatLabel]?.emoji} {item.heatLabel}
                  </span>
                )}
                {item.trendStatus && (() => {
                  const tag = getTrendTag(item.trendStatus);
                  return tag ? (
                    <span
                      className="text-[10px] px-1.5 py-0.5 rounded font-medium truncate max-w-[80px]"
                      style={{
                        color: tag.color,
                        backgroundColor: `${tag.color}10`,
                      }}
                    >
                      {tag.label}
                    </span>
                  ) : null;
                })()}
              </div>
            )}
          </div>
        </div>
      </button>
    </div>
  );
};
