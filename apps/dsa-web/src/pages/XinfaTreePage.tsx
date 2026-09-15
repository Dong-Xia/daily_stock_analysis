import type React from 'react';
import { useCallback, useEffect, useRef, useState } from 'react';
import {
  ArrowLeft,
  FilePlus,
  GripVertical,
  Plus,
  TreePine,
  Trash2,
  X,
} from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { EmptyState } from '../components/common';
import type { KnowledgeTree, TreeNode } from '../types/xinfa';
import { createEmptyNode, createEmptyTree, createNodeId } from '../types/xinfa';
import { cn } from '../utils/cn';

// ---------------------------------------------------------------------------
// Storage
// ---------------------------------------------------------------------------

const STORAGE_KEY = 'xinfa_knowledge_trees';

function loadTrees(): KnowledgeTree[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) return JSON.parse(raw) as KnowledgeTree[];
  } catch { /* ignore */ }
  return [];
}

function saveTrees(trees: KnowledgeTree[]) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(trees));
}

// ---------------------------------------------------------------------------
// Seed Data — 涅盘重升 + 五游资核心知识树
// ---------------------------------------------------------------------------

function seedTrees(): KnowledgeTree[] {
  return [
    {
      id: createNodeId(),
      title: '涅盘重升交易系统',
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
      nodes: [
        {
          id: createNodeId(),
          label: '投机 = 赚钱效应的延续',
          description: '市场投机的本质是赚钱效应的扩散和消退。赚钱效应强则资金涌入，赚钱效应弱则资金离场。',
          collapsed: false,
          children: [
            {
              id: createNodeId(),
              label: '六大情绪体系',
              description: '投机情绪(涨停数/连板高度/炸板率)、市场情绪(指数强度/涨跌比)、板块情绪(资金偏好/主升强度)、整体市场情绪(综合赚钱效应)、整体投机情绪(整体投机氛围)、整体板块情绪(龙头持续打高度)',
              collapsed: false,
              children: [],
            },
            {
              id: createNodeId(),
              label: '确定性 = 打板 + 做核心',
              description: '好行情不打板容易错失机会，差行情不打板容易犯错。选股一定要做核心股，市场地位最重要。',
              collapsed: true,
              children: [],
            },
            {
              id: createNodeId(),
              label: '资金总是流向阻力最小的方向',
              description: '理解资金的偏好和阻力位，就能预判下一个热点方向。',
              collapsed: true,
              children: [],
            },
            {
              id: createNodeId(),
              label: '炒作情绪占7成，图形只占3成',
              description: '如果题材强度够，弱图形也能大肉；题材不够，强图形也会面。首板重题材，高位板重情绪。',
              collapsed: true,
              children: [],
            },
            {
              id: createNodeId(),
              label: '最容易亏钱的5种情形',
              description: '1)最有赚钱效应板块的对立面 2)末期机会风险大 3)非主流冷门重仓 4)系统性风险 5)市场情绪差抓小转折',
              collapsed: true,
              children: [],
            },
          ],
        },
        {
          id: createNodeId(),
          label: '系统 = 树干 + 树枝',
          description: '把股市认知整理成树干(主要思想)和树枝(小规律)。没有系统，知识就像散沙被行情吹散。',
          collapsed: false,
          children: [
            {
              id: createNodeId(),
              label: '复盘 → 验证 → 融入系统 → 进化',
              description: '每天复盘输出结论，第二天去市场验证。验证有效→进化为树枝/树干；验证无效→果断砍掉。',
              collapsed: true,
              children: [],
            },
            {
              id: createNodeId(),
              label: '放弃才能拥有',
              description: '什么小机会都抓反而做不好。成功来自不断主动放弃看不懂的机会，只抓确定的部分。',
              collapsed: true,
              children: [],
            },
            {
              id: createNodeId(),
              label: '推倒重来的勇气',
              description: '不是每一次坚持都是对的。早期总结的"小规律"后来发现是错的，果断推翻，不抱残守缺。',
              collapsed: true,
              children: [],
            },
          ],
        },
        {
          id: createNodeId(),
          label: '预判能力',
          description: '所有的操作都来自对当天盘面强势方向的跟随预判和对明日的预判。这是涅盘区别于普通打板客的最大特点。',
          collapsed: false,
          children: [
            {
              id: createNodeId(),
              label: '明日不看好 → 一字板也走',
              description: '即使自己持股一字涨停，判断后排跟风走弱/板块退潮，果断一字板离场。案例：超级细菌概念一字板离场，次日被核按钮。',
              collapsed: true,
              children: [],
            },
            {
              id: createNodeId(),
              label: '明日看好 → 尾盘竞价也要上仓位',
              description: '看好次日走势，不等明天竞价，今天尾盘就拿先手。预判机会时进攻，预判风险时防守。',
              collapsed: true,
              children: [],
            },
            {
              id: createNodeId(),
              label: '龙头走弱 → 后排不要碰',
              description: '龙头走弱后，后排拉板不要去追，追高容易吃面。但低吸提前调整过的后排反而安全。',
              collapsed: true,
              children: [],
            },
          ],
        },
        {
          id: createNodeId(),
          label: '仓位管理 = 复利的基础',
          description: '稳定性是最终归宿。从满仓梭哈到分仓分批，回撤从48%降到不足3%。',
          collapsed: true,
          children: [
            {
              id: createNodeId(),
              label: '大部分1-2成仓操作一支',
              description: '三分之一就算重仓。两个月里只有三四次单票超过半仓。',
              collapsed: true,
              children: [],
            },
            {
              id: createNodeId(),
              label: '大跌时最好的防守是空仓',
              description: '非顶级水平的人在大跌时任何试探性操作最终大概率还是吃亏。管住手也是能力。',
              collapsed: true,
              children: [],
            },
          ],
        },
      ],
    },
    {
      id: createNodeId(),
      title: '92科比 — 情绪周期',
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
      nodes: [
        {
          id: createNodeId(),
          label: '三支柱：龙头 + 补涨 + 切换',
          description: '做龙头(主升段/加速段)、做补涨(最强方向低位找类似)、做切换(板块内部高低切/板块间切换/风格切换)。中位股最危险。',
          collapsed: false,
          children: [
            {
              id: createNodeId(),
              label: '低位试错期',
              description: '题材冰点、轮动、无主线。操作：打首板/低位补涨/切换新题材。',
              collapsed: true,
              children: [],
            },
            {
              id: createNodeId(),
              label: '主升期',
              description: '主线确认、龙头打出高度、普涨。操作：买龙头(任何位置进都对)/补涨/潜伏。',
              collapsed: true,
              children: [],
            },
            {
              id: createNodeId(),
              label: '高位震荡期',
              description: '龙头滞涨、板块分化。操作：轻仓应对/低位补涨/挖掘低位。',
              collapsed: true,
              children: [],
            },
            {
              id: createNodeId(),
              label: '主跌期',
              description: '龙头人气股大跌。操作：切换新题材/搏反弹(连续大跌两天尾盘买入)。',
              collapsed: true,
              children: [],
            },
          ],
        },
        {
          id: createNodeId(),
          label: '10万分仓，不加杠杆',
          description: '分仓至关重要。赚钱是行情给予的，永远不要重仓赌。',
          collapsed: true,
          children: [],
        },
      ],
    },
    {
      id: createNodeId(),
      title: '北京炒家 — 首板系统',
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
      nodes: [
        {
          id: createNodeId(),
          label: '纯粹首板，隔日交易',
          description: '只做低位首板，不做二板接力、不做高位板、不做龙头板。次日必换股，从不满仓过夜格局。',
          collapsed: false,
          children: [
            {
              id: createNodeId(),
              label: '首板四类型',
              description: '秒拉板(排板+板块效应)、回封板(炸板回封更安全)、换手板(5-8点横盘30分钟后扫板)、尾盘板(两点半后不打)。',
              collapsed: true,
              children: [],
            },
            {
              id: createNodeId(),
              label: '交易八法',
              description: '市场风格/赚钱板块/指数共振/赔率>胜率/龙头理解/交易一致性/尊重市场/历史重演。',
              collapsed: true,
              children: [],
            },
          ],
        },
        {
          id: createNodeId(),
          label: '慢就是快',
          description: '复利是世界第八大奇迹，稳定性是最终归宿。最大回撤控制在3%以内。',
          collapsed: true,
          children: [],
        },
      ],
    },
    {
      id: createNodeId(),
      title: '陈小群 — 龙头战法',
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
      nodes: [
        {
          id: createNodeId(),
          label: '只做市场合力总龙头',
          description: '散户最大的误区是以为游资抱团，其实是市场合力。合力才是龙头的本质。',
          collapsed: false,
          children: [
            {
              id: createNodeId(),
              label: '龙头首阴反包',
              description: '龙头首阴大概率有反包。总龙头首阴后反包→行情继续高歌；首阴后被按→市场将有调整。',
              collapsed: true,
              children: [],
            },
            {
              id: createNodeId(),
              label: '该弱不弱视为强，该强不强视为弱',
              description: '大单卖出但封单增大→市场合力大，要加速。跌时缩量→资金锁仓。',
              collapsed: true,
              children: [],
            },
          ],
        },
        {
          id: createNodeId(),
          label: '用功钻研',
          description: '做主线、研究情绪、研究内在逻辑、钻研重要性(一个问题在家想一整天)、纪律性。',
          collapsed: true,
          children: [],
        },
      ],
    },
    {
      id: createNodeId(),
      title: '一瞬流光 — 高位接力',
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
      nodes: [
        {
          id: createNodeId(),
          label: '买入分歧，卖出一致',
          description: '涨势中分歧=买点：越不舒服的买点越大肉。人气龙头股分歧时进场，锁仓到两个涨停板后第三天退场。',
          collapsed: false,
          children: [
            {
              id: createNodeId(),
              label: '杜绝临时起意',
              description: '只计划操作——大亏的根源就是临时起意。先处理好手里的，再开始下一笔。',
              collapsed: true,
              children: [],
            },
            {
              id: createNodeId(),
              label: '满仓三条件',
              description: '满仓打的板必须符合：指数单边上涨 + 板块当日核心 + 个股人气容量核心。',
              collapsed: true,
              children: [],
            },
          ],
        },
        {
          id: createNodeId(),
          label: '永远只看龙头',
          description: '少看杂毛弱转强，那是大面源泉。天天在杂毛里混，看不清市场。',
          collapsed: true,
          children: [],
        },
      ],
    },
  ];
}

