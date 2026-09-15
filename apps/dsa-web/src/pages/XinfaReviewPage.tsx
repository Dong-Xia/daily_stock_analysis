import type React from 'react';
import { useCallback, useEffect, useState } from 'react';
import {
  ArrowLeft,
  BookHeart,
  Check,
  Plus,
} from 'lucide-react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { xinfaApi } from '../api/xinfa';
import { getParsedApiError } from '../api/error';
import { EmptyState, Loading } from '../components/common';
import type { XinfaEntryItem } from '../types/xinfa';
import { cn } from '../utils/cn';

// ---------------------------------------------------------------------------
// 涅槃重升式复盘 — 表单数据类型
// ---------------------------------------------------------------------------

interface ReviewFormData {
  date: string;

  // 一、我的交易回顾
  tradeReview: string;

  // 二、盘面复盘 - 主线三维度
  mainDragon: string;
  mainFollowUp: string;
  mainSwitch: string;

  // 二、盘面复盘 - 涨停质量
  limitYiZi: string;
  limitHuanShou: string;
  limitZhaBan: string;
  limitZhaBanRate: string;
  limitMaxLianBan: string;
  limitLianBanTier: string;
  limitProfitEffect: string; // 好 / 一般 / 差

  // 二、盘面复盘 - 情绪周期定位
  cyclePhase: string;      // 低位试错 / 主升 / 高位震荡 / 主跌
  cycleKeySignal: string;
  cycleReasoning: string;

  // 三、昨日预判验证
  prevVerify: string;

  // 四、明日预判
  tomorrowDirection: string;
  tomorrowDirectionReason: string;
  tomorrowMainline: string;
  tomorrowMainlineReason: string;
  tomorrowSentiment: string;
  tomorrowSentimentReason: string;
  tomorrowPosition: string;
  tomorrowBuyPlan: string;
  tomorrowInvalidCondition: string;

  // 五、知行合一检查
  checkExecuted: boolean;
  checkOutside: boolean;
  checkOutsideReason: string;

  // 六、系统完善
  learnedToday: string;
  cognitionFix: string;
  disciplineRule: string;
}

// ---------------------------------------------------------------------------
// Markdown 序列化 / 反序列化
// ---------------------------------------------------------------------------

function emptyFormData(date?: string): ReviewFormData {
  return {
    date: date ?? new Date().toISOString().slice(0, 10),
    tradeReview: '',
    mainDragon: '',
    mainFollowUp: '',
    mainSwitch: '',
    limitYiZi: '',
    limitHuanShou: '',
    limitZhaBan: '',
    limitZhaBanRate: '',
    limitMaxLianBan: '',
    limitLianBanTier: '',
    limitProfitEffect: '',
    cyclePhase: '',
    cycleKeySignal: '',
    cycleReasoning: '',
    prevVerify: '',
    tomorrowDirection: '',
    tomorrowDirectionReason: '',
    tomorrowMainline: '',
    tomorrowMainlineReason: '',
    tomorrowSentiment: '',
    tomorrowSentimentReason: '',
    tomorrowPosition: '',
    tomorrowBuyPlan: '',
    tomorrowInvalidCondition: '',
    checkExecuted: false,
    checkOutside: false,
    checkOutsideReason: '',
    learnedToday: '',
    cognitionFix: '',
    disciplineRule: '',
  };
}

