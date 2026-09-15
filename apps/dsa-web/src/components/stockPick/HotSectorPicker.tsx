import type React from 'react';
import { useState, useEffect, useCallback, useRef } from 'react';
import {
  Flame,
  Loader2,
  CheckCircle2,
  XCircle,
  Clock,
} from 'lucide-react';
import { useStockPickStore } from '../../stores/stockPickStore';
import type {
  HotSectorChainResponse,
  SectorPickResult,
} from '../../types/stockPick';
import { Card, Badge, EmptyState } from '../common';
import { cn } from '../../utils/cn';

/* ---------- Sub-components ---------- */

const ProgressRow: React.FC<{
  sector: string;
  label: string;
  status: 'pending' | 'processing' | 'done' | 'error';
  count?: number;
}> = ({ sector, label, status, count }) => {
  const icon = {
    pending: <Clock className="h-3.5 w-3.5 text-secondary-text" />,
    processing: <Loader2 className="h-3.5 w-3.5 animate-spin text-cyan" />,
    done: <CheckCircle2 className="h-3.5 w-3.5 text-success" />,
    error: <XCircle className="h-3.5 w-3.5 text-danger" />,
  }[status];

  const labelClass = {
    pending: 'text-secondary-text',
    processing: 'text-cyan',
    done: 'text-success',
    error: 'text-danger',
  }[status];

  return (
    <div className="flex items-center gap-2 text-xs">
      {icon}
      <span className={cn('flex-1', labelClass)}>
        <span className="font-medium">{label}</span>
        <span className="text-secondary-text ml-1">{sector}</span>
      </span>
      {status === 'done' && count != null && (
        <span className="text-secondary-text">{count} 只精选</span>
      )}
      {status === 'error' && (
        <span className="text-danger">失败</span>
      )}
    </div>
  );
};

/* ---------- Simulation of sequential progress ---------- */

function useSequentialProgress(
  loading: boolean,
  result: HotSectorChainResponse | null,
): {
  stepIndex: number;
  steps: { name: string; label: string; status: 'pending' | 'processing' | 'done' | 'error'; count?: number }[];
} {
  const sectorCount = result?.results.length ?? 5;
  const total = sectorCount;

  // When not loading, derive final step index from complete result
  const derivedIndex = !loading && result
    ? result.results.filter((r) => r.success || !r.success).length
    : 0;

  // Animated progress during loading — all setState calls happen inside async callbacks
  const [animatedIndex, setAnimatedIndex] = useState(0);
  const timersRef = useRef<ReturnType<typeof setTimeout>[]>([]);

  useEffect(() => {
    if (!loading) return;

    const interval = result?.intervalSeconds ?? 8;
    const estimatedPerSector = Math.max(interval, 5) * 1000 + 8000;

    timersRef.current.forEach(clearTimeout);
    timersRef.current = [];

    const tick = (idx: number) => {
      if (idx >= total) return;
      setAnimatedIndex(idx + 1);
      const t = setTimeout(() => tick(idx + 1), estimatedPerSector);
      timersRef.current.push(t);
    };

    const start = setTimeout(() => tick(0), 2000);
    timersRef.current.push(start);

    return () => {
      timersRef.current.forEach(clearTimeout);
      timersRef.current = [];
    };
  }, [loading, result, total]);

  const stepIndex = !loading && result ? derivedIndex : animatedIndex;

  const steps = Array.from({ length: total }, (_, i) => {
    const r: SectorPickResult | undefined = result?.results[i];
    const name = r?.sectorName ?? '';
    const label = r?.classificationCn ?? '';
    const completed = r !== undefined;
    const failed = r && !r.success;
    const count = r?.candidates.length;

    let status: 'pending' | 'processing' | 'done' | 'error';
    if (failed) {
      status = 'error';
    } else if (completed) {
      status = 'done';
    } else if (i < stepIndex) {
      status = 'done';
    } else if (i === stepIndex) {
      status = 'processing';
    } else {
      status = 'pending';
    }

    return { name, label, status, count };
  });

  return { stepIndex, steps };
}

/* ---------- Main Component ---------- */

