import type React from 'react';
import { useCallback, useEffect, useState } from 'react';
import { Calendar, ChevronDown, ChevronUp, Database, Flame, Info, Play, RefreshCw, TrendingUp } from 'lucide-react';
import { sectorsApi } from '../api/sectors';
import { getParsedApiError } from '../api/error';
import type { ParsedApiError } from '../api/error';
import { Card, EmptyState, Tooltip } from '../components/common';
import type { HotSectorItem, SectorStockItem, ScraperBoardDataResponse, ScraperSectorRankingItem, ScraperLimitUpItem, ScraperSectorDetailItem } from '../types/sectors';

type SectorTab = 'auto' | 'scraper';

const SectorsPage: React.FC = () => {
  const [sectors, setSectors] = useState<HotSectorItem[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<ParsedApiError | null>(null);
  const [expandedSector, setExpandedSector] = useState<string | null>(null);
  const [cacheStatus, setCacheStatus] = useState<string>('unknown');
  const [activeTab, setActiveTab] = useState<SectorTab>('auto');
  const [selectedDate, setSelectedDate] = useState<string>('');
  const [availableDates, setAvailableDates] = useState<string[]>([]);
  const [analysisDate, setAnalysisDate] = useState<string>('');
  const [isTriggering, setIsTriggering] = useState(false);
  const [triggerFeedback, setTriggerFeedback] = useState<string | null>(null);
  const [scraperData, setScraperData] = useState<ScraperBoardDataResponse | null>(null);
  const [scraperLoading, setScraperLoading] = useState(false);
  const [scraperError, setScraperError] = useState<string | null>(null);
  const [scraperTriggering, setScraperTriggering] = useState(false);
  const [scraperFeedback, setScraperFeedback] = useState<string | null>(null);

  const loadAvailableDates = useCallback(async () => {
    try {
      const dates = await sectorsApi.getAvailableDates();
      setAvailableDates(dates);
    } catch {
      // 无预计算数据时静默处理
    }
  }, []);

  const loadSectors = useCallback(async (date?: string) => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await sectorsApi.getHotSectors({
        market: 'cn',
        limit: 20,
        minLimitUp: 1,
        date: date || undefined,
      });
      setSectors(data.sectors);
      setCacheStatus(data.cacheStatus || 'unknown');
      setAnalysisDate(data.date || '');
    } catch (err) {
      const parsed = getParsedApiError(err);
      setError(parsed);
    } finally {
      setIsLoading(false);
    }
  }, []);

  const triggerAnalysis = useCallback(async () => {
    setIsTriggering(true);
    setTriggerFeedback(null);
    try {
      const data = await sectorsApi.triggerAnalysis();
      setSectors(data.sectors);
      setCacheStatus(data.cacheStatus || 'unknown');
      setAnalysisDate(data.date || '');
      setTriggerFeedback('分析完成，数据已更新');
      void loadAvailableDates();
    } catch (err) {
      const parsed = getParsedApiError(err);
      setTriggerFeedback(parsed.message || '触发分析失败，请稍后重试');
    } finally {
      setIsTriggering(false);
    }
  }, [loadAvailableDates]);

  const loadScraperData = useCallback(async (date?: string) => {
    setScraperLoading(true);
    setScraperError(null);
    try {
      const data = await sectorsApi.getScraperBoardData({ date: date || undefined });
      setScraperData(data);
    } catch (err) {
      const parsed = getParsedApiError(err);
      setScraperError(parsed.message || '获取爬虫数据失败');
    } finally {
      setScraperLoading(false);
    }
  }, []);

  const triggerScraper = useCallback(async () => {
    setScraperTriggering(true);
    setScraperFeedback(null);
    setScraperError(null);
    try {
      const data = await sectorsApi.triggerScraper();
      setScraperData(data);
      setScraperFeedback(`采集完成（${data.date}）`);
    } catch (err) {
      const parsed = getParsedApiError(err);
      setScraperError(parsed.message || '爬虫采集失败');
    } finally {
      setScraperTriggering(false);
    }
  }, []);

  const loadScraperDates = useCallback(async () => {
    try {
      const dates = await sectorsApi.getScraperAvailableDates();
      setAvailableDates((prev) => [...new Set([...prev, ...dates])].sort().reverse());
    } catch {
      // silent — no scraper data yet
    }
  }, []);

  useEffect(() => {
    document.title = '热点 - DSA';
    void loadAvailableDates();
    void loadSectors();
  }, [loadSectors, loadAvailableDates]);

  useEffect(() => {
    if (!triggerFeedback) return;
    const timer = setTimeout(() => setTriggerFeedback(null), 4000);
    return () => clearTimeout(timer);
  }, [triggerFeedback]);

  useEffect(() => {
    if (!scraperFeedback) return;
    const timer = setTimeout(() => setScraperFeedback(null), 4000);
    return () => clearTimeout(timer);
  }, [scraperFeedback]);

  const toggleExpand = (name: string) => {
    setExpandedSector((prev) => (prev === name ? null : name));
  };

  const isNetworkError = error && (error.status == null || error.status >= 500);

  return (
    <div className="min-h-screen space-y-4 p-4 md:p-6">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div className="flex items-center gap-2">
          <Flame className="h-5 w-5 text-cyan" />
          <h1 className="text-xl font-semibold text-foreground">热点板块分析</h1>
          {cacheStatus === 'pre_computed' && (
            <span className="rounded-full bg-cyan/10 px-2 py-0.5 text-xs text-cyan">
              预计算
            </span>
          )}
          {cacheStatus === 'realtime_fallback' && (
            <span className="rounded-full bg-amber-500/10 px-2 py-0.5 text-xs text-amber-500">
              实时
            </span>
          )}
        </div>
      </div>

      <div className="flex gap-1 rounded-xl border border-border/40 bg-card/50 p-1">
        <button
          type="button"
          onClick={() => setActiveTab('auto')}
          className={`flex-1 rounded-lg px-4 py-1.5 text-sm font-medium transition-colors ${activeTab === 'auto' ? 'bg-cyan/10 text-cyan' : 'text-secondary-text hover:text-foreground'}`}
        >
          自动分析
        </button>
        <button
          type="button"
          onClick={() => { setActiveTab('scraper'); if (!scraperData) void loadScraperData(); void loadScraperDates(); }}
          className={`flex-1 rounded-lg px-4 py-1.5 text-sm font-medium transition-colors ${activeTab === 'scraper' ? 'bg-cyan/10 text-cyan' : 'text-secondary-text hover:text-foreground'}`}
        >
          <span className="flex items-center justify-center gap-1.5">
            <Database className="h-3.5 w-3.5" />
            爬虫快照
          </span>
        </button>
      </div>

      {activeTab === 'auto' && (<>
        <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="flex flex-col gap-1">
          <span className="label-uppercase text-xs inline-flex items-center gap-1.5">
             基于 AI 分析的热点板块，自动识别龙头与连板梯队
             <Tooltip
              contentClassName="max-w-[28rem]"
              content={
                <div className="space-y-2">
                  <p className="font-medium">热点板块筛选原理</p>
                  <p>系统自动拉取全市场板块排行数据，对每个板块进行四步分析：</p>
                  <div className="space-y-3">
                    <div>
                      <span className="inline-flex items-center justify-center w-4.5 h-4.5 rounded bg-primary/15 text-primary text-[10px] font-bold mr-1">1</span>
                      <span className="font-medium">涨停识别</span>
                      <div className="text-xs space-y-1 pl-5 mt-1">
                        <p>获取板块内全部成分股的实时行情，逐个计算涨停阈值（A 股主板 ±10%、科创板/创业板 ±20%、北交所 ±30%、ST ±5%），</p>
                        <p>精确判定每只成分股是否触及涨停价。仅统计真正涨停的个股，不包含冲高回落或未封板的股票。</p>
                      </div>
                    </div>
                    <div className="border-t border-border/20 pt-2">
                      <span className="inline-flex items-center justify-center w-4.5 h-4.5 rounded bg-primary/15 text-primary text-[10px] font-bold mr-1">2</span>
                      <span className="font-medium">连板梯队</span>
                      <div className="text-xs space-y-1 pl-5 mt-1">
                        <p>向前回溯 20 个交易日，统计每只涨停股的连续涨停天数。如果某股今日涨停且昨日也涨停，连板数 +1。</p>
                        <p>将涨停股按连板数分组：高位板（≥3板）、中位板（2板）、首板。梯队完整性 = 不同连板层级的数量。</p>
                      </div>
                    </div>
                    <div className="border-t border-border/20 pt-2">
                      <span className="inline-flex items-center justify-center w-4.5 h-4.5 rounded bg-primary/15 text-primary text-[10px] font-bold mr-1">3</span>
                      <span className="font-medium">龙头识别与带动效应</span>
                      <div className="space-y-3 mt-1 pl-5">
                        <div>
                          <p className="text-[11px] font-semibold text-cyan mb-1">▸ 龙头判定</p>
                          <div className="text-xs space-y-1">
                            <p>公式：<span className="font-mono text-[11px]">连板天数 × 0.5 + 筹码质量分 × 0.5</span>，综合排序选出龙头。</p>
                            <p>不再是"谁板多谁是龙头"的老思路。筹码干净、无套牢盘、趋势结构好的低位票，即使连板数少，也可能被判定为真龙头。</p>
                            <p>最优候选筹码 &lt;20 分时，自动降级选第二候选。</p>
                          </div>
                        </div>
                        <div className="border-t border-border/20 pt-2">
                          <p className="text-[11px] font-semibold text-cyan mb-1">▸ 筹码质量四维评分</p>
                          <div className="text-xs space-y-0.5">
                            <div className="flex gap-2"><span className="text-cyan shrink-0">浮筹</span><span>(30分) 近期缩量 + 窄幅震荡 → 筹码干净，拉升阻力小</span></div>
                            <div className="flex gap-2"><span className="text-cyan shrink-0">稳定</span><span>(25分) 波动率低 + 站上均线 → 持股信心强</span></div>
                            <div className="flex gap-2"><span className="text-cyan shrink-0">爆炒</span><span>(25分) 近60日涨幅小 → 无大量获利盘</span></div>
                            <div className="flex gap-2"><span className="text-cyan shrink-0">趋势</span><span>(20分) 均线多头排列 → 筹码锁定好</span></div>
                          </div>
                        </div>
                        <div className="border-t border-border/20 pt-2">
                          <p className="text-[11px] font-semibold text-purple mb-1">▸ 带动效应计算</p>
                          <div className="text-xs space-y-1">
                            <p>取龙头 + 板块内前 8 只成分股，拉取最近 14 个交易日的日涨跌幅，按日期对齐后计算斯皮尔曼秩相关系数，取所有有效值的平均值。</p>
                            <div className="space-y-0.5">
                              <p><span className="text-danger font-medium">≥ 0.8</span> — 强正相关，联动紧密</p>
                              <p><span className="text-warning font-medium">0.3 ~ 0.8</span> — 中等相关</p>
                              <p><span className="text-secondary-text font-medium">0 ~ 0.3</span> — 弱相关</p>
                              <p><span className="text-muted-text font-medium">&lt; 0</span> — 负相关，不计入评分</p>
                            </div>
                            <p>评分贡献：<span className="font-mono text-[11px]">max(0, 系数) × 15.0</span></p>
                          </div>
                        </div>
                      </div>
                    </div>
                    <div className="border-t border-border/20 pt-2">
                      <span className="inline-flex items-center justify-center w-4.5 h-4.5 rounded bg-primary/15 text-primary text-[10px] font-bold mr-1">4</span>
                      <span className="font-medium">综合评分</span>
                      <div className="text-xs space-y-1 pl-5 mt-1">
                        <p className="font-mono text-[11px]">score = 板块涨幅×2.0 + 涨停家数×5.0 + 梯队完整性×8.0 + 龙头带动×15.0</p>
                        <p>龙头带动效应权重最高（15x），因为龙头是板块持续性的核心指标。</p>
                        <p>涨停家数≥3 才能入选热点板块，避免把零星涨停的板块误判为热点。</p>
                      </div>
                    </div>
                    <div className="border-t border-border/20 pt-2">
                      <p className="text-[11px] text-secondary-text leading-relaxed">
                        <strong>数据来源</strong>：板块排行通过 AkShare → Tushare → efinance 三级回退链获取；成分股行情优先使用缓存（6 小时有效），过期自动刷新。每日 18:00 定时预计算，也可手动触发"立即分析"。
                      </p>
                    </div>
                  </div>
                </div>
              }
              side="bottom"
            >
              <span className="inline-flex h-5 w-5 cursor-help items-center justify-center rounded-full border border-border/60 text-xs font-bold text-cyan hover:border-cyan hover:bg-cyan/10 hover:text-cyan">
                <Info className="h-3.5 w-3.5" />
              </span>
            </Tooltip>
          </span>
          <p className="text-[11px] text-secondary-text/70 leading-relaxed">
            热点板块是<strong className="text-secondary-text">"今天谁在涨"</strong>的探测器，锁定板块是<strong className="text-secondary-text">"谁能持续涨"</strong>的筛选器。
            热点提供排行榜素材，<span className="text-cyan/70">板块轮动分析</span>站在多日数据上把主线从噪音中分离出来。
          </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <div className="flex items-center gap-1.5 rounded-lg border border-border/40 bg-card/50 px-2.5 py-1.5">
            <Calendar className="h-3.5 w-3.5 text-secondary-text" />
            <select
              value={selectedDate}
              onChange={(e) => {
                const d = e.target.value;
                setSelectedDate(d);
                void loadSectors(d || undefined);
              }}
              className="bg-transparent text-sm text-foreground outline-none"
            >
              <option value="">最近数据</option>
              {availableDates.map((d) => (
                <option key={d} value={d}>{d}</option>
              ))}
            </select>
          </div>
          <button
            type="button"
            onClick={() => void loadSectors(selectedDate || undefined)}
            disabled={isLoading || isTriggering}
            className="btn-primary h-8 px-3 text-xs"
          >
            {isLoading ? (
              <span className="flex items-center gap-1.5">
                <RefreshCw className="h-3.5 w-3.5 animate-spin" />
              </span>
            ) : '刷新'}
          </button>
          <button
            type="button"
            onClick={() => void triggerAnalysis()}
            disabled={isTriggering || isLoading}
            className="btn-primary h-8 px-3 text-xs"
          >
            {isTriggering ? (
              <span className="flex items-center gap-1.5">
                <RefreshCw className="h-3.5 w-3.5 animate-spin" />
                分析中
              </span>
            ) : (
              <span className="flex items-center gap-1.5">
                <Play className="h-3 w-3" />
                立即分析
              </span>
            )}
          </button>
        </div>
      </div>

      {triggerFeedback && (
        <div className={`rounded-lg px-4 py-2.5 text-sm transition-opacity duration-300 ${triggerFeedback.startsWith('分析完成') ? 'bg-success/10 text-success' : 'bg-warning/10 text-warning'}`}>
          {triggerFeedback}
        </div>
      )}

      {error && (
        <div className="rounded-xl border border-warning/20 bg-warning/5 p-4">
          <div className="flex items-start gap-3">
            <div className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-warning/10 text-warning">
              <RefreshCw className="h-4 w-4" />
            </div>
            <div className="min-w-0 flex-1">
              <p className="text-sm font-medium text-foreground">
                {isNetworkError ? '数据源繁忙，请稍后重试' : '请求失败'}
              </p>
              <p className="mt-1 text-xs text-secondary-text">
                {isNetworkError
                  ? '当前数据源（东方财富）请求受限，这是临时性问题。您可以稍后重试，或在交易时间（9:30-15:00）访问以获得更稳定的体验。'
                  : error.message}
              </p>
              <button
                type="button"
                onClick={() => void loadSectors(selectedDate || undefined)}
                disabled={isLoading}
                className="btn-primary mt-3 h-8 px-3 text-xs"
              >
                {isLoading ? '重试中...' : '重新加载'}
              </button>
            </div>
          </div>
        </div>
      )}

      {isLoading && sectors.length === 0 && !error && (
        <div className="flex min-h-[200px] flex-col items-center justify-center gap-3">
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-cyan/20 border-t-cyan" />
          <p className="text-xs text-secondary-text">正在分析热点板块...</p>
        </div>
      )}

      {!isLoading && sectors.length === 0 && !error && (
        cacheStatus === 'warming_up' || cacheStatus === 'empty' ? (
          <div className="flex min-h-[200px] flex-col items-center justify-center gap-3 rounded-xl border border-border/40 bg-surface p-6">
            <div className="h-8 w-8 animate-spin rounded-full border-2 border-cyan/20 border-t-cyan" />
            <p className="text-sm font-medium text-foreground">数据准备中</p>
            <p className="text-xs text-secondary-text">
              首次加载正在预拉取板块数据，约需 1-2 分钟。请稍后再试。
            </p>
              <button
                type="button"
                onClick={() => void loadSectors(selectedDate || undefined)}
                disabled={isLoading}
                className="btn-primary h-8 px-3 text-xs"
              >
                刷新
              </button>
            </div>
          ) : (
            <EmptyState
              title="暂无热点板块"
              description="当前未检测到满足条件的热点板块，请稍后刷新或调整筛选条件。"
            />
          )
        )}
      </div>

      {sectors.length > 0 && analysisDate && (
        <p className="text-xs text-secondary-text">
          分析日期：{analysisDate}
          {cacheStatus === 'pre_computed' && '（预计算数据）'}
        </p>
      )}

      <div className="grid grid-cols-1 gap-3">
        {sectors.map((sector) => (
          <SectorCard
            key={sector.name}
            sector={sector}
            isExpanded={expandedSector === sector.name}
            onToggle={() => toggleExpand(sector.name)}
          />
        ))}
      </div>
      </>)}

      {activeTab === 'scraper' && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <p className="text-xs text-secondary-text">
              爬虫采集的原始板块数据，用于自行复盘分析
            </p>
            <div className="flex items-center gap-2">
              <div className="flex items-center gap-1.5 rounded-lg border border-border/40 bg-card/50 px-2.5 py-1.5">
                <Calendar className="h-3.5 w-3.5 text-secondary-text" />
                <select
                  value={selectedDate}
                  onChange={(e) => {
                    const d = e.target.value;
                    setSelectedDate(d);
                    void loadScraperData(d || undefined);
                  }}
                  className="bg-transparent text-sm text-foreground outline-none"
                >
                  <option value="">最近数据</option>
                  {availableDates.map((d) => (
                    <option key={d} value={d}>{d}</option>
                  ))}
                </select>
              </div>
              <button
                type="button"
                onClick={() => void loadScraperData(selectedDate || undefined)}
                disabled={scraperLoading || scraperTriggering}
                className="btn-primary h-8 px-3 text-xs"
              >
                {scraperLoading ? (
                  <span className="flex items-center gap-1.5">
                    <RefreshCw className="h-3 w-3 animate-spin" />
                    加载中
                  </span>
                ) : '刷新'}
              </button>
              <button
                type="button"
                onClick={() => void triggerScraper()}
                disabled={scraperTriggering || scraperLoading}
                className="btn-primary h-8 px-3 text-xs"
              >
                {scraperTriggering ? (
                  <span className="flex items-center gap-1.5">
                    <RefreshCw className="h-3 w-3 animate-spin" />
                    采集中...
                  </span>
                ) : (
                  <span className="flex items-center gap-1.5">
                    <Database className="h-3 w-3" />
                    立即采集
                  </span>
                )}
              </button>
            </div>
          </div>

          {scraperFeedback && (
            <div className="rounded-lg bg-success/10 px-4 py-2.5 text-sm text-success transition-opacity duration-300">
              {scraperFeedback}
            </div>
          )}

          {scraperLoading && (
            <div className="flex min-h-[200px] flex-col items-center justify-center gap-3">
              <div className="h-8 w-8 animate-spin rounded-full border-2 border-cyan/20 border-t-cyan" />
              <p className="text-xs text-secondary-text">加载爬虫数据...</p>
            </div>
          )}

          {scraperError && (
            <div className="rounded-xl border border-warning/20 bg-warning/5 p-4">
              <p className="text-sm font-medium text-foreground">加载失败</p>
              <p className="mt-1 text-xs text-secondary-text">{scraperError}</p>
              <button
                type="button"
                onClick={() => void loadScraperData()}
                disabled={scraperLoading}
                className="btn-primary mt-3 h-8 px-3 text-xs"
              >
                重试
              </button>
            </div>
          )}

          {!scraperLoading && !scraperError && !scraperData && (
            <EmptyState
              title="暂无爬虫数据"
              description="请先启用 Playwright 爬虫并运行一次采集。设置 ENABLE_BOARD_SCRAPER=true 或在定时任务中触发。"
            />
          )}

          {scraperData && (
            <>
              <p className="text-xs text-secondary-text">
                数据日期：{scraperData.date}
                <span className="ml-2 rounded bg-cyan/10 px-1.5 py-0.5 text-[10px] text-cyan">爬虫原始数据</span>
              </p>

              <ScraperSectorTable sectors={scraperData.sectorRankings} sectorStocks={scraperData.sectorStocks} />
              <ScraperLimitUpTable stocks={scraperData.limitUpPool} />
            </>
          )}
        </div>
      )}
    </div>
  );
};