// ---------------------------------------------------------------------------
// Node Modal
// ---------------------------------------------------------------------------

type NodeModalProps = {
  isOpen: boolean;
  title: string;
  initialLabel: string;
  initialDescription: string;
  onSave: (label: string, description: string) => void;
  onClose: () => void;
};

const NodeModal: React.FC<NodeModalProps> = ({
  isOpen,
  title,
  initialLabel,
  initialDescription,
  onSave,
  onClose,
}) => {
  const [label, setLabel] = useState(initialLabel);
  const [description, setDescription] = useState(initialDescription);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (isOpen) {
      setLabel(initialLabel);
      setDescription(initialDescription);
      setTimeout(() => inputRef.current?.focus(), 50);
    }
  }, [isOpen, initialLabel, initialDescription]);

  if (!isOpen) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div className="flex w-full max-w-lg flex-col rounded-2xl border border-border bg-card shadow-2xl">
        <div className="flex items-center justify-between border-b border-border px-6 py-4">
          <h2 className="text-base font-semibold text-foreground">{title}</h2>
          <button type="button" onClick={onClose} className="btn-ghost rounded-lg p-1.5">
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="flex flex-col gap-4 p-6">
          <div>
            <label className="mb-1.5 block text-xs font-medium text-secondary-text">名称</label>
            <input
              ref={inputRef}
              type="text"
              value={label}
              onChange={(e) => setLabel(e.target.value)}
              className="input w-full"
              placeholder="输入名称..."
              onKeyDown={(e) => {
                if (e.key === 'Enter' && label.trim()) {
                  onSave(label.trim(), description.trim());
                }
              }}
            />
          </div>
          <div>
            <label className="mb-1.5 block text-xs font-medium text-secondary-text">详细说明</label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              className="input w-full min-h-[100px] resize-y"
              placeholder="输入说明（支持多行）..."
              rows={4}
            />
          </div>
        </div>

        <div className="flex justify-end gap-3 border-t border-border px-6 py-4">
          <button type="button" className="btn-ghost" onClick={onClose}>
            取消
          </button>
          <button
            type="button"
            className="btn-primary"
            disabled={!label.trim()}
            onClick={() => onSave(label.trim(), description.trim())}
          >
            保存
          </button>
        </div>
      </div>
    </div>
  );
};