const HotSectorPicker: React.FC = () => {
  const {
    hotSectorLoading,
    hotSectorError,
    hotSectorData,
    handleHotSectorChain,
    rotationData,
  } = useStockPickStore();

  const [hasRun, setHasRun] = useState(false);

  const hasRotationData = rotationData != null;

  const { steps } = useSequentialProgress(hotSectorLoading, hotSectorData);

  const onPick = useCallback(() => {
    setHasRun(true);
    void handleHotSectorChain();
  }, [handleHotSectorChain]);

  const succeeded = hotSectorData?.succeeded ?? 0;
  const failed = hotSectorData?.failed ?? 0;
  const total = hotSectorData?.totalSectors ?? 0;
  const interval = hotSectorData?.intervalSeconds ?? 8;

  return (
    <div className="rounded-2xl border border-orange-500/20 bg-gradient-to-br from-orange-500/[0.03] to-transparent">
      <div className="p-4 sm:p-5">
        {/* Header */}
        <div className="mb-3 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-orange-500/10 text-orange-500">
              <Flame className="h-4 w-4" />
            </div>
            <h2 className="text-sm font-semibold text-foreground">一键选股</h2>
            <span className="hidden rounded-full border border-border/30 bg-surface/50 px-2 py-0.5 text-[10px] text-secondary-text sm:inline">
              间隔 {interval}s
            </span>
          </div>
          <button
            type="button"
            onClick={onPick}
            disabled={hotSectorLoading || !hasRotationData}
            className="inline-flex h-8 items-center gap-1.5 rounded-lg bg-orange-500 px-3 text-xs font-medium text-white transition-colors hover:bg-orange-600 disabled:cursor-not-allowed disabled:opacity-40"
          >
            {hotSectorLoading ? (
              <>
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
                选股中
              </>
            ) : (
              <>
                <Flame className="h-3.5 w-3.5" />
                热点选股
              </>
            )}
          </button>
        </div>

        {/* Description */}
        <p className="mb-4 text-xs leading-relaxed text-secondary-text">
          从板块锁定结果中自动选取 Top 5 热点板块，逐个筛选优质个股。
          调用间隔 {interval} 秒，避免触发风控。
          {!hasRotationData && (
            <span className="ml-1 text-warning">
              请先执行"步骤 2：板块锁定"获取板块数据。
            </span>
          )}
        </p>

        {/* Progress */}
        {hotSectorLoading && steps.length > 0 && (
          <div className="mb-3 space-y-1.5">
            {steps.map((s, i) => (
              <ProgressRow
                key={i}
                sector={s.name}
                label={s.label}
                status={s.status}
                count={s.count}
              />
            ))}
          </div>
        )}

        {/* Error state */}
        {hotSectorError && (
          <div className="mb-3 rounded-lg border border-warning/20 bg-warning/5 p-3">
            <p className="text-xs text-warning">{hotSectorError.message}</p>
          </div>
        )}

        {/* Result summary */}
        {hotSectorData && !hotSectorLoading && (
          <div className="mb-3 flex items-center gap-3 text-xs">
            <span className="text-secondary-text">
              共 {total} 个板块
            </span>
            {succeeded > 0 && (
              <span className="flex items-center gap-1 text-success">
                <CheckCircle2 className="h-3 w-3" />
                成功 {succeeded}
              </span>
            )}
            {failed > 0 && (
              <span className="flex items-center gap-1 text-danger">
                <XCircle className="h-3 w-3" />
                失败 {failed}
              </span>
            )}
          </div>
        )}

        {/* Sector result cards */}
        {hotSectorData && !hotSectorLoading && hotSectorData.results.length > 0 && (
          <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-3">
            {hotSectorData.results.map((sector, idx) => (
              <SectorResultCard key={idx} sector={sector} />
            ))}
          </div>
        )}

        {/* Empty state when done but no results */}
        {hasRun && !hotSectorLoading && !hotSectorError && !hotSectorData && (
          <EmptyState title="无结果" description="请先完成板块锁定分析。" />
        )}
      </div>
    </div>
  );
};

/* ---------- Sector Result Card ---------- */

const SectorResultCard: React.FC<{ sector: SectorPickResult }> = ({ sector }) => {
  const colorMap: Record<string, string> = {
    '主线': 'text-success',
    '强势轮动': 'text-cyan',
    '轮动': 'text-warning',
  };

  const labelColor = colorMap[sector.classificationCn] ?? 'text-secondary-text';

  if (!sector.success) {
    return (
      <Card variant="bordered" padding="sm">
        <div className="flex items-center gap-2">
          <XCircle className="h-4 w-4 shrink-0 text-danger" />
          <div className="min-w-0 flex-1">
            <p className="text-sm font-medium text-foreground">{sector.sectorName}</p>
            <p className="text-xs text-danger">{sector.errorMessage}</p>
          </div>
        </div>
      </Card>
    );
  }

  if (sector.candidates.length === 0) {
    return (
      <Card variant="bordered" padding="sm">
        <div className="flex items-center gap-2">
          <Clock className="h-4 w-4 shrink-0 text-secondary-text" />
          <div>
            <p className="text-sm font-medium text-foreground">{sector.sectorName}</p>
            <p className="text-xs text-secondary-text">未筛选到符合条件的个股</p>
          </div>
        </div>
      </Card>
    );
  }

  return (
    <Card variant="bordered" padding="sm">
      <div className="mb-2 flex items-center justify-between gap-2">
        <div className="min-w-0 flex-1 truncate">
          <span className="text-sm font-semibold text-foreground">{sector.sectorName}</span>
          <span className={cn('ml-1.5 text-xs font-medium', labelColor)}>
            {sector.classificationCn}
          </span>
        </div>
        <Badge variant="success" className="shrink-0">
          {sector.candidates.length}
        </Badge>
      </div>
      <div className="space-y-1.5">
        {sector.candidates.slice(0, 5).map((c) => {
          const pctColor = c.changePct >= 0 ? 'text-danger' : 'text-success';
          return (
            <div key={c.code} className="flex items-center justify-between rounded-lg bg-surface/30 px-2 py-1.5 text-xs">
              <div className="flex items-center gap-2 min-w-0">
                <span className="font-medium text-foreground">{c.name}</span>
                <span className="text-secondary-text">{c.code}</span>
              </div>
              <div className="flex items-center gap-3 shrink-0">
                <span className={cn('font-medium tabular-nums', pctColor)}>
                  {c.changePct >= 0 ? '+' : ''}{c.changePct.toFixed(2)}%
                </span>
                <span className="font-medium tabular-nums text-cyan">
                  {c.compositeScore.toFixed(1)}
                </span>
              </div>
            </div>
          );
        })}
        {sector.candidates.length > 5 && (
          <p className="text-[10px] text-secondary-text text-center pt-0.5">
            +{sector.candidates.length - 5} 只更多
          </p>
        )}
      </div>
    </Card>
  );
};

export default HotSectorPicker;