function serializeReview(data: ReviewFormData, stockCode: string, stockName: string): string {
  const lines: string[] = [];
  const dateLabel = data.date || new Date().toISOString().slice(0, 10);
  lines.push(`# 复盘 ${dateLabel}`);
  lines.push('');

  if (stockCode) {
    lines.push(`> 股票：${stockCode} ${stockName || ''}`);
    lines.push('');
  }

  // ---------- 一、我的交易回顾 ----------
  if (data.tradeReview.trim()) {
    lines.push('## 我的交易回顾');
    lines.push('');
    lines.push(data.tradeReview.trim());
    lines.push('');
  }

  // ---------- 二、盘面复盘 ----------
  const hasMainline = data.mainDragon.trim() || data.mainFollowUp.trim() || data.mainSwitch.trim();
  const hasLimitUp = data.limitYiZi.trim() || data.limitHuanShou.trim() || data.limitZhaBan.trim()
    || data.limitZhaBanRate.trim() || data.limitMaxLianBan.trim() || data.limitLianBanTier.trim()
    || data.limitProfitEffect.trim();
  const hasCycle = data.cyclePhase.trim() || data.cycleKeySignal.trim() || data.cycleReasoning.trim();

  if (hasMainline || hasLimitUp || hasCycle) {
    lines.push('## 盘面复盘');
    lines.push('');

    if (hasMainline) {
      lines.push('### 主线三维度');
      lines.push('');
      if (data.mainDragon.trim()) lines.push(`- **龙头股：** ${data.mainDragon.trim()}`);
      if (data.mainFollowUp.trim()) lines.push(`- **补涨股：** ${data.mainFollowUp.trim()}`);
      if (data.mainSwitch.trim()) lines.push(`- **切换方向：** ${data.mainSwitch.trim()}`);
      lines.push('');
    }

    if (hasLimitUp) {
      lines.push('### 涨停质量');
      lines.push('');
      const limitParts: string[] = [];
      if (data.limitYiZi.trim()) limitParts.push(`一字板：${data.limitYiZi.trim()}`);
      if (data.limitHuanShou.trim()) limitParts.push(`换手板：${data.limitHuanShou.trim()}`);
      if (data.limitZhaBan.trim()) limitParts.push(`炸板：${data.limitZhaBan.trim()}`);
      if (limitParts.length > 0) {
        lines.push(limitParts.join(' | '));
        lines.push('');
      }
      if (data.limitZhaBanRate.trim()) {
        lines.push(`炸板率：${data.limitZhaBanRate.trim()}${data.limitZhaBanRate.trim().includes('%') ? '' : '%'}`);
        lines.push('');
      }
      if (data.limitMaxLianBan.trim()) {
        lines.push(`最高连板：${data.limitMaxLianBan.trim()}`);
        lines.push('');
      }
      if (data.limitLianBanTier.trim()) {
        lines.push(`连板梯队：${data.limitLianBanTier.trim()}`);
        lines.push('');
      }
      if (data.limitProfitEffect.trim()) {
        lines.push(`赚钱效应：${data.limitProfitEffect.trim()}`);
        lines.push('');
      }
    }

    if (hasCycle) {
      lines.push('### 情绪周期定位');
      lines.push('');
      if (data.cyclePhase.trim()) lines.push(`- **当前阶段：** ${data.cyclePhase.trim()}`);
      if (data.cycleKeySignal.trim()) lines.push(`- **关键信号：** ${data.cycleKeySignal.trim()}`);
      if (data.cycleReasoning.trim()) lines.push(`- **判断依据：** ${data.cycleReasoning.trim()}`);
      lines.push('');
    }
  }

  // ---------- 三、昨日预判验证 ----------
  if (data.prevVerify.trim()) {
    lines.push('## 昨日预判验证');
    lines.push('');
    lines.push(data.prevVerify.trim());
    lines.push('');
  }

  // ---------- 四、明日预判 ----------
  const hasTomorrow = data.tomorrowDirection.trim() || data.tomorrowDirectionReason.trim()
    || data.tomorrowMainline.trim() || data.tomorrowMainlineReason.trim()
    || data.tomorrowSentiment.trim() || data.tomorrowSentimentReason.trim()
    || data.tomorrowPosition.trim() || data.tomorrowBuyPlan.trim()
    || data.tomorrowInvalidCondition.trim();

  if (hasTomorrow) {
    lines.push('## 明日预判');
    lines.push('');

    const tomFields: Array<[string, string, string]> = [
      ['大盘方向', data.tomorrowDirection, data.tomorrowDirectionReason],
      ['主线延续', data.tomorrowMainline, data.tomorrowMainlineReason],
      ['情绪演化', data.tomorrowSentiment, data.tomorrowSentimentReason],
    ];
    for (const [label, value, reason] of tomFields) {
      if (value.trim() || reason.trim()) {
        const parts = [`- **${label}：** ${value.trim() || '—'}`];
        if (reason.trim()) parts[0] += `（${reason.trim()}）`;
        lines.push(parts[0]);
      }
    }
    if (data.tomorrowPosition.trim()) {
      lines.push(`- **仓位计划：** ${data.tomorrowPosition.trim()}`);
    }
    lines.push('');
    if (data.tomorrowBuyPlan.trim()) {
      lines.push('**核心买点计划（如果有）：**');
      lines.push('> ' + data.tomorrowBuyPlan.trim());
      lines.push('');
    }
    if (data.tomorrowInvalidCondition.trim()) {
      lines.push('**失效条件（什么情况证明判断错了）：**');
      lines.push('> ' + data.tomorrowInvalidCondition.trim());
      lines.push('');
    }
  }

  // ---------- 五、知行合一检查 ----------
  lines.push('## 知行合一检查');
  lines.push('');
  lines.push(`- [${data.checkExecuted ? 'x' : ' '}] 今天是否执行了昨晚的计划？`);
  lines.push(`- [${data.checkOutside ? 'x' : ' '}] 盘中是否有计划外的操作？`);
  if (data.checkOutsideReason.trim()) {
    lines.push(`- 如果有计划外操作，是什么触发的？${data.checkOutsideReason.trim()}`);
  }
  lines.push('');

  // ---------- 六、系统完善 ----------
  const hasSystem = data.learnedToday.trim() || data.cognitionFix.trim() || data.disciplineRule.trim();
  if (hasSystem) {
    lines.push('## 系统完善');
    lines.push('');
    if (data.learnedToday.trim()) {
      lines.push(`**今天学到的最重要 1 条：**`);
      lines.push('> ' + data.learnedToday.trim());
      lines.push('');
    }
    if (data.cognitionFix.trim()) {
      lines.push(`**需要修正的认知 / 规则：**`);
      lines.push('> ' + data.cognitionFix.trim());
      lines.push('');
    }
    if (data.disciplineRule.trim()) {
      lines.push(`**今天的错误能否提炼成一条纪律？**`);
      lines.push('> ' + data.disciplineRule.trim());
      lines.push('');
    }
  }

  return lines.join('\n').trim();
}

