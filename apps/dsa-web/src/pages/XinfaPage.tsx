import type React from 'react';
import { useCallback, useEffect, useState } from 'react';
import {
  BookHeart,
  Eye,
  EyeOff,
  FilePlus,
  ListRestart,
  Pencil,
  Plus,
  Search,
  Star,
  Trash2,
} from 'lucide-react';
import Markdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { useNavigate } from 'react-router-dom';
import { xinfaApi } from '../api/xinfa';
import { getParsedApiError } from '../api/error';
import type { ParsedApiError } from '../api/error';
import { Card, EmptyState, Loading } from '../components/common';
import { CATEGORY_LABELS, CATEGORY_LIST } from '../types/xinfa';
import type {
  XinfaEntryItem,
  XinfaCategorySummaryItem,
} from '../types/xinfa';
import { cn } from '../utils/cn';

function formatDate(iso: string | null): string {
  if (!iso) return '';
  const d = new Date(iso);
  return d.toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  });
}

function sentimentStars(n: number | null): string {
  if (!n || n < 1 || n > 5) return '';
  return '★'.repeat(n) + '☆'.repeat(5 - n);
}

// ---------------------------------------------------------------------------
// Create Modal
// ---------------------------------------------------------------------------

type CreateModalProps = {
  isOpen: boolean;
  onClose: () => void;
  onCreated: () => void;
  initialData?: XinfaEntryItem;
  onUpdated?: () => void;
};

