export interface XinfaEntryItem {
  id: number;
  title: string;
  content: string;
  category: string;
  tags: string[] | null;
  stockCode: string | null;
  stockName: string | null;
  sentiment: number | null;
  isStarred: boolean;
  createdAt: string | null;
  updatedAt: string | null;
}

export interface XinfaListResponse {
  total: number;
  items: XinfaEntryItem[];
  page: number;
  pageSize: number;
}

export interface XinfaCategorySummaryItem {
  category: string;
  count: number;
  label: string;
}

export interface XinfaCategorySummaryResponse {
  categories: XinfaCategorySummaryItem[];
}

export interface XinfaCreateRequest {
  title: string;
  content: string;
  category?: string;
  tags?: string[];
  stockCode?: string;
  stockName?: string;
  sentiment?: number;
  isStarred?: boolean;
}

export interface XinfaUpdateRequest {
  title?: string;
  content?: string;
  category?: string;
  tags?: string[];
  stockCode?: string;
  stockName?: string;
  sentiment?: number;
  isStarred?: boolean;
}

export const CATEGORY_LABELS: Record<string, string> = {
  general: '通用',
  review: '复盘反思',
  discipline: '交易纪律',
  mindset: '心态建设',
  experience: '经验总结',
  plan: '交易计划',
};

export const CATEGORY_LIST = Object.entries(CATEGORY_LABELS).map(([key, label]) => ({
  key,
  label,
}));

// ---------------------------------------------------------------------------
// 树干树枝 (Knowledge Tree) 数据类型
// ---------------------------------------------------------------------------

export interface TreeNode {
  id: string;
  label: string;
  description: string;
  children: TreeNode[];
  collapsed: boolean;
}

export interface KnowledgeTree {
  id: string;
  title: string;
  nodes: TreeNode[]; // 根节点 = 树干
  createdAt: string;
  updatedAt: string;
}

export function createNodeId(): string {
  return `node_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
}

export function createEmptyTree(title?: string): KnowledgeTree {
  return {
    id: createNodeId(),
    title: title ?? '新建知识树',
    nodes: [],
    createdAt: new Date().toISOString(),
    updatedAt: new Date().toISOString(),
  };
}

export function createEmptyNode(label?: string): TreeNode {
  return {
    id: createNodeId(),
    label: label ?? '新节点',
    description: '',
    children: [],
    collapsed: false,
  };
}