function deserializeReview(content: string): ReviewFormData {
  const data = emptyFormData();

  // Extract date from "# 复盘 YYYY-MM-DD"
  const dateMatch = content.match(/^#\s+复盘\s+(\d{4}-\d{2}-\d{2})/m);
  if (dateMatch) data.date = dateMatch[1];

  // Detect format: new (涅槃) or old
  const hasNewHeaders = /^##\s+我的交易回顾/m.test(content)
    || /^##\s+盘面复盘/m.test(content)
    || /^##\s+知行合一检查/m.test(content);

  if (hasNewHeaders) {
    // --- New format parser ---
    const sections = content.split(/^##\s+/m);
    for (const section of sections) {
      const lines = section.trim().split('\n');
      const heading = lines[0].trim();
      const body = lines.slice(1).join('\n').trim();

      switch (heading) {
        case '我的交易回顾':
          data.tradeReview = body;
          break;

        case '盘面复盘': {
          // extract ### sub-sections
          const subSections = body.split(/^###\s+/m);
          for (const sub of subSections) {
            const subLines = sub.trim().split('\n');
            const subHeading = subLines[0].trim();
            const subBody = subLines.slice(1).join('\n').trim();

            switch (subHeading) {
              case '主线三维度': {
                const dr = extractKeyValue(subBody, '龙头股');
                if (dr) data.mainDragon = dr;
                const fu = extractKeyValue(subBody, '补涨股');
                if (fu) data.mainFollowUp = fu;
                const sw = extractKeyValue(subBody, '切换方向');
                if (sw) data.mainSwitch = sw;
                break;
              }
              case '涨停质量': {
                const yz = extractAfter(subBody, '一字板');
                if (yz) data.limitYiZi = yz;
                const hs = extractAfter(subBody, '换手板');
                if (hs) data.limitHuanShou = hs;
                const zb = extractAfter(subBody, '炸板');
                if (zb) data.limitZhaBan = zb;
                const zbr = extractAfter(subBody, '炸板率');
                if (zbr) data.limitZhaBanRate = zbr.replace('%', '');
                const mlb = extractAfter(subBody, '最高连板');
                if (mlb) data.limitMaxLianBan = mlb;
                const lbt = extractAfter(subBody, '连板梯队');
                if (lbt) data.limitLianBanTier = lbt;
                const pe = extractAfter(subBody, '赚钱效应');
                if (pe) data.limitProfitEffect = pe;
                break;
              }
              case '情绪周期定位': {
                const cp = extractKeyValue(subBody, '当前阶段');
                if (cp) data.cyclePhase = cp;
                const ks = extractKeyValue(subBody, '关键信号');
                if (ks) data.cycleKeySignal = ks;
                const re = extractKeyValue(subBody, '判断依据');
                if (re) data.cycleReasoning = re;
                break;
              }
            }
          }
          break;
        }

        case '昨日预判验证':
          data.prevVerify = body;
          break;

        case '明日预判': {
          // Try structured extraction
          data.tomorrowDirection = extractKeyValue(body, '大盘方向') || '';
          data.tomorrowMainline = extractKeyValue(body, '主线延续') || '';
          data.tomorrowSentiment = extractKeyValue(body, '情绪演化') || '';
          data.tomorrowPosition = extractKeyValue(body, '仓位计划') || '';

          // Try to extract reasons from "X（reason）" format
          const reasonMatch = (label: string) => {
            const re = new RegExp(`\\*\\*${label}:\\*\\*\\s*([^（]+?)(?:（(.+?)）)?\\s*$`, 'm');
            const m = body.match(re);
            return m ? m[2]?.trim() || '' : '';
          };
          data.tomorrowDirectionReason = reasonMatch('大盘方向');
          data.tomorrowMainlineReason = reasonMatch('主线延续');
          data.tomorrowSentimentReason = reasonMatch('情绪演化');

          // Extract buy plan / invalid condition
          const bp = body.match(/核心买点计划[^]*?>\s*(.+?)(?:\n\n|$)/);
          if (bp) data.tomorrowBuyPlan = bp[1].trim();
          const ic = body.match(/失效条件[^]*?>\s*(.+?)(?:\n\n|$)/);
          if (ic) data.tomorrowInvalidCondition = ic[1].trim();
          break;
        }

        case '知行合一检查': {
          data.checkExecuted = /\[x\]/.test(body.split('\n')[0] || '');
          data.checkOutside = /\[x\]/.test(body.split('\n')[1] || '');
          const reasonMatch = body.match(/触发的？(.+)/);
          if (reasonMatch) data.checkOutsideReason = reasonMatch[1].trim();
          break;
        }

        case '系统完善': {
          const lt = body.match(/学到的最重要 1 条[^]*?>\s*(.+?)(?:\n\n|$)/);
          if (lt) data.learnedToday = lt[1].trim();
          const cf = body.match(/需要修正的认知[^]*?>\s*(.+?)(?:\n\n|$)/);
          if (cf) data.cognitionFix = cf[1].trim();
          const dr = body.match(/提炼成一条纪律[^]*?>\s*(.+?)(?:\n\n|$)/);
          if (dr) data.disciplineRule = dr[1].trim();
          break;
        }
      }
    }
  } else {
    // --- Old format parser (backward compat) ---
    const sections = content.split(/^##\s+/m);
    for (const section of sections) {
      const lines = section.trim().split('\n');
      const heading = lines[0].trim();
      const body = lines.slice(1).join('\n').trim();

      if (heading === '今日操作总结') {
        data.tradeReview = body;
      } else if (heading === '明日计划') {
        const subLines = body.split('\n');
        const parts: string[] = [];
        for (const line of subLines) {
          const match = line.match(/^###\s+(.+)/);
          if (match) {
            parts.push(match[1].trim());
          } else {
            parts.push(line);
          }
        }
        data.tomorrowBuyPlan = parts.join('\n').trim();
      }
    }
  }

  return data;
}

/** Extract value after "label：" on same or next line */
function extractKeyValue(text: string, label: string): string {
  const re = new RegExp(
    `\\*\\*${label}:\\*\\*\\s*(.+?)(?:\\n|$)`  // same line
  );
  const m = text.match(re);
  if (m) return m[1].trim();

  // next line variant
  const re2 = new RegExp(`\\*\\*${label}:\\*\\*\\s*\\n+\\s*(.+?)(?:\\n|$)`);
  const m2 = text.match(re2);
  if (m2) return m2[1].trim();

  return '';
}

/** Extract the rest of the line after "label：" */
function extractAfter(text: string, label: string): string {
  const re = new RegExp(`${label}[：:]\\s*(.+?)(?:\\s*[|\\n]|$)`);
  const m = text.match(re);
  if (m) return m[1].trim();
  return '';
}

// ---------------------------------------------------------------------------
// 子组件
// ---------------------------------------------------------------------------

const FormSection: React.FC<{
  label: string;
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  rows?: number;
  hint?: string;
}> = ({ label, value, onChange, placeholder, rows = 3, hint }) => (
  <div className="flex flex-col gap-1.5">
    <label className="text-sm font-medium text-foreground">{label}</label>
    {hint && <p className="text-xs text-secondary-text">{hint}</p>}
    <textarea
      value={value}
      onChange={(e) => onChange(e.target.value)}
      placeholder={placeholder}
      className="input w-full resize-y min-h-[60px]"
      rows={rows}
    />
  </div>
);

const FormInput: React.FC<{
  label: string;
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  className?: string;
}> = ({ label, value, onChange, placeholder, className }) => (
  <div className="flex flex-col gap-1">
    <label className="text-xs font-medium text-foreground/80">{label}</label>
    <input
      type="text"
      value={value}
      onChange={(e) => onChange(e.target.value)}
      placeholder={placeholder}
      className={cn('input', className)}
    />
  </div>
);

const FormSelect: React.FC<{
  label: string;
  value: string;
  onChange: (v: string) => void;
  options: Array<{ value: string; label: string }>;
  placeholder?: string;
  className?: string;
}> = ({ label, value, onChange, options, placeholder, className }) => (
  <div className="flex flex-col gap-1">
    <label className="text-xs font-medium text-foreground/80">{label}</label>
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className={cn('input', className)}
    >
      <option value="">{placeholder ?? '请选择'}</option>
      {options.map((opt) => (
        <option key={opt.value} value={opt.value}>{opt.label}</option>
      ))}
    </select>
  </div>
);

// ---------------------------------------------------------------------------
// Review Card (for listing past reviews)
// ---------------------------------------------------------------------------

const ReviewCard: React.FC<{
  entry: XinfaEntryItem;
  onEdit: () => void;
}> = ({ entry, onEdit }) => {
  const data = deserializeReview(entry.content);
  const dateLabel = data.date || entry.title;
  return (
    <div
      className="cursor-pointer rounded-xl border border-border/60 bg-card p-4 transition-all hover:border-primary/40"
      onClick={onEdit}
    >
      <div className="mb-2 flex items-center justify-between">
        <span className="text-sm font-semibold text-foreground">
          {dateLabel}
        </span>
        <div className="flex items-center gap-2 text-xs text-secondary-text">
          {entry.sentiment && (
            <span className="text-yellow-600">
              {'★'.repeat(entry.sentiment) + '☆'.repeat(5 - entry.sentiment)}
            </span>
          )}
          <span>{entry.createdAt?.slice(0, 10)}</span>
        </div>
      </div>
      <div className="flex flex-wrap gap-1.5">
        {entry.tags?.map((t) => (
          <span key={t} className="rounded-md bg-base px-2 py-0.5 text-xs text-secondary-text">
            #{t}
          </span>
        ))}
      </div>
      {data.tradeReview && (
        <p className="mt-2 line-clamp-2 text-sm text-foreground/70">
          {data.tradeReview}
        </p>
      )}
    </div>
  );
};

// ---------------------------------------------------------------------------
// Main Page
// ---------------------------------------------------------------------------

const XinfaReviewPage: React.FC = () => {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const editId = searchParams.get('edit');

  // Form state
  const [formData, setFormData] = useState<ReviewFormData>(emptyFormData());
  const [sentiment, setSentiment] = useState(0);
  const [tagsText, setTagsText] = useState('');
  const [stockCode, setStockCode] = useState('');
  const [stockName, setStockName] = useState('');

  // Submission
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastSaved, setLastSaved] = useState(false);

  // Recent reviews list
  const [reviews, setReviews] = useState<XinfaEntryItem[]>([]);
  const [reviewsLoading, setReviewsLoading] = useState(true);

  // Loading existing entry for edit
  const [loadingEntry, setLoadingEntry] = useState(!!editId);

  useEffect(() => {
    document.title = '复盘 - DSA';
  }, []);

  // Load existing entry if editing
  useEffect(() => {
    if (!editId) return;
    setLoadingEntry(true);
    xinfaApi.get(Number(editId))
      .then((entry) => {
        const data = deserializeReview(entry.content);
        setFormData(data);
        setSentiment(entry.sentiment ?? 0);
        setTagsText(entry.tags?.join(', ') ?? '');
        setStockCode(entry.stockCode ?? '');
        setStockName(entry.stockName ?? '');
      })
      .catch((err) => {
        setError(getParsedApiError(err)?.message ?? '加载复盘失败');
      })
      .finally(() => setLoadingEntry(false));
  }, [editId]);

  // Load recent reviews
  const loadReviews = useCallback(async () => {
    setReviewsLoading(true);
    try {
      const data = await xinfaApi.list({
        category: 'review',
        page: 1,
        pageSize: 10,
      });
      setReviews(data.items);
    } catch {
      /* noop */
    } finally {
      setReviewsLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadReviews();
  }, [loadReviews]);

  const updateField = useCallback(<K extends keyof ReviewFormData>(key: K, value: ReviewFormData[K]) => {
    setFormData((prev) => ({ ...prev, [key]: value }));
    setLastSaved(false);
  }, []);

  const handleSubmit = async () => {
    const dateLabel = formData.date || new Date().toISOString().slice(0, 10);
    const title = `复盘 ${dateLabel}`;
    const content = serializeReview(formData, stockCode.trim(), stockName.trim());

    if (!content.trim()) {
      setError('内容不能为空');
      return;
    }

    setSubmitting(true);
    setError(null);
    try {
      const payload = {
        title,
        content,
        category: 'review' as const,
        sentiment: sentiment > 0 ? sentiment : undefined,
        tags: tagsText
          ? tagsText.split(/[,，、]/).map((t) => t.trim()).filter(Boolean)
          : undefined,
        stockCode: stockCode.trim() || undefined,
        stockName: stockName.trim() || undefined,
      };

      if (editId) {
        await xinfaApi.update(Number(editId), payload);
      } else {
        await xinfaApi.create(payload);
      }
      setLastSaved(true);
      void loadReviews();

      if (!editId) {
        setFormData(emptyFormData());
        setSentiment(0);
        setTagsText('');
        setStockCode('');
        setStockName('');
      }
    } catch (err) {
      setError(getParsedApiError(err)?.message ?? (editId ? '保存失败' : '创建失败'));
    } finally {
      setSubmitting(false);
    }
  };

  const handleEdit = (entry: XinfaEntryItem) => {
    navigate(`/xinfa/review?edit=${entry.id}`);
  };

  const handleNew = () => {
    navigate('/xinfa/review');
  };

  // ---- Render ----

  return (
    <div className="flex h-full flex-col gap-4 overflow-y-auto p-4 md:p-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={() => navigate('/xinfa')}
            className="rounded-lg p-2 text-secondary-text transition-colors hover:bg-hover hover:text-foreground"
            title="返回心法"
          >
            <ArrowLeft className="h-5 w-5" />
          </button>
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-purple/15 text-purple">
            <BookHeart className="h-5 w-5" />
          </div>
          <div>
            <h1 className="text-lg font-semibold text-foreground">
              {editId ? '编辑复盘' : '今日复盘'}
            </h1>
            <p className="text-xs text-secondary-text">涅槃重升式 · 推倒重来，每天清零</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {editId && (
            <button
              type="button"
              className="btn-ghost flex items-center gap-2"
              onClick={handleNew}
            >
              <Plus className="h-4 w-4" />
              <span className="hidden sm:inline">新建复盘</span>
            </button>
          )}
          <button
            type="button"
            className="btn-primary flex items-center gap-2"
            disabled={submitting}
            onClick={() => void handleSubmit()}
          >
            <Check className="h-4 w-4" />
            <span>{submitting ? '保存中...' : '保存复盘'}</span>
          </button>
        </div>
      </div>

      {error && (
        <div className="rounded-lg border border-red/20 bg-red/5 px-4 py-2 text-sm text-red">
          {error}
        </div>
      )}

      {lastSaved && !error && (
        <div className="rounded-lg border border-green/20 bg-green/5 px-4 py-2 text-sm text-green">
          复盘已保存
        </div>
      )}

      {loadingEntry ? (
        <div className="flex flex-1 items-center justify-center">
          <Loading />
        </div>
      ) : (
        <>
          {/* ======== Form ======== */}
          <div className="flex flex-col gap-6 rounded-xl border border-border bg-card p-4 md:p-6">
            {/* Meta row */}
            <div className="flex flex-wrap items-center gap-4">
              <div className="flex items-center gap-2">
                <label className="text-sm font-medium text-foreground">日期</label>
                <input
                  type="date"
                  value={formData.date}
                  onChange={(e) => updateField('date', e.target.value)}
                  className="input w-auto"
                />
              </div>
              <div className="flex items-center gap-2">
                <label className="text-sm font-medium text-foreground">股票代码</label>
                <input
                  type="text"
                  placeholder="如 600519"
                  value={stockCode}
                  onChange={(e) => setStockCode(e.target.value)}
                  className="input w-28"
                />
              </div>
              <div className="flex items-center gap-2">
                <label className="text-sm font-medium text-foreground">股票名称</label>
                <input
                  type="text"
                  placeholder="如 贵州茅台"
                  value={stockName}
                  onChange={(e) => setStockName(e.target.value)}
                  className="input w-32"
                />
              </div>
              <div className="flex items-center gap-2">
                <label className="text-sm font-medium text-foreground">情绪</label>
                <div className="flex items-center gap-1">
                  {[1, 2, 3, 4, 5].map((n) => (
                    <button
                      key={n}
                      type="button"
                      onClick={() => setSentiment(n === sentiment ? 0 : n)}
                      className={cn(
                        'rounded-lg px-2 py-1 text-sm font-medium transition-all',
                        n <= sentiment
                          ? 'border border-yellow-500/40 bg-yellow/10 text-yellow-600'
                          : 'border border-border text-secondary-text hover:border-yellow-500/30 hover:text-yellow-600'
                      )}
                    >
                      {n}
                    </button>
                  ))}
                </div>
              </div>
              <div className="flex items-center gap-2">
                <label className="text-sm font-medium text-foreground">标签</label>
                <input
                  type="text"
                  placeholder="逗号分隔"
                  value={tagsText}
                  onChange={(e) => setTagsText(e.target.value)}
                  className="input w-40"
                />
              </div>
            </div>

            <hr className="border-border/60" />

            {/* ===== 一、我的交易回顾 ===== */}
            <FormSection
              label="一、我的交易回顾"
              value={formData.tradeReview}
              onChange={(v) => updateField('tradeReview', v)}
              placeholder={
                '| 操作 | 标的 | 买卖点 | 逻辑 | 对错 | 错在哪 |\n'
                + '| 买 | 600519 | 09:35 买入 | 看好白酒反弹 | ✅/❌ | |\n'
                + '| 卖 | 002xxx | 14:00 卖出 | 破位止损 | ✅/❌ | |'
              }
              rows={5}
              hint="按表格格式填写每笔操作。自问：是按计划做的还是盘中冲动？"
            />

            <hr className="border-border/60" />

            {/* ===== 二、盘面复盘 ===== */}
            <div>
              <h3 className="mb-3 text-sm font-semibold text-foreground">二、盘面复盘</h3>
              <div className="flex flex-col gap-4">
                {/* 主线三维度 */}
                <div>
                  <p className="mb-2 text-xs font-medium text-secondary-text">主线三维度</p>
                  <div className="grid gap-3 md:grid-cols-3">
                    <FormInput
                      label="龙头股"
                      value={formData.mainDragon}
                      onChange={(v) => updateField('mainDragon', v)}
                      placeholder="如 海能达（高度5板）"
                    />
                    <FormInput
                      label="补涨股"
                      value={formData.mainFollowUp}
                      onChange={(v) => updateField('mainFollowUp', v)}
                      placeholder="补涨标的"
                    />
                    <FormInput
                      label="切换方向"
                      value={formData.mainSwitch}
                      onChange={(v) => updateField('mainSwitch', v)}
                      placeholder="资金切换方向"
                    />
                  </div>
                </div>

                {/* 涨停质量 */}
                <div>
                  <p className="mb-2 text-xs font-medium text-secondary-text">涨停质量</p>
                  <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
                    <FormInput label="一字板" value={formData.limitYiZi} onChange={(v) => updateField('limitYiZi', v)} placeholder="家数" />
                    <FormInput label="换手板" value={formData.limitHuanShou} onChange={(v) => updateField('limitHuanShou', v)} placeholder="家数" />
                    <FormInput label="炸板" value={formData.limitZhaBan} onChange={(v) => updateField('limitZhaBan', v)} placeholder="家数" />
                    <FormInput label="炸板率" value={formData.limitZhaBanRate} onChange={(v) => updateField('limitZhaBanRate', v)} placeholder="如 25" />
                    <FormInput label="最高连板" value={formData.limitMaxLianBan} onChange={(v) => updateField('limitMaxLianBan', v)} placeholder="如 5板" />
                    <FormInput label="连板梯队" value={formData.limitLianBanTier} onChange={(v) => updateField('limitLianBanTier', v)} placeholder="如 5板1家/4板2家" />
                    <FormSelect
                      label="赚钱效应"
                      value={formData.limitProfitEffect}
                      onChange={(v) => updateField('limitProfitEffect', v)}
                      options={[
                        { value: '好', label: '好' },
                        { value: '一般', label: '一般' },
                        { value: '差', label: '差' },
                      ]}
                      placeholder="请选择"
                    />
                  </div>
                </div>

                {/* 情绪周期定位 */}
                <div>
                  <p className="mb-2 text-xs font-medium text-secondary-text">情绪周期定位</p>
                  <div className="grid gap-3 md:grid-cols-3">
                    <FormSelect
                      label="当前阶段"
                      value={formData.cyclePhase}
                      onChange={(v) => updateField('cyclePhase', v)}
                      options={[
                        { value: '低位试错', label: '低位试错' },
                        { value: '主升', label: '主升' },
                        { value: '高位震荡', label: '高位震荡' },
                        { value: '主跌', label: '主跌' },
                      ]}
                      placeholder="请选择"
                    />
                    <FormInput
                      label="关键信号"
                      value={formData.cycleKeySignal}
                      onChange={(v) => updateField('cycleKeySignal', v)}
                      placeholder="龙头分歧 有/无 | 亏钱效应蔓延 有/无 | 情绪极值 有/无"
                      className="md:col-span-2"
                    />
                  </div>
                  <div className="mt-3">
                    <FormSection
                      label="判断依据"
                      value={formData.cycleReasoning}
                      onChange={(v) => updateField('cycleReasoning', v)}
                      placeholder="为什么判断当前处于这个阶段？有什么关键信号支撑？"
                      rows={2}
                    />
                  </div>
                </div>
              </div>
            </div>

            <hr className="border-border/60" />

            {/* ===== 三、昨日预判验证 ===== */}
            <FormSection
              label="三、昨日预判验证"
              value={formData.prevVerify}
              onChange={(v) => updateField('prevVerify', v)}
              placeholder={
                '| 维度 | 昨日判断 | 实际走势 | 对错 | 偏差原因 |\n'
                + '| 大盘方向 | 看多/看空/震荡 | 实际走势 | ✅/❌ | 原因 |\n'
                + '| 主线方向 | 强化/分歧/切换 | 实际表现 | ✅/❌ | 原因 |\n'
                + '| 核心个股 | 预期 | 实际 | ✅/❌ | 原因 |'
              }
              rows={5}
              hint="连续 2 天预判偏差 > 50%，停下来只观察不交易"
            />

            <hr className="border-border/60" />

            {/* ===== 四、明日预判 ===== */}
            <div>
              <h3 className="mb-3 text-sm font-semibold text-foreground">四、明日预判</h3>
              <div className="flex flex-col gap-4">
                <div className="grid gap-3 md:grid-cols-3">
                  <FormSelect
                    label="大盘方向"
                    value={formData.tomorrowDirection}
                    onChange={(v) => updateField('tomorrowDirection', v)}
                    options={[
                      { value: '看多', label: '看多' },
                      { value: '看空', label: '看空' },
                      { value: '震荡', label: '震荡' },
                    ]}
                    placeholder="请选择"
                  />
                  <FormSelect
                    label="主线延续"
                    value={formData.tomorrowMainline}
                    onChange={(v) => updateField('tomorrowMainline', v)}
                    options={[
                      { value: '强化', label: '强化' },
                      { value: '分歧', label: '分歧' },
                      { value: '切换', label: '切换' },
                    ]}
                    placeholder="请选择"
                  />
                  <FormSelect
                    label="情绪演化"
                    value={formData.tomorrowSentiment}
                    onChange={(v) => updateField('tomorrowSentiment', v)}
                    options={[
                      { value: '继续', label: '继续' },
                      { value: '退潮', label: '退潮' },
                      { value: '冰点反弹', label: '冰点反弹' },
                    ]}
                    placeholder="请选择"
                  />
                </div>
                <div className="grid gap-3 md:grid-cols-3">
                  <FormSection
                    label="大盘方向依据"
                    value={formData.tomorrowDirectionReason}
                    onChange={(v) => updateField('tomorrowDirectionReason', v)}
                    placeholder="判断理由"
                    rows={2}
                  />
                  <FormSection
                    label="主线延续依据"
                    value={formData.tomorrowMainlineReason}
                    onChange={(v) => updateField('tomorrowMainlineReason', v)}
                    placeholder="判断理由"
                    rows={2}
                  />
                  <FormSection
                    label="情绪演化依据"
                    value={formData.tomorrowSentimentReason}
                    onChange={(v) => updateField('tomorrowSentimentReason', v)}
                    placeholder="判断理由"
                    rows={2}
                  />
                </div>
                <div className="grid gap-3 md:grid-cols-3">
                  <FormInput
                    label="仓位计划"
                    value={formData.tomorrowPosition}
                    onChange={(v) => updateField('tomorrowPosition', v)}
                    placeholder="如 5成仓 / 空仓"
                  />
                </div>
                <FormSection
                  label="核心买点计划（如果有）"
                  value={formData.tomorrowBuyPlan}
                  onChange={(v) => updateField('tomorrowBuyPlan', v)}
                  placeholder="具体的买入标的、条件、仓位"
                  rows={2}
                />
                <FormSection
                  label="失效条件（什么情况证明判断错了）"
                  value={formData.tomorrowInvalidCondition}
                  onChange={(v) => updateField('tomorrowInvalidCondition', v)}
                  placeholder="提前想好判断错误的信号，到了就执行备用方案"
                  rows={2}
                />
              </div>
            </div>

            <hr className="border-border/60" />

            {/* ===== 五、知行合一检查 ===== */}
            <div>
              <h3 className="mb-3 text-sm font-semibold text-foreground">五、知行合一检查</h3>
              <div className="flex flex-col gap-3">
                <label className="flex items-center gap-3 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={formData.checkExecuted}
                    onChange={(e) => updateField('checkExecuted', e.target.checked)}
                    className="h-4 w-4 rounded border-border accent-primary"
                  />
                  <span className="text-sm text-foreground">今天是否执行了昨晚的计划？</span>
                </label>
                <label className="flex items-center gap-3 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={formData.checkOutside}
                    onChange={(e) => updateField('checkOutside', e.target.checked)}
                    className="h-4 w-4 rounded border-border accent-primary"
                  />
                  <span className="text-sm text-foreground">盘中是否有计划外的操作？</span>
                </label>
                {formData.checkOutside && (
                  <FormSection
                    label="计划外操作触发原因"
                    value={formData.checkOutsideReason}
                    onChange={(v) => updateField('checkOutsideReason', v)}
                    placeholder="是什么触发了计划外操作？冲动 / 消息 / 他人推荐？"
                    rows={2}
                  />
                )}
              </div>
            </div>

            <hr className="border-border/60" />

            {/* ===== 六、系统完善 ===== */}
            <div>
              <h3 className="mb-3 text-sm font-semibold text-foreground">六、系统完善</h3>
              <div className="flex flex-col gap-4">
                <FormSection
                  label="今天学到的最重要 1 条"
                  value={formData.learnedToday}
                  onChange={(v) => updateField('learnedToday', v)}
                  placeholder="今天最大的认知收获是什么？"
                  rows={2}
                />
                <FormSection
                  label="需要修正的认知 / 规则"
                  value={formData.cognitionFix}
                  onChange={(v) => updateField('cognitionFix', v)}
                  placeholder="哪些之前的认知被今天的盘面证伪了？"
                  rows={2}
                />
                <FormSection
                  label="今天的错误能否提炼成一条纪律？"
                  value={formData.disciplineRule}
                  onChange={(v) => updateField('disciplineRule', v)}
                  placeholder="如果今天犯了错，能否变成一条今后遵守的纪律？"
                  rows={2}
                />
              </div>
            </div>
          </div>

          {/* Recent reviews */}
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-semibold text-foreground">近期复盘记录</h2>
            <button
              type="button"
              className="btn-ghost flex items-center gap-1 text-xs"
              onClick={() => navigate('/xinfa?category=review')}
            >
              查看全部
              <ArrowLeft className="h-3 w-3 rotate-180" />
            </button>
          </div>

          {reviewsLoading ? (
            <div className="flex items-center justify-center py-8">
              <Loading />
            </div>
          ) : reviews.length === 0 ? (
            <EmptyState
              icon={<BookHeart className="h-10 w-10" />}
              title="还没有复盘记录"
              description="填写上方表单并保存，复盘记录会出现在这里"
            />
          ) : (
            <div className="grid gap-3 md:grid-cols-2">
              {reviews.map((entry) => (
                <ReviewCard
                  key={entry.id}
                  entry={entry}
                  onEdit={() => handleEdit(entry)}
                />
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
};

export default XinfaReviewPage;