const CreateModal: React.FC<CreateModalProps> = ({
  isOpen,
  onClose,
  onCreated,
  initialData,
  onUpdated,
}) => {
  const [title, setTitle] = useState(initialData?.title ?? '');
  const [content, setContent] = useState(initialData?.content ?? '');
  const [category, setCategory] = useState(initialData?.category ?? 'general');
  const [tagsText, setTagsText] = useState(initialData?.tags?.join(', ') ?? '');
  const [sentiment, setSentiment] = useState(initialData?.sentiment ?? 0);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const reset = useCallback(() => {
    if (initialData) {
      setTitle(initialData.title);
      setContent(initialData.content);
      setCategory(initialData.category);
      setTagsText(initialData.tags?.join(', ') ?? '');
      setSentiment(initialData.sentiment ?? 0);
    } else {
      setTitle('');
      setContent('');
      setCategory('general');
      setTagsText('');
      setSentiment(0);
    }
    setError(null);
  }, [initialData]);

  const handleSubmit = async () => {
    if (!title.trim() || !content.trim()) {
      setError('标题和内容不能为空');
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      const payload = {
        title: title.trim(),
        content: content.trim(),
        category,
        tags: tagsText
          ? tagsText.split(/[,，、]/).map((t) => t.trim()).filter(Boolean)
          : undefined,
        sentiment: sentiment > 0 ? sentiment : undefined,
      };
      if (initialData) {
        await xinfaApi.update(initialData.id, payload);
        onUpdated?.();
      } else {
        await xinfaApi.create(payload);
        onCreated();
      }
      reset();
      onClose();
    } catch (err) {
      setError(getParsedApiError(err)?.message ?? (initialData ? '编辑失败' : '创建失败'));
    } finally {
      setSubmitting(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <div className="flex w-full max-w-2xl flex-col rounded-2xl border border-border bg-card shadow-2xl">
        <div className="flex items-center justify-between border-b border-border px-6 py-4">
          <h2 className="text-lg font-semibold text-foreground">
            {initialData ? '编辑心法' : '记录心法'}
          </h2>
          <button type="button" onClick={onClose} className="btn-ghost rounded-lg p-1.5">
            <EyeOff className="h-5 w-5" />
          </button>
        </div>

        <div className="flex flex-col gap-4 overflow-y-auto p-6">
          {error && (
            <div className="rounded-lg border border-red/20 bg-red/5 px-4 py-2 text-sm text-red">
              {error}
            </div>
          )}

          <input
            type="text"
            placeholder="标题"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            className="input w-full"
            autoFocus
          />

          <select
            value={category}
            onChange={(e) => setCategory(e.target.value)}
            className="input w-full"
          >
            {CATEGORY_LIST.map((c) => (
              <option key={c.key} value={c.key}>
                {c.label}
              </option>
            ))}
          </select>

          {initialData && (initialData.stockCode || initialData.stockName) && (
            <div className="flex items-center gap-2 rounded-lg border border-border/60 bg-base px-3 py-2 text-sm">
              <span className="text-secondary-text">相关股票：</span>
              <span className="font-medium text-info">
                {initialData.stockCode}
                {initialData.stockName ? ` ${initialData.stockName}` : ''}
              </span>
            </div>
          )}

          <input
            type="text"
            placeholder="标签（逗号分隔）"
            value={tagsText}
            onChange={(e) => setTagsText(e.target.value)}
            className="input w-full"
          />

          <div className="flex items-center gap-2">
            <span className="text-sm text-secondary-text">情绪评分：</span>
            {[1, 2, 3, 4, 5].map((n) => (
              <button
                key={n}
                type="button"
                onClick={() => setSentiment(n === sentiment ? 0 : n)}
                className={cn(
                  'rounded-lg px-3 py-1.5 text-sm font-medium transition-all',
                  'min-w-[36px]',
                  n <= sentiment
                    ? 'border border-yellow-500/40 bg-yellow/10 text-yellow-600 shadow-sm'
                    : 'border border-border bg-card text-secondary-text hover:border-yellow-500/30 hover:text-yellow-600'
                )}
              >
                {n}
              </button>
            ))}
          </div>

          <textarea
            placeholder="内容（支持 Markdown）"
            value={content}
            onChange={(e) => setContent(e.target.value)}
            className="input w-full min-h-[200px] resize-y"
            rows={8}
          />
        </div>

        <div className="flex justify-end gap-3 border-t border-border px-6 py-4">
          <button type="button" className="btn-ghost" onClick={() => { reset(); onClose(); }}>
            取消
          </button>
          <button
            type="button"
            className="btn-primary"
            disabled={submitting}
            onClick={() => void handleSubmit()}
          >
            {submitting ? '提交中...' : '保存'}
          </button>
        </div>
      </div>
    </div>
  );
};

// ---------------------------------------------------------------------------
// Entry Card
// ---------------------------------------------------------------------------

type EntryCardProps = {
  entry: XinfaEntryItem;
  onDeleted: () => void;
  onStarToggled: () => void;
  onEdit: () => void;
};

const EntryCard: React.FC<EntryCardProps> = ({ entry, onDeleted, onStarToggled, onEdit }) => {
  const navigate = useNavigate();
  const [expanded, setExpanded] = useState(false);
  const [deleting, setDeleting] = useState(false);

  const handleDelete = async () => {
    if (!window.confirm('确认删除这条心法？')) return;
    setDeleting(true);
    try {
      await xinfaApi.delete(entry.id);
      onDeleted();
    } catch {
      /* silent */
    } finally {
      setDeleting(false);
    }
  };

  const handleToggleStar = async () => {
    try {
      await xinfaApi.update(entry.id, { isStarred: !entry.isStarred });
      onStarToggled();
    } catch {
      /* silent */
    }
  };

  const catLabel = CATEGORY_LABELS[entry.category] ?? entry.category;
  const isReview = entry.category === 'review';
  const preview =
    entry.content.length > 200 ? entry.content.slice(0, 200) + '...' : entry.content;

  return (
    <Card
      className={cn(
        'group relative border border-border/60 bg-card p-4 transition-all',
        isReview ? 'hover:border-purple/40 cursor-pointer' : 'hover:border-border/100'
      )}
      onClick={isReview ? () => navigate(`/xinfa/review?edit=${entry.id}`) : undefined}
    >
      <div className="mb-2 flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <h2 className="truncate text-base font-semibold text-foreground">{entry.title}</h2>
          <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-secondary-text">
            <span className={cn(
              'rounded px-2 py-0.5',
              isReview
                ? 'bg-purple/10 text-purple'
                : 'bg-primary/10 text-primary'
            )}>
              {isReview ? '复盘' : catLabel}
            </span>
            <span>{formatDate(entry.createdAt)}</span>
            {entry.sentiment ? (
              <span className="text-yellow-600">{sentimentStars(entry.sentiment)}</span>
            ) : null}
            {entry.stockCode ? (
              <span className="text-info">
                {entry.stockCode} {entry.stockName ?? ''}
              </span>
            ) : null}
          </div>
        </div>

        <div className="flex shrink-0 items-center gap-1 opacity-100 transition-opacity sm:opacity-0 sm:group-hover:opacity-100">
          <button
            type="button"
            onClick={handleToggleStar}
            className="rounded-lg p-2 text-secondary-text transition-colors hover:bg-hover hover:text-yellow-500"
            title={entry.isStarred ? '取消标星' : '标星'}
          >
            <Star className={cn('h-5 w-5', entry.isStarred && 'fill-yellow-500 text-yellow-500')} />
          </button>
          <button
            type="button"
            onClick={onEdit}
            className="rounded-lg p-2 text-secondary-text transition-colors hover:bg-hover hover:text-foreground"
            title="编辑"
          >
            <Pencil className="h-5 w-5" />
          </button>
          <button
            type="button"
            onClick={() => setExpanded(!expanded)}
            className="rounded-lg p-2 text-secondary-text transition-colors hover:bg-hover hover:text-foreground"
            title={expanded ? '收起' : '展开'}
          >
            {expanded ? <EyeOff className="h-5 w-5" /> : <Eye className="h-5 w-5" />}
          </button>
          <button
            type="button"
            onClick={() => void handleDelete()}
            disabled={deleting}
            className="rounded-lg p-2 text-secondary-text transition-colors hover:bg-red/10 hover:text-red"
            title="删除"
          >
            <Trash2 className="h-5 w-5" />
          </button>
        </div>
      </div>

      {entry.tags && entry.tags.length > 0 && (
        <div className="mb-2 flex flex-wrap gap-1.5">
          {entry.tags.map((tag) => (
            <span
              key={tag}
              className="rounded-md bg-base px-2 py-0.5 text-xs text-secondary-text"
            >
              #{tag}
            </span>
          ))}
        </div>
      )}

      <div className="text-sm leading-relaxed text-foreground/80 prose prose-sm max-w-none prose-headings:text-foreground prose-strong:text-foreground prose-ul:my-1 prose-li:my-0.5 prose-p:my-1 prose-code:before:content-none prose-code:after:content-none prose-pre:border prose-a:no-underline hover:prose-a:underline prose-blockquote:text-secondary-text break-words">
        {expanded ? (
          <Markdown remarkPlugins={[remarkGfm]}>{entry.content}</Markdown>
        ) : (
          <Markdown remarkPlugins={[remarkGfm]}>{preview}</Markdown>
        )}
        {!expanded && entry.content.length > 200 && (
          <button
            type="button"
            onClick={() => setExpanded(true)}
            className="mt-1 text-xs text-info hover:underline"
          >
            展开全文
          </button>
        )}
      </div>
    </Card>
  );
};

// ---------------------------------------------------------------------------
// Main Page
// ---------------------------------------------------------------------------

const XinfaPage: React.FC = () => {
  const navigate = useNavigate();
  const [entries, setEntries] = useState<XinfaEntryItem[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<ParsedApiError | null>(null);

  const [categories, setCategories] = useState<XinfaCategorySummaryItem[]>([]);
  const [activeCategory, setActiveCategory] = useState<string | null>(null);
  const [keyword, setKeyword] = useState('');
  const [showStarredOnly, setShowStarredOnly] = useState(false);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [editingEntry, setEditingEntry] = useState<XinfaEntryItem | null>(null);

  const pageSize = 20;

  // Set per-route document title
  useEffect(() => {
    document.title = '心法 - DSA';
  }, []);

  const loadEntries = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await xinfaApi.list({
        category: activeCategory ?? undefined,
        keyword: keyword || undefined,
        isStarred: showStarredOnly || undefined,
        page: 1,
        pageSize,
      });
      setEntries(data.items);
      setTotal(data.total);
    } catch (err) {
      setError(getParsedApiError(err) ?? { message: '加载失败', status: 500 });
    } finally {
      setLoading(false);
    }
  }, [activeCategory, keyword, showStarredOnly]);

  const loadCategories = useCallback(async () => {
    try {
      const data = await xinfaApi.getCategories();
      setCategories(data.categories);
    } catch {
      // Fallback: show all categories from CATEGORY_LIST when API fails
      setCategories(
        CATEGORY_LIST.map((c) => ({ category: c.key, count: 0, label: c.label })),
      );
    }
  }, []);

  useEffect(() => {
    void loadEntries();
  }, [loadEntries]);

  useEffect(() => {
    void loadCategories();
  }, [loadCategories]);

  const handleEntryChange = useCallback(() => {
    void loadEntries();
    void loadCategories();
  }, [loadEntries, loadCategories]);

  return (
    <div className="flex h-full flex-col gap-4 p-4 md:p-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-purple/15 text-purple">
            <BookHeart className="h-5 w-5" />
          </div>
          <div>
            <h1 className="text-lg font-semibold text-foreground">心法</h1>
            <p className="text-xs text-secondary-text">记录炒股心得，修炼交易心态</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            className="btn-ghost flex items-center gap-2"
            onClick={() => navigate('/xinfa/review')}
          >
            <ListRestart className="h-4 w-4" />
            <span className="hidden sm:inline">复盘</span>
          </button>
          <button
            type="button"
            className="btn-primary flex items-center gap-2"
            onClick={() => setShowCreateModal(true)}
          >
            <FilePlus className="h-4 w-4" />
            <span className="hidden sm:inline">记录心法</span>
          </button>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <div className="relative flex-1 min-w-[200px] max-w-sm">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-secondary-text" />
          <input
            type="text"
            placeholder="搜索心法..."
            value={keyword}
            onChange={(e) => setKeyword(e.target.value)}
            className="input w-full pl-9"
            onKeyDown={(e) => {
              if (e.key === 'Enter') void loadEntries();
            }}
          />
        </div>

        <select
          value={activeCategory ?? ''}
          onChange={(e) => setActiveCategory(e.target.value || null)}
          className="input w-auto min-w-[120px]"
        >
          <option value="">全部分类</option>
          {CATEGORY_LIST.map((c) => (
            <option key={c.key} value={c.key}>
              {c.label}
            </option>
          ))}
        </select>

        <button
          type="button"
          className={cn(
            'flex items-center gap-1.5 rounded-lg border px-3 py-2 text-sm transition-colors',
            showStarredOnly
              ? 'border-yellow-500/40 bg-yellow/10 text-yellow-600'
              : 'border-border/60 text-secondary-text hover:border-border hover:text-foreground'
          )}
          onClick={() => setShowStarredOnly(!showStarredOnly)}
        >
          <Star className={cn('h-4 w-4', showStarredOnly && 'fill-yellow-500')} />
          <span>标星</span>
        </button>
      </div>

      {categories.length > 0 && !keyword && !showStarredOnly && (
        <div className="flex flex-wrap gap-2">
          {categories.map((c) => (
            <button
              key={c.category}
              type="button"
              onClick={() => setActiveCategory(c.category === activeCategory ? null : c.category)}
              className={cn(
                'rounded-lg border px-3 py-1.5 text-xs transition-colors',
                activeCategory === c.category
                  ? 'border-primary/40 bg-primary/10 text-primary'
                  : 'border-border/40 text-secondary-text hover:border-border hover:text-foreground'
              )}
            >
              {c.label} ({c.count})
            </button>
          ))}
        </div>
      )}

      {loading ? (
        <div className="flex flex-1 items-center justify-center">
          <Loading />
        </div>
      ) : error ? (
        <EmptyState
          icon={<BookHeart className="h-12 w-12" />}
          title="加载失败"
          description={error.message}
        />
      ) : entries.length === 0 ? (
        <EmptyState
          icon={<BookHeart className="h-12 w-12" />}
          title="还没有心法记录"
          description="点击右上角「记录心法」开始记录你的炒股心得"
          action={
            <button
              type="button"
              className="btn-primary mt-4 flex items-center gap-2"
              onClick={() => setShowCreateModal(true)}
            >
              <Plus className="h-4 w-4" />
              写第一条心法
            </button>
          }
        />
      ) : (
        <div className="flex flex-col gap-3 overflow-y-auto pb-4">
          <p className="text-xs text-secondary-text">共 {total} 条</p>
          {entries.map((entry) => (
            <EntryCard
              key={entry.id}
              entry={entry}
              onDeleted={handleEntryChange}
              onStarToggled={handleEntryChange}
              onEdit={() => setEditingEntry(entry)}
            />
          ))}
        </div>
      )}

      <CreateModal
        key={editingEntry?.id ?? 'create'}
        isOpen={showCreateModal || editingEntry !== null}
        onClose={() => { setShowCreateModal(false); setEditingEntry(null); }}
        onCreated={handleEntryChange}
        initialData={editingEntry ?? undefined}
        onUpdated={handleEntryChange}
      />
    </div>
  );
};

export default XinfaPage;
