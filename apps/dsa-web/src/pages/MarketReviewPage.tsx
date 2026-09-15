import type React from 'react';
import { useEffect } from 'react';
import { Calendar, ChevronLeft, ChevronRight, FileText, RefreshCw, AlertCircle, Zap } from 'lucide-react';
import Markdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { useMarketReviewStore } from '../stores/marketReviewStore';
import { EmptyState } from '../components/common';

const MarketReviewPage: React.FC = () => {
  const {
    reports, current, currentIndex,
    isLoading, isLoadingContent, isGenerating, error, loaded,
    loadList, generate, selectReport, goToPrev, goToNext,
  } = useMarketReviewStore();

  useEffect(() => {
    if (!loaded) {
      void loadList();
    }
  }, [loaded, loadList]);

  if (isLoading && !isGenerating) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-cyan/20 border-t-cyan" />
      </div>
    );
  }

  if (error && reports.length === 0 && !isGenerating) {
    return (
      <div className="p-6">
        <EmptyState
          icon={<AlertCircle className="h-10 w-10" />}
          title="加载失败"
          description={error}
          action={<button type="button" onClick={() => void loadList()} className="btn-primary">重试</button>}
        />
      </div>
    );
  }

  if (reports.length === 0 && !isGenerating) {
    return (
      <div className="p-6">
        <EmptyState
          icon={<FileText className="h-10 w-10" />}
          title="暂无复盘报告"
          description="点击下方按钮立即生成今日大盘复盘报告，分析过程需要 30-60 秒。"
          action={
            <button
              type="button"
              onClick={() => void generate()}
              className="btn-primary inline-flex items-center gap-2"
            >
              <Zap className="h-4 w-4" />
              生成今日复盘
            </button>
          }
        />
      </div>
    );
  }

  return (
    <div className="flex h-full gap-4 p-4">
      <div className="flex w-48 shrink-0 flex-col gap-2">
        <div className="mb-2 flex items-center justify-between">
          <h2 className="text-sm font-semibold text-foreground">复盘记录</h2>
          <div className="flex items-center gap-1">
            <button
              type="button"
              onClick={() => void generate()}
              disabled={isGenerating}
              className="flex h-7 w-7 items-center justify-center rounded-lg text-secondary-text hover:bg-hover hover:text-foreground disabled:opacity-30"
              aria-label="生成复盘"
            >
              <Zap className="h-4 w-4" />
            </button>
            <button
              type="button"
              onClick={() => void loadList()}
              className="flex h-7 w-7 items-center justify-center rounded-lg text-secondary-text hover:bg-hover hover:text-foreground"
              aria-label="刷新"
            >
              <RefreshCw className="h-4 w-4" />
            </button>
          </div>
        </div>
        <div className="scrollbar-thin flex-1 space-y-1 overflow-y-auto">
          {reports.map((meta, idx) => (
            <button
              key={meta.date}
              type="button"
              onClick={() => void selectReport(meta, idx)}
              className={`flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left text-sm transition-all ${
                idx === currentIndex
                  ? 'bg-[var(--nav-active-bg)] text-foreground font-medium'
                  : 'text-secondary-text hover:bg-hover hover:text-foreground'
              }`}
            >
              <Calendar className="h-3.5 w-3.5 shrink-0" />
              <span className="truncate">{meta.date_formatted}</span>
            </button>
          ))}
        </div>
      </div>

      <div className="flex flex-1 flex-col overflow-hidden rounded-2xl border bg-surface">
        {current && !isGenerating && (
          <div className="flex items-center justify-between border-b px-5 py-3">
            <div className="flex items-center gap-2 text-sm text-secondary-text">
              <FileText className="h-4 w-4" />
              <span>{current.meta.date_formatted} 大盘复盘</span>
            </div>
            <div className="flex items-center gap-1">
              <button
                type="button"
                onClick={goToNext}
                disabled={currentIndex === 0}
                className="flex h-8 w-8 items-center justify-center rounded-lg text-secondary-text hover:bg-hover hover:text-foreground disabled:opacity-30 disabled:cursor-not-allowed"
                aria-label="上一篇"
              >
                <ChevronLeft className="h-4 w-4" />
              </button>
              <span className="min-w-[4rem] text-center text-xs text-secondary-text">
                {reports.length - currentIndex} / {reports.length}
              </span>
              <button
                type="button"
                onClick={goToPrev}
                disabled={currentIndex === reports.length - 1}
                className="flex h-8 w-8 items-center justify-center rounded-lg text-secondary-text hover:bg-hover hover:text-foreground disabled:opacity-30 disabled:cursor-not-allowed"
                aria-label="下一篇"
              >
                <ChevronRight className="h-4 w-4" />
              </button>
            </div>
          </div>
        )}

        <div className="scrollbar-thin flex-1 overflow-y-auto p-5">
          {isGenerating ? (
            <div className="flex h-full flex-col items-center justify-center gap-4">
              <div className="h-10 w-10 animate-spin rounded-full border-[3px] border-cyan/20 border-t-cyan" />
              <p className="text-sm text-secondary-text">正在生成大盘复盘报告（约 30-60 秒）...</p>
            </div>
          ) : isLoadingContent ? (
            <div className="flex h-64 items-center justify-center">
              <div className="h-8 w-8 animate-spin rounded-full border-2 border-cyan/20 border-t-cyan" />
            </div>
          ) : current ? (
            <div
              className="prose prose-invert prose-sm max-w-none
                prose-headings:text-foreground prose-headings:font-semibold prose-headings:mt-5 prose-headings:mb-3
                prose-h1:text-xl prose-h2:text-lg prose-h3:text-base
                prose-p:leading-relaxed prose-p:mb-3 prose-p:last:mb-0
                prose-strong:text-foreground prose-strong:font-semibold
                prose-ul:my-2 prose-ol:my-2 prose-li:my-1
                prose-code:px-1.5 prose-code:py-0.5 prose-code:rounded
                prose-pre:border
                prose-table:border-collapse
                prose-hr:my-4
                prose-a:no-underline hover:prose-a:underline
                prose-blockquote:text-secondary-text
                whitespace-pre-line break-words
              "
            >
              <Markdown remarkPlugins={[remarkGfm]}>
                {current.content}
              </Markdown>
            </div>
          ) : (
            <div className="flex h-64 items-center justify-center text-secondary-text text-sm">
              选择左侧日期查看复盘报告
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default MarketReviewPage;
