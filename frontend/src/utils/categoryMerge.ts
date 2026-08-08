import type { CategoryNode, PlatformId } from '@/types/products'

export interface CategorySourceRef {
  id: string
  platform: PlatformId
  isWatched: boolean
}

/** 展示用品类节点：可合并多平台同源品类 */
export interface DisplayCategoryNode {
  /** 稳定展示 key（合并后为 merge:xxx，单节点为真实 id） */
  key: string
  name: string
  /** 可映射到后端查询的本地 category 来源 */
  sources: CategorySourceRef[]
  /** 当前品类及所有后代品类的商品数 */
  productCount: number
  children: DisplayCategoryNode[]
  /** 用于选图标的归一化词 */
  iconKey: string
}

/** 中英文 / 近义品类归一化词典 */
const SYNONYM_GROUPS: string[][] = [
  ['electronics', '电子', '电子产品', '数码', '数码电子', 'consumer electronics'],
  ['computers', '电脑', '计算机', 'computer', 'pc', 'laptops', '笔记本'],
  ['phones', '手机', '手机通讯', 'cell phones', 'mobile phones', 'smartphones'],
  ['headphones', '耳机', '耳麦', 'earphones', 'earbuds', 'headsets'],
  ['wireless headphones', '无线耳机', 'bluetooth headphones', '蓝牙耳机'],
  ['home', '家居', '家居厨具', 'home & kitchen', 'home and kitchen', 'household'],
  ['kitchen', '厨房', '厨具', 'cookware'],
  ['beauty', '美妆', '美容', 'beauty & personal care', 'personal care', '护肤'],
  ['fashion', '服装', '服饰', 'clothing', 'apparel', 'fashion clothing'],
  ['shoes', '鞋靴', 'shoes & bags', 'footwear'],
  ['sports', '运动', '运动户外', 'sports & outdoors', 'outdoors', 'outdoor'],
  ['toys', '玩具', '玩具游戏', 'toys & games', 'games'],
  ['books', '图书', '书籍', 'book'],
  ['food', '食品', '食品饮料', 'grocery', 'food & beverage', '饮料'],
  ['baby', '母婴', '婴童', 'baby products', 'maternity'],
  ['automotive', '汽车', '汽车用品', 'car', 'vehicle'],
  ['pet', '宠物', '宠物用品', 'pet supplies', 'pets'],
  ['office', '办公', '办公用品', 'office products', 'stationery'],
  ['health', '健康', '保健', 'health & household', 'healthcare'],
  ['garden', '园艺', 'garden', 'patio', 'lawn & garden'],
  ['tools', '工具', '五金', 'tools & home improvement', 'hardware'],
  ['jewelry', '珠宝', '饰品', 'jewellery', 'accessories'],
  ['watches', '手表', '钟表', 'watch'],
  ['cameras', '相机', '摄影', 'camera', 'photo'],
  ['music', '音乐', '乐器', 'musical instruments'],
  ['industrial', '工业', '工业品', 'industrial & scientific'],
  ['software', '软件', 'software & apps'],
  ['video games', '游戏', '电子游戏', 'videogames'],
]

const SYNONYM_TO_CANONICAL = new Map<string, string>()

for (const group of SYNONYM_GROUPS) {
  const canonical = group[0]
  for (const term of group) {
    SYNONYM_TO_CANONICAL.set(normalizeRaw(term), canonical)
  }
}

function normalizeRaw(name: string): string {
  return name
    .trim()
    .toLowerCase()
    .replace(/[&/\\|]+/g, ' ')
    .replace(/[^\p{L}\p{N}\s]/gu, '')
    .replace(/\s+/g, ' ')
}

/** 归一化品类名，用于跨平台合并 */
export function canonicalizeCategoryName(name: string): string {
  const raw = normalizeRaw(name)
  if (!raw) return ''
  return SYNONYM_TO_CANONICAL.get(raw) ?? raw
}