// ---------------------------------------------------------------------------
// Tree Diagram — SVG 树形可视化
// ---------------------------------------------------------------------------

const TREE_NODE_W = 176;
const TREE_NODE_H = 58;
const TREE_GAP_H = 20;
const TREE_GAP_V = 80;

interface LayoutNode {
  id: string;
  x: number;
  y: number;
  w: number;
  h: number;
}

function computeTreeLayout(node: TreeNode, depth = 0): { nodes: LayoutNode[]; totalW: number } {
  const nodeW = Math.max(140, TREE_NODE_W - depth * 12);
  const nodeH = TREE_NODE_H;

  if (node.children.length === 0 || node.collapsed) {
    return {
      nodes: [{ id: node.id, x: nodeW / 2, y: depth * (nodeH + TREE_GAP_V), w: nodeW, h: nodeH }],
      totalW: nodeW,
    };
  }

  const childResults = node.children.map((c) => computeTreeLayout(c, depth + 1));
  const totalChildW = childResults.reduce((s, r) => s + r.totalW, 0) + TREE_GAP_H * (node.children.length - 1);
  const totalW = Math.max(nodeW, totalChildW);

  const startX = (totalW - totalChildW) / 2;
  let cx = startX;
  const childNodes: LayoutNode[] = [];

  for (let i = 0; i < node.children.length; i++) {
    for (const n of childResults[i].nodes) {
      childNodes.push({ ...n, x: n.x + cx, y: n.y });
    }
    cx += childResults[i].totalW + TREE_GAP_H;
  }

  return {
    nodes: [{ id: node.id, x: totalW / 2, y: depth * (nodeH + TREE_GAP_V), w: nodeW, h: nodeH }, ...childNodes],
    totalW,
  };
}