const SectorCard: React.FC<{
  sector: HotSectorItem;
  isExpanded: boolean;
  onToggle: () => void;
}> = ({ sector, isExpanded, onToggle }) => {
  const changeColor = sector.changePct >= 0 ? 'text-danger' : 'text-success';
  const leader = sector.leader;

  return (
    <Card variant="default" padding="md">
      <div
        className="flex cursor-pointer items-center justify-between"
        onClick={onToggle}
        role="button"
        tabIndex={0}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            onToggle();
          }
        }}
      >
        <div className="flex items-center gap-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-cyan/10 text-cyan">
            <TrendingUp className="h-5 w-5" />
          </div>
          <div>
            <p className="text-sm font-semibold text-foreground">{sector.name}</p>
            <p className="text-xs text-secondary-text">
              涨停 {sector.limitUpCount} 家
              {leader && ` | 龙头: ${leader.name}(${leader.consecutiveLimitUpDays}连板)`}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <span className={`text-sm font-bold ${changeColor}`}>
            {sector.changePct >= 0 ? '+' : ''}
            {sector.changePct.toFixed(2)}%
          </span>
          <span className="text-xs font-medium text-secondary-text">
            score: {sector.score.toFixed(1)}
          </span>
          {isExpanded ? (
            <ChevronUp className="h-4 w-4 text-secondary-text" />
          ) : (
            <ChevronDown className="h-4 w-4 text-secondary-text" />
          )}
        </div>
      </div>

      {isExpanded && (
        <div className="mt-4 space-y-4 border-t border-border/40 pt-4">
          {sector.ladder.length > 0 && (
            <div>
              <p className="mb-2 text-xs font-medium text-secondary-text">连板梯队</p>
              <div className="flex flex-wrap gap-2">
                {sector.ladder.map((rung) => (
                  <span
                    key={rung.stockCode}
                    className="inline-flex items-center rounded-lg bg-cyan/10 px-2 py-1 text-xs font-medium text-cyan"
                  >
                    {rung.stockName} ({rung.days}板)
                  </span>
                ))}
              </div>
            </div>
          )}

          {leader && (
            <div className="flex items-center gap-2 text-xs text-secondary-text">
              <span>龙头带动效应:</span>
              <Tooltip
                contentClassName="max-w-[22rem]"
                content={
                  <div className="space-y-2">
                    <p className="font-medium">龙头带动效应</p>
                    <p className="text-xs">衡量龙头股涨跌对板块内其他个股的带动能力。</p>
                    <div className="text-xs space-y-1.5">
                      <p><strong>算法</strong>：取龙头 + 板块内前 8 只成分股，拉取最近 14 个交易日的日涨跌幅，按日期对齐后计算斯皮尔曼秩相关系数，取所有有效值的均值。</p>
                      <p><strong>为什么用斯皮尔曼</strong>：涨停/跌停等极端值会严重干扰皮尔逊相关，斯皮尔曼只看涨跌排名顺序，不受极端值影响。</p>
                      <div className="border-t border-border/20 pt-2 space-y-1">
                        <p><span className="text-danger font-medium">≥ 0.8</span> — 强正相关，龙头涨板块跟涨，联动紧密</p>
                        <p><span className="text-warning font-medium">0.3 ~ 0.8</span> — 中等相关，有一定带动效应</p>
                        <p><span className="text-secondary-text font-medium">0 ~ 0.3</span> — 弱相关，龙头对板块带动不明显</p>
                        <p><span className="text-muted-text font-medium">&lt; 0</span> — 负相关，不计入评分</p>
                      </div>
                      <div className="border-t border-border/20 pt-2">
                        <p className="text-[11px] text-secondary-text">评分贡献：<span className="font-mono">max(0, 系数) × 15.0</span>，是评分公式中权重最高的单项。</p>
                      </div>
                    </div>
                  </div>
                }
                side="top"
              >
                <span className="font-medium text-foreground cursor-help border-b border-dotted border-foreground/30 hover:border-cyan">
                  {sector.leaderCorrelation.toFixed(3)}
                </span>
              </Tooltip>
            </div>
          )}

          {sector.limitUpStocks.length > 0 && (
            <div>
              <p className="mb-2 text-xs font-medium text-secondary-text">板块内个股</p>
              <div className="overflow-x-auto">
                <table className="w-full text-xs">
                  <thead className="border-b border-border/40 text-secondary-text">
                    <tr>
                      <th className="py-1.5 pr-2 text-left">代码</th>
                      <th className="py-1.5 pr-2 text-left">名称</th>
                      <th className="py-1.5 pr-2 text-right">涨跌幅</th>
                      <th className="py-1.5 pr-2 text-right">最新价</th>
                      <th className="py-1.5 text-right">连板</th>
                    </tr>
                  </thead>
                  <tbody>
                    {sector.limitUpStocks.map((stock) => (
                      <StockRow key={stock.code} stock={stock} />
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      )}
    </Card>
  );
};

const ScraperSectorTable: React.FC<{
  sectors: ScraperSectorRankingItem[];
  sectorStocks: ScraperSectorDetailItem[];
}> = ({ sectors, sectorStocks }) => {
  const topSectors = sectors.filter((s) => s.rankType === 'top');
  const bottomSectors = sectors.filter((s) => s.rankType === 'bottom');
  const bottomAllPositive = bottomSectors.length > 0 && bottomSectors.every((s) => (s.changePct ?? 0) >= 0);

  // Build lookup: sector_code → detail
  const detailByCode: Record<string, ScraperSectorDetailItem> = {};
  for (const d of sectorStocks) {
    detailByCode[d.sectorCode] = d;
  }
  const detailByName: Record<string, ScraperSectorDetailItem> = {};
  for (const d of sectorStocks) {
    detailByName[d.sectorName] = d;
  }

  const renderSectorRow = (s: ScraperSectorRankingItem) => {
    const detail = detailByCode[s.code] || detailByName[s.name];
    const luStocks = detail?.limitUpStocks || [];
    const ldStocks = detail?.limitDownStocks || [];
    const luNames = luStocks.map((x) => x.name).join('、');
    const ldNames = ldStocks.map((x) => x.name).join('、');

    return (
      <tr key={s.code || s.name} className="border-b border-border/20 hover:bg-surface/50">
        <td className="py-1.5 pr-2 text-foreground">{s.code}</td>
        <td className="py-1.5 pr-2">
          <span className="text-foreground">{s.name}</span>
          {luStocks.length > 0 && (
            <span title={luNames} className="ml-1.5 rounded bg-danger/10 px-1 py-0.5 text-[10px] font-medium text-danger">
              涨停{luStocks.length}
            </span>
          )}
          {ldStocks.length > 0 && (
            <span title={ldNames} className="ml-1 rounded bg-success/10 px-1 py-0.5 text-[10px] font-medium text-success">
              跌停{ldStocks.length}
            </span>
          )}
        </td>
        <td className={`py-1.5 pr-2 text-right ${s.changePct >= 0 ? 'text-danger' : 'text-success'}`}>
          {s.changePct >= 0 ? '+' : ''}{s.changePct.toFixed(2)}%
        </td>
        <td className="py-1.5 text-secondary-text text-xs">{s.leader || '-'}</td>
      </tr>
    );
  };

  return (
    <div className="rounded-xl border border-border/40 bg-surface p-4">
      <h3 className="mb-3 flex items-center gap-2 text-sm font-semibold text-foreground">
        <TrendingUp className="h-4 w-4 text-cyan" />
        板块涨跌榜
        <span className="rounded bg-cyan/10 px-1.5 py-0.5 text-[10px] text-cyan">{sectors.length} 个板块</span>
      </h3>

      {topSectors.length > 0 && (
        <div className="mb-4">
          <p className="mb-2 text-xs font-medium text-danger">领涨板块</p>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead className="border-b border-border/40 text-secondary-text">
                <tr>
                  <th className="py-1.5 pr-2 text-left">代码</th>
                  <th className="py-1.5 pr-2 text-left">名称</th>
                  <th className="py-1.5 pr-2 text-right">涨跌幅</th>
                  <th className="py-1.5 pr-2 text-left">领涨股</th>
                </tr>
              </thead>
              <tbody>
                {topSectors.map((s) => renderSectorRow(s))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {bottomSectors.length > 0 && (
        <div>
          <p className={`mb-2 text-xs font-medium ${bottomAllPositive ? 'text-danger' : 'text-success'}`}>
            {bottomAllPositive ? '涨幅靠后' : '领跌板块'}
          </p>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead className="border-b border-border/40 text-secondary-text">
                <tr>
                  <th className="py-1.5 pr-2 text-left">代码</th>
                  <th className="py-1.5 pr-2 text-left">名称</th>
                  <th className="py-1.5 pr-2 text-right">涨跌幅</th>
                  <th className="py-1.5 pr-2 text-left">领涨股</th>
                </tr>
              </thead>
              <tbody>
                {bottomSectors.map((s) => renderSectorRow(s))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
};

const ScraperLimitUpTable: React.FC<{ stocks: ScraperLimitUpItem[] }> = ({ stocks }) => {
  const [showAll, setShowAll] = useState(false);
  const displayStocks = showAll ? stocks : stocks.slice(0, 20);
  const highLadder = stocks.filter((s) => s.consecutiveDays >= 3);

  return (
    <div className="rounded-xl border border-border/40 bg-surface p-4">
      <h3 className="mb-3 flex items-center gap-2 text-sm font-semibold text-foreground">
        <Database className="h-4 w-4 text-cyan" />
        涨停板池
        <span className="rounded bg-cyan/10 px-1.5 py-0.5 text-[10px] text-cyan">{stocks.length} 只</span>
      </h3>

      {highLadder.length > 0 && (
        <div className="mb-4 rounded-lg bg-danger/5 p-3">
          <p className="mb-2 text-xs font-medium text-danger">
            高连板关注（{'\u2265'}3板）
          </p>
          <div className="flex flex-wrap gap-2">
            {highLadder.map((s) => (
              <span
                key={s.code}
                className="inline-flex items-center rounded-lg bg-danger/10 px-2 py-1 text-xs font-medium text-danger"
              >
                {s.name} ({s.consecutiveDays}板)
              </span>
            ))}
          </div>
        </div>
      )}

      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead className="border-b border-border/40 text-secondary-text">
            <tr>
              <th className="py-1.5 pr-2 text-left">代码</th>
              <th className="py-1.5 pr-2 text-left">名称</th>
              <th className="py-1.5 pr-2 text-right">最新价</th>
              <th className="py-1.5 pr-2 text-right">涨跌幅</th>
                  <th className="py-1.5 pr-2 text-right">连板</th>
                  <th className="py-1.5 text-left">所属行业</th>
            </tr>
          </thead>
          <tbody>
            {displayStocks.map((s) => (
              <tr key={s.code} className="border-b border-border/20">
                <td className="py-1.5 pr-2 text-foreground">{s.code}</td>
                <td className="py-1.5 pr-2 text-foreground">{s.name}</td>
                <td className="py-1.5 pr-2 text-right text-foreground">{s.price.toFixed(2)}</td>
                <td className={`py-1.5 pr-2 text-right ${s.changePct >= 0 ? 'text-danger' : 'text-success'}`}>
                  {s.changePct >= 0 ? '+' : ''}{s.changePct.toFixed(2)}%
                </td>
                <td className="py-1.5 pr-2 text-right">
                  {s.consecutiveDays >= 3 ? (
                    <span className="rounded bg-danger/10 px-1 py-0.5 font-medium text-danger">{s.consecutiveDays}板</span>
                  ) : s.consecutiveDays > 0 ? (
                    <span className="rounded bg-cyan/10 px-1 py-0.5 text-cyan">{s.consecutiveDays}板</span>
                  ) : (
                    <span className="text-secondary-text">首板</span>
                  )}
                </td>
                <td className="py-1.5 text-secondary-text">{s.industry || '-'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {stocks.length > 20 && (
        <button
          type="button"
          onClick={() => setShowAll(!showAll)}
          className="mt-3 w-full rounded-lg border border-border/40 py-1.5 text-xs text-secondary-text hover:text-foreground"
        >
          {showAll ? '收起' : `查看全部 ${stocks.length} 只`}
        </button>
      )}
    </div>
  );
};

const StockRow: React.FC<{ stock: SectorStockItem }> = ({ stock }) => {
  const changeColor = stock.changePct >= 0 ? 'text-danger' : 'text-success';
  return (
    <tr className="border-b border-border/20">
      <td className="py-1.5 pr-2 text-foreground">{stock.code}</td>
      <td className="py-1.5 pr-2 text-foreground">{stock.name}</td>
      <td className={`py-1.5 pr-2 text-right ${changeColor}`}>
        {stock.changePct >= 0 ? '+' : ''}
        {stock.changePct.toFixed(2)}%
      </td>
      <td className="py-1.5 pr-2 text-right text-foreground">{stock.price.toFixed(2)}</td>
      <td className="py-1.5 text-right">
        {stock.isLimitUp ? (
          <span className="rounded bg-danger/10 px-1 py-0.5 text-[10px] font-medium text-danger">
            {stock.consecutiveLimitUpDays > 0 ? `${stock.consecutiveLimitUpDays}连板` : '涨停'}
          </span>
        ) : (
          <span className="text-secondary-text">-</span>
        )}
      </td>
    </tr>
  );
};

export default SectorsPage;