function sortByName(a: DisplayCategoryNode, b: DisplayCategoryNode): number {
  return a.name.localeCompare(b.name, 'zh-CN')
}

function pickDisplayName(nodes: CategoryNode[]): string {
  const zh = nodes.find((n) => /[\u4e00-\u9fff]/.test(n.name))
  if (zh) return zh.name
  return [...nodes].sort((a, b) => a.name.length - b.name.length)[0]?.name ?? '未命名'
}

/**
 * 将多平台品类树按近似名称合并。
 * 同层名称归一化后相同的节点合并；子树递归合并。
 */
export function mergeCategoryTrees(roots: CategoryNode[]): DisplayCategoryNode[] {
  return mergeLevel(roots).sort(sortByName)
}

function mergeLevel(nodes: CategoryNode[]): DisplayCategoryNode[] {
  const groups = new Map<string, CategoryNode[]>()

  for (const node of nodes) {
    const key = canonicalizeCategoryName(node.name) || node.id
    const list = groups.get(key)
    if (list) list.push(node)
    else groups.set(key, [node])
  }

  const result: DisplayCategoryNode[] = []

  for (const [canon, group] of groups) {
    const childPool: CategoryNode[] = []
    for (const node of group) {
      childPool.push(...(node.children || []))
    }

    const sources: CategorySourceRef[] = []
    const seen = new Set<string>()
    for (const n of group) {
      const id = String(n.id)
      if (seen.has(id)) continue
      seen.add(id)
      sources.push({ id, platform: n.platform, isWatched: n.is_watched })
    }
    const name = pickDisplayName(group)
    const idsKey = sources
      .map((s) => s.id)
      .sort()
      .join('+')
    const key = sources.length === 1 ? sources[0].id : `merge:${canon}:${idsKey}`

    result.push({
      key,
      name,
      sources,
      productCount: group.reduce((total, node) => total + node.product_count, 0),
      iconKey: canon,
      children: mergeLevel(childPool).sort(sortByName),
    })
  }

  return result
}

/** 单平台：原样转为展示节点，不合并 */
export function toDisplayTree(roots: CategoryNode[]): DisplayCategoryNode[] {
  const mapNode = (node: CategoryNode): DisplayCategoryNode => ({
    key: String(node.id),
    name: node.name,
    sources: [
      { id: String(node.id), platform: node.platform, isWatched: node.is_watched },
    ],
    productCount: node.product_count,
    iconKey: canonicalizeCategoryName(node.name) || String(node.id),
    children: (node.children || []).map(mapNode),
  })
  return roots.map(mapNode)
}

/** 前端关键字过滤品类树（保留匹配节点的祖先链） */
export function filterDisplayTree(
  nodes: DisplayCategoryNode[],
  keyword: string,
): DisplayCategoryNode[] {
  const q = keyword.trim().toLowerCase()
  if (!q) return nodes

  const walk = (list: DisplayCategoryNode[]): DisplayCategoryNode[] => {
    const out: DisplayCategoryNode[] = []
    for (const node of list) {
      const children = walk(node.children)
      const selfMatch = node.name.toLowerCase().includes(q)
      if (selfMatch || children.length > 0) {
        out.push({ ...node, children })
      }
    }
    return out
  }

  return walk(nodes)
}

/** 在树中查找节点 */
export function findDisplayNode(
  nodes: DisplayCategoryNode[],
  key: string | null,
): DisplayCategoryNode | null {
  if (!key) return null
  for (const node of nodes) {
    if (node.key === key) return node
    const found = findDisplayNode(node.children, key)
    if (found) return found
  }
  return null
}

/** 统计展示树节点数 */
export function countDisplayNodes(nodes: DisplayCategoryNode[]): number {
  let total = 0
  const walk = (list: DisplayCategoryNode[]) => {
    for (const node of list) {
      total += 1
      walk(node.children)
    }
  }
  walk(nodes)
  return total
}