type TreeDiagramProps = {
  root: TreeNode;
  onEdit: (id: string) => void;
  onDelete: (id: string) => void;
  onAddChild: (id: string) => void;
  onToggleCollapse: (id: string) => void;
};

function nodeToSvgPath(
  parent: LayoutNode,
  child: LayoutNode,
): string {
  const x1 = parent.x;
  const y1 = parent.y + parent.h;
  const x2 = child.x;
  const y2 = child.y;
  const cy = (y1 + y2) / 2;
  return `M ${x1} ${y1} C ${x1} ${cy}, ${x2} ${cy}, ${x2} ${y2}`;
}

const TreeDiagram: React.FC<TreeDiagramProps> = ({
  root,
  onEdit,
  onDelete,
  onAddChild,
  onToggleCollapse,
}) => {
  const { nodes, totalW } = computeTreeLayout(root);
  const totalH = nodes.length > 0
    ? Math.max(...nodes.map((n) => n.y)) + TREE_NODE_H + 40
    : 200;

  const layoutMap = new Map(nodes.map((n) => [n.id, n]));

  // Build parent-child pairs for SVG lines
  const pairs: Array<[LayoutNode, LayoutNode]> = [];
  function collectPairs(node: TreeNode) {
    const pNode = layoutMap.get(node.id);
    if (!pNode) return;
    for (const child of node.children) {
      const cNode = layoutMap.get(child.id);
      if (cNode && !node.collapsed) {
        pairs.push([pNode, cNode]);
        collectPairs(child);
      }
    }
  }
  collectPairs(root);

  return (
    <div className="overflow-auto">
      <div
        className="relative mx-auto"
        style={{ width: Math.max(totalW + 80, 400), minHeight: totalH, padding: '20px 40px 40px' }}
      >
        {/* SVG lines */}
        <svg
          className="pointer-events-none absolute inset-0"
          style={{ width: '100%', height: '100%' }}
        >
          <defs>
            <linearGradient id="branchGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="hsl(var(--amber) / 0.3)" />
              <stop offset="100%" stopColor="hsl(var(--amber) / 0.08)" />
            </linearGradient>
          </defs>
          {pairs.map(([p, c]) => (
            <path
              key={`${p.id}-${c.id}`}
              d={nodeToSvgPath(p, c)}
              fill="none"
              stroke="hsl(var(--amber) / 0.25)"
              strokeWidth={1.5}
              strokeLinecap="round"
            />
          ))}
        </svg>

        {/* Nodes */}
        {nodes.map((ln) => {
          const node = findNodeInTree(root, ln.id);
          if (!node) return null;
          const isTrunk = ln.y === 0;
          const hasChildren = node.children.length > 0;

          return (
            <div
              key={ln.id}
              className="group absolute"
              style={{
                left: ln.x - ln.w / 2,
                top: ln.y,
                width: ln.w,
              }}
            >
              {/* Collapse button (dot/circle above card) */}
              {hasChildren && (
                <button
                  type="button"
                  onClick={() => onToggleCollapse(node.id)}
                  className="absolute left-1/2 -translate-x-1/2 flex items-center justify-center rounded-full transition-all hover:bg-amber/10"
                  style={{ top: -18, width: 24, height: 24 }}
                  title={node.collapsed ? '展开' : '收起'}
                >
                  <div
                    className={cn(
                      'h-2 w-2 rounded-full transition-all',
                      node.collapsed ? 'bg-amber/30' : 'bg-amber/50',
                    )}
                  />
                </button>
              )}

              {/* Card */}
              <div
                className={cn(
                  'rounded-xl border transition-all cursor-pointer',
                  isTrunk
                    ? 'border-amber/25 bg-gradient-to-br from-amber/[0.05] to-transparent shadow-sm hover:border-amber/40 hover:shadow-md'
                    : 'border-border/50 bg-card hover:border-border/80 hover:shadow-sm',
                )}
                style={{ minHeight: TREE_NODE_H }}
                onClick={() => onEdit(node.id)}
              >
                <div className="flex flex-col p-2.5">
                  <div className="flex items-start justify-between gap-1">
                    <div className="min-w-0 flex-1">
                      {isTrunk && (
                        <span className="inline-block rounded-md bg-amber/10 px-1.5 py-0.5 text-[9px] font-medium text-amber mb-1">
                          树干
                        </span>
                      )}
                      <div
                        className={cn(
                          'font-medium leading-snug text-foreground',
                          isTrunk ? 'text-sm' : 'text-xs',
                        )}
                      >
                        {node.label}
                      </div>
                      {node.description && (
                        <div className="mt-1 text-[10px] leading-relaxed text-secondary-text line-clamp-2">
                          {node.description}
                        </div>
                      )}
                    </div>
                  </div>

                  {/* Hover actions */}
                  <div className="mt-1.5 flex items-center gap-1 opacity-0 transition-opacity group-hover:opacity-100">
                    <button
                      type="button"
                      onClick={(e) => { e.stopPropagation(); onAddChild(node.id); }}
                      className="rounded-md p-1 text-secondary-text transition-colors hover:bg-amber/10 hover:text-amber"
                      title={isTrunk ? '添加树枝' : '添加子分支'}
                    >
                      <Plus className="h-3 w-3" />
                    </button>
                    <button
                      type="button"
                      onClick={(e) => { e.stopPropagation(); onEdit(node.id); }}
                      className="rounded-md p-1 text-secondary-text transition-colors hover:bg-hover hover:text-foreground"
                      title="编辑"
                    >
                      <GripVertical className="h-3 w-3" />
                    </button>
                    <button
                      type="button"
                      onClick={(e) => { e.stopPropagation(); onDelete(node.id); }}
                      className="rounded-md p-1 text-secondary-text transition-colors hover:bg-red/10 hover:text-red"
                      title="删除"
                    >
                      <Trash2 className="h-3 w-3" />
                    </button>
                  </div>
                </div>
              </div>
            </div>
          );
        })}

        {/* Add trunk button below empty areas */}
        {nodes.length === 1 && root.children.length === 0 && !root.collapsed && (
          <div
            className="absolute flex items-start justify-center"
            style={{ left: totalW / 2 + 100, top: TREE_NODE_H + 20 }}
          >
            <button
              type="button"
              onClick={() => onAddChild(root.id)}
              className="flex items-center gap-1 rounded-lg border border-dashed border-border/40 px-3 py-2 text-xs text-secondary-text transition-all hover:border-amber/30 hover:text-amber hover:bg-amber/[0.03]"
            >
              <Plus className="h-3.5 w-3.5" />
              添加分支
            </button>
          </div>
        )}
      </div>
    </div>
  );
};

function findNodeInTree(node: TreeNode, id: string): TreeNode | null {
  if (node.id === id) return node;
  for (const child of node.children) {
    const found = findNodeInTree(child, id);
    if (found) return found;
  }
  return null;
}

// ---------------------------------------------------------------------------
// Main Page
// ---------------------------------------------------------------------------

const XinfaTreePage: React.FC = () => {
  const navigate = useNavigate();

  const [trees, setTrees] = useState<KnowledgeTree[]>([]);
  const [activeTreeId, setActiveTreeId] = useState<string | null>(null);
  const [showSeeder, setShowSeeder] = useState(false);

  const [modalOpen, setModalOpen] = useState(false);
  const [modalTitle, setModalTitle] = useState('');
  const [editingNodeKey, setEditingNodeKey] = useState<string | null>(null);
  const [editingLabel, setEditingLabel] = useState('');
  const [editingDescription, setEditingDescription] = useState('');

  const [renameOpen, setRenameOpen] = useState(false);
  const [renameTreeId, setRenameTreeId] = useState<string | null>(null);
  const [renameValue, setRenameValue] = useState('');

  const [selectedTrunkId, setSelectedTrunkId] = useState<string | null>(null);

  useEffect(() => {
    document.title = '树干树枝 - DSA';
    const saved = loadTrees();
    if (saved.length > 0) {
      setTrees(saved);
      setActiveTreeId(saved[0].id);
    } else {
      setShowSeeder(true);
    }
  }, []);

  // Auto-select first trunk when tree changes
  useEffect(() => {
    const tree = trees.find((t) => t.id === activeTreeId);
    if (tree && tree.nodes.length > 0) {
      const currentInTree = tree.nodes.some((n) => n.id === selectedTrunkId);
      if (!currentInTree) {
        setSelectedTrunkId(tree.nodes[0].id);
      }
    } else {
      setSelectedTrunkId(null);
    }
  }, [activeTreeId, trees]);

  const persist = useCallback((updated: KnowledgeTree[]) => {
    setTrees(updated);
    saveTrees(updated);
  }, []);

  function findNode(nodes: TreeNode[], id: string): TreeNode | null {
    for (const n of nodes) {
      if (n.id === id) return n;
      if (n.children.length > 0) {
        const found = findNode(n.children, id);
        if (found) return found;
      }
    }
    return null;
  }

  function mapNodes(nodes: TreeNode[], id: string, fn: (n: TreeNode) => TreeNode): TreeNode[] {
    return nodes.map((n) => {
      if (n.id === id) return fn(n);
      if (n.children.length > 0) return { ...n, children: mapNodes(n.children, id, fn) };
      return n;
    });
  }

  function filterNodes(nodes: TreeNode[], id: string): TreeNode[] {
    return nodes
      .filter((n) => n.id !== id)
      .map((n) => ({
        ...n,
        children: n.children.length > 0 ? filterNodes(n.children, id) : [],
      }));
  }

  // --- Actions ---

  function addTrunk(treeId: string) {
    const trunk = createEmptyNode('新树干');
    const updated = trees.map((t) => {
      if (t.id !== treeId) return t;
      return { ...t, nodes: [...t.nodes, trunk], updatedAt: new Date().toISOString() };
    });
    persist(updated);
    openNodeModal('编辑树干', treeId, trunk.id);
  }

  function addChildNode(treeId: string, parentId: string) {
    const updated = trees.map((t) => {
      if (t.id !== treeId) return t;
      const child = createEmptyNode('新分支');
      const newNodes = mapNodes(t.nodes, parentId, (n) => ({
        ...n,
        children: [...n.children, child],
        collapsed: false,
      }));
      return { ...t, nodes: newNodes, updatedAt: new Date().toISOString() };
    });
    persist(updated);
    const tree = updated.find((t) => t.id === treeId);
    if (tree) {
      const parent = findNode(tree.nodes, parentId);
      if (parent && parent.children.length > 0) {
        const newChildId = parent.children[parent.children.length - 1].id;
        openNodeModal('编辑分支', treeId, newChildId);
      }
    }
  }

  function deleteNode(treeId: string, nodeId: string) {
    if (!window.confirm('确认删除这个节点及其所有子节点？')) return;
    const updated = trees.map((t) => {
      if (t.id !== treeId) return t;
      return { ...t, nodes: filterNodes(t.nodes, nodeId), updatedAt: new Date().toISOString() };
    });
    persist(updated);
  }

  function toggleCollapse(treeId: string, nodeId: string) {
    const updated = trees.map((t) => {
      if (t.id !== treeId) return t;
      return {
        ...t,
        nodes: mapNodes(t.nodes, nodeId, (n) => ({ ...n, collapsed: !n.collapsed })),
      };
    });
    persist(updated);
  }

  function openNodeDialog(treeId: string, nodeId: string) {
    const tree = trees.find((t) => t.id === treeId);
    if (!tree) return;
    const node = findNode(tree.nodes, nodeId);
    if (!node) return;

    const depth = getNodeDepth(tree.nodes, nodeId);
    const label = depth === 0 ? '编辑树干' : '编辑分支';
    const key = `${treeId}::${nodeId}`;

    setModalTitle(label);
    setEditingNodeKey(key);
    setEditingLabel(node.label);
    setEditingDescription(node.description);
    setModalOpen(true);
  }

  function openNodeModal(title: string, treeId: string, nodeId: string) {
    const key = `${treeId}::${nodeId}`;
    setModalTitle(title);
    setEditingNodeKey(key);
    setEditingLabel('');
    setEditingDescription('');
    setModalOpen(true);
  }

  function getNodeDepth(nodes: TreeNode[], targetId: string, depth = 0): number {
    for (const n of nodes) {
      if (n.id === targetId) return depth;
      if (n.children.length > 0) {
        const d = getNodeDepth(n.children, targetId, depth + 1);
        if (d >= 0) return d;
      }
    }
    return -1;
  }

  function handleModalSave(label: string, description: string) {
    if (!editingNodeKey) return;
    const [treeId, nodeId] = editingNodeKey.split('::');

    const updated = trees.map((t) => {
      if (t.id !== treeId) return t;
      return {
        ...t,
        nodes: mapNodes(t.nodes, nodeId, (n) => ({ ...n, label, description })),
        updatedAt: new Date().toISOString(),
      };
    });
    persist(updated);
    setModalOpen(false);
    setEditingNodeKey(null);
  }

  function handleNewTree() {
    const newTree = createEmptyTree(`知识树 ${trees.length + 1}`);
    persist([...trees, newTree]);
    setActiveTreeId(newTree.id);
  }

  function handleDeleteTree(treeId: string) {
    if (!window.confirm('确认删除整棵知识树？此操作不可恢复。')) return;
    const updated = trees.filter((t) => t.id !== treeId);
    persist(updated);
    if (activeTreeId === treeId) {
      setActiveTreeId(updated.length > 0 ? updated[0].id : null);
    }
  }

  function handleSeed() {
    persist(seedTrees());
    setActiveTreeId(seedTrees()[0].id);
    setShowSeeder(false);
  }

  const activeTree = trees.find((t) => t.id === activeTreeId) ?? null;

  return (
    <div className="flex h-full flex-col gap-4 p-4 md:p-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={() => navigate('/xinfa')}
            className="btn-ghost rounded-lg p-2"
            title="返回心法"
          >
            <ArrowLeft className="h-5 w-5" />
          </button>
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-amber/15 text-amber">
            <TreePine className="h-5 w-5" />
          </div>
          <div>
            <h1 className="text-lg font-semibold text-foreground">树干树枝</h1>
            <p className="text-xs text-secondary-text">构建你的交易知识树，树干+树枝不断进化</p>
          </div>
        </div>

        {!showSeeder && trees.length > 0 && (
          <div className="flex items-center gap-2">
            <button
              type="button"
              className="btn-ghost flex items-center gap-2 text-sm"
              onClick={handleNewTree}
            >
              <FilePlus className="h-4 w-4" />
              <span className="hidden sm:inline">新建知识树</span>
            </button>
          </div>
        )}
      </div>

      {showSeeder && trees.length === 0 ? (
        <div className="flex flex-1 items-center justify-center">
          <EmptyState
            icon={<TreePine className="h-14 w-14" />}
            title="还没有知识树"
            description="根据五位游资的体系，初始化示例知识树开始使用"
            action={
              <div className="mt-4 flex flex-col items-center gap-3">
                <button
                  type="button"
                  className="btn-primary flex items-center gap-2"
                  onClick={handleSeed}
                >
                  <TreePine className="h-4 w-4" />
                  初始化示例知识树
                </button>
                <button
                  type="button"
                  className="btn-ghost flex items-center gap-2 text-sm"
                  onClick={() => {
                    const newTree = createEmptyTree('我的知识树');
                    persist([newTree]);
                    setActiveTreeId(newTree.id);
                    setShowSeeder(false);
                  }}
                >
                  <Plus className="h-4 w-4" />
                  从空白开始
                </button>
              </div>
            }
          />
        </div>
      ) : (
        <div className="flex flex-1 gap-0 overflow-hidden">
          {trees.length > 1 && (
            <div className="hidden w-56 shrink-0 flex-col gap-1 overflow-y-auto border-r border-border/40 pr-3 md:flex">
              {trees.map((t) => (
                <button
                  key={t.id}
                  type="button"
                  onClick={() => {
                    setActiveTreeId(t.id);
                    setSelectedTrunkId(t.nodes[0]?.id ?? null);
                  }}
                  className={cn(
                    'flex items-center gap-2 rounded-lg px-3 py-2 text-left text-sm transition-all',
                    activeTreeId === t.id
                      ? 'bg-amber/10 text-amber font-medium'
                      : 'text-secondary-text hover:bg-hover hover:text-foreground'
                  )}
                >
                  <TreePine className="h-4 w-4 shrink-0" />
                  <span className="truncate">{t.title}</span>
                </button>
              ))}
            </div>
          )}

          <div className="flex-1 overflow-y-auto pb-8">
            {activeTree && (
              <div className="flex flex-col gap-4">
                {/* Tree header */}
                <div className="group flex items-center justify-between px-1">
                  <div className="flex items-center gap-2">
                    <TreePine className="h-5 w-5 text-amber" />
                    <span className="text-base font-semibold text-foreground">{activeTree.title}</span>
                  </div>
                  <div className="flex items-center gap-1 opacity-0 transition-opacity group-hover:opacity-100">
                    <button
                      type="button"
                      onClick={() => {
                        setRenameTreeId(activeTree.id);
                        setRenameValue(activeTree.title);
                        setRenameOpen(true);
                      }}
                      className="rounded-lg px-2 py-1 text-xs text-secondary-text transition-colors hover:bg-hover hover:text-foreground"
                    >
                      重命名
                    </button>
                    <button
                      type="button"
                      onClick={() => handleDeleteTree(activeTree.id)}
                      className="rounded-lg px-2 py-1 text-xs text-secondary-text transition-colors hover:bg-red/10 hover:text-red"
                    >
                      删除
                    </button>
                  </div>
                </div>

                {/* Trunk selector */}
                {activeTree.nodes.length > 1 && (
                  <div className="flex flex-wrap items-center gap-2 px-1">
                    {activeTree.nodes.map((trunk) => (
                      <button
                        key={trunk.id}
                        type="button"
                        onClick={() => setSelectedTrunkId(trunk.id)}
                        className={cn(
                          'rounded-lg border px-3 py-1.5 text-xs transition-all',
                          selectedTrunkId === trunk.id
                            ? 'border-amber/40 bg-amber/10 text-amber font-medium'
                            : 'border-border/40 text-secondary-text hover:border-border hover:text-foreground'
                        )}
                      >
                        {trunk.label}
                      </button>
                    ))}
                    <button
                      type="button"
                      onClick={() => addTrunk(activeTree.id)}
                      className="flex items-center gap-1 rounded-lg border border-dashed border-border/30 px-3 py-1.5 text-xs text-secondary-text transition-all hover:border-amber/30 hover:text-amber"
                    >
                      <Plus className="h-3 w-3" />
                      新增树干
                    </button>
                  </div>
                )}

                {/* Single trunk view */}
                {activeTree.nodes.length === 0 ? (
                  <div className="flex flex-col items-center gap-4 py-20">
                    <TreePine className="h-12 w-12 text-border" />
                    <p className="text-sm text-secondary-text">还没有树干，点击下方按钮新增第一个树干</p>
                    <button
                      type="button"
                      onClick={() => addTrunk(activeTree.id)}
                      className="btn-primary flex items-center gap-2"
                    >
                      <Plus className="h-4 w-4" />
                      新增树干
                    </button>
                  </div>
                ) : (
                  <div className="flex flex-col items-center">
                    {(() => {
                      const trunkId = selectedTrunkId ?? activeTree.nodes[0]?.id;
                      const trunk = trunkId ? findNode(activeTree.nodes, trunkId) : null;
                      if (!trunk) return null;
                      return (
                        <TreeDiagram
                          key={trunk.id}
                          root={trunk}
                          onEdit={(nodeId) => openNodeDialog(activeTree.id, nodeId)}
                          onDelete={(nodeId) => deleteNode(activeTree.id, nodeId)}
                          onAddChild={(parentId) => addChildNode(activeTree.id, parentId)}
                          onToggleCollapse={(nodeId) => toggleCollapse(activeTree.id, nodeId)}
                        />
                      );
                    })()}
                  </div>
                )}
              </div>
            )}

            {!activeTree && trees.length > 0 && (
              <div className="flex flex-1 items-center justify-center py-20">
                <p className="text-sm text-secondary-text">请从左侧选择一棵知识树</p>
              </div>
            )}
          </div>
        </div>
      )}

      <NodeModal
        isOpen={modalOpen}
        title={modalTitle}
        initialLabel={editingLabel}
        initialDescription={editingDescription}
        onSave={handleModalSave}
        onClose={() => { setModalOpen(false); setEditingNodeKey(null); }}
      />

      <NodeModal
        isOpen={renameOpen}
        title="重命名知识树"
        initialLabel={renameValue}
        initialDescription=""
        onSave={(label) => {
          if (label.trim() && renameTreeId) {
            const updated = trees.map((t) => {
              if (t.id !== renameTreeId) return t;
              return { ...t, title: label.trim(), updatedAt: new Date().toISOString() };
            });
            persist(updated);
            setRenameOpen(false);
            setRenameTreeId(null);
          }
        }}
        onClose={() => { setRenameOpen(false); setRenameTreeId(null); }}
      />
    </div>
  );
};

export default XinfaTreePage;
