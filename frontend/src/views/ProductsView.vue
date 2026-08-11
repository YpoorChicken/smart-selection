<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import type { Component } from 'vue'
import { ElMessage } from 'element-plus'
import * as echarts from 'echarts/core'
import { LineChart } from 'echarts/charts'
import {
  GridComponent,
  TooltipComponent,
} from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import {
  Box,
  Cellphone,
  Cpu,
  FirstAidKit,
  Goods,
  Headset,
  House,
  MessageBox,
  MagicStick,
  Monitor,
  Orange,
  PictureFilled,
  Present,
  Reading,
  Refresh,
  Search,
  Soccer,
  StarFilled,
  Van,
  WarningFilled,
} from '@element-plus/icons-vue'
import {
  getCategoryTree,
  getProductHistory,
  getProducts,
  getSyncStatus,
  syncCategories,
  syncProducts,
} from '@/api/products'
import type {
  PlatformId,
  ProductHistoryPoint,
  ProductListItem,
  SyncLog,
} from '@/types/products'
import {
  countDisplayNodes,
  filterDisplayTree,
  findDisplayNode,
  mergeCategoryTrees,
  toDisplayTree,
  type DisplayCategoryNode,
} from '@/utils/categoryMerge'

echarts.use([LineChart, GridComponent, TooltipComponent, CanvasRenderer])

type PlatformFilter = PlatformId | ''
type LoadState = 'idle' | 'loading' | 'success' | 'empty' | 'error'

const PLATFORM_OPTIONS: { label: string; value: PlatformFilter }[] = [
  { label: '全部平台', value: '' },
  { label: 'Amazon', value: 'amazon' },
  { label: 'Shopee', value: 'shopee' },
  { label: 'Mock', value: 'mock' },
  { label: 'DummyJSON', value: 'dummyjson' },
  { label: 'FakeStore', value: 'fakestore' },
]

const PAGE_SIZE_OPTIONS = [10, 20, 30, 50]

const CATEGORY_ICONS: Record<string, Component> = {
  electronics: Cpu,
  computers: Monitor,
  phones: Cellphone,
  headphones: Headset,
  'wireless headphones': Headset,
  home: House,
  kitchen: House,
  beauty: MagicStick,
  fashion: Goods,
  shoes: Goods,
  sports: Soccer,
  toys: Present,
  books: Reading,
  food: Orange,
  baby: Present,
  automotive: Van,
  pet: Present,
  office: Reading,
  health: FirstAidKit,
  garden: House,
  tools: Box,
  jewelry: Goods,
  watches: Goods,
  cameras: PictureFilled,
  music: Headset,
  industrial: Box,
  software: Cpu,
  'video games': Present,
}

const platformId = ref<PlatformFilter>('')
const keyword = ref('')
const categoryFilter = ref('')
const selectedCategoryKey = ref<string | null>(null)
const sortMode = ref<'rating_desc' | 'price_asc' | 'price_desc' | 'sales_asc'>(
  'rating_desc',
)
const watchedOnly = ref(false)

const page = ref(1)
const pageSize = ref(20)

const categoryRaw = ref<DisplayCategoryNode[]>([])
const categoryState = ref<LoadState>('idle')
const categoryError = ref('')
const categoryRequestId = ref(0)

const displayCategories = computed(() => {
  const filtered = filterDisplayTree(categoryRaw.value, categoryFilter.value)
  if (!watchedOnly.value) return filtered

  const keepWatched = (nodes: DisplayCategoryNode[]): DisplayCategoryNode[] =>
    nodes.flatMap((node) => {
      const children = keepWatched(node.children)
      const watched = node.sources.some((source) => source.isWatched)
      return watched || children.length > 0 ? [{ ...node, children }] : []
    })

  return keepWatched(filtered)
})
const categoryTotal = computed(() => countDisplayNodes(displayCategories.value))
const selectedCategory = computed(() =>
  findDisplayNode(categoryRaw.value, selectedCategoryKey.value),
)
const defaultExpandedKeys = computed(() =>
  categoryRaw.value[0] ? [categoryRaw.value[0].key] : [],
)

interface CategoryOption {
  key: string
  label: string
  depth: number
}

const categoryOptions = computed<CategoryOption[]>(() => {
  const options: CategoryOption[] = []
  const walk = (nodes: DisplayCategoryNode[], depth: number) => {
    for (const node of nodes) {
      options.push({ key: node.key, label: node.name, depth })
      walk(node.children, depth + 1)
    }
  }
  walk(categoryRaw.value, 0)
  return options
})

const products = ref<ProductListItem[]>([])
const productTotal = ref(0)
const productState = ref<LoadState>('idle')
const productError = ref('')
const productRefreshing = ref(false)
const productRequestId = ref(0)

const syncingCategories = ref(false)
const syncingProducts = ref(false)
const syncingDetailId = ref<string | null>(null)

const collectionVisible = ref(false)
const collectionSaving = ref(false)
const collectionPlatform = ref<PlatformId>('amazon')
const collectionCategoryKeys = ref<string[]>([])
const collectionFrequency = ref<'hourly' | 'daily'>('hourly')
const collectionTrigger = ref<'scheduled' | 'manual'>('scheduled')
const collectionEnabled = ref(true)
const collectionTasks = ref<SyncLog[]>([])
const collectionTasksLoading = ref(false)

const historyVisible = ref(false)
const historyLoading = ref(false)
const historyError = ref('')
const historyProduct = ref<ProductListItem | null>(null)
const historyPoints = ref<ProductHistoryPoint[]>([])
const chartRef = ref<HTMLDivElement | null>(null)
let chartInstance: echarts.ECharts | null = null

const recentSyncedAt = computed(() => {
  let latest = ''
  for (const product of products.value) {
    if (product.last_synced_at && product.last_synced_at > latest) {
      latest = product.last_synced_at
    }
  }
  return latest
})

function categoryIcon(iconKey: string): Component {
  return CATEGORY_ICONS[iconKey] || Box
}

function toNumber(value: string | number | null | undefined): number | null {
  if (value == null || value === '') return null
  const n = typeof value === 'number' ? value : Number(value)
  return Number.isFinite(n) ? n : null
}

function formatPrice(row: ProductListItem): string {
  const price = toNumber(row.price)
  if (price == null) return '—'
  const currency = (row.currency || 'USD').toUpperCase()
  const symbol = currency === 'USD' ? '$' : currency === 'CNY' ? '¥' : `${currency} `
  return `${symbol}${price.toFixed(2)}`
}

function formatCount(value: number | null | undefined): string {
  if (value == null) return '—'
  return value.toLocaleString('en-US')
}

function formatSyncTime(value: string | null): string {
  if (!value) return '—'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '—'
  const now = new Date()
  const sameDay = date.toDateString() === now.toDateString()
  const time = date.toLocaleTimeString('zh-CN', {
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  })
  return sameDay ? `今天 ${time}` : `${date.getMonth() + 1}-${date.getDate()} ${time}`
}

function ratingTone(rating: number | null): 'high' | 'mid' | 'low' | 'none' {
  if (rating == null) return 'none'
  if (rating >= 4.5) return 'high'
  if (rating >= 3.5) return 'mid'
  return 'low'
}

function platformLabel(platform: PlatformId): string {
  if (platform === 'amazon') return 'Amazon'
  if (platform === 'shopee') return 'Shopee'
  if (platform === 'dummyjson') return 'DummyJSON'
  if (platform === 'fakestore') return 'FakeStore'
  return 'Mock'
}

function platformTagClass(platform: PlatformId): string {
  if (platform === 'amazon') return 'tag-amazon'
  if (platform === 'shopee') return 'tag-shopee'
  return 'tag-neutral'
}

function requirePlatform(): PlatformId | null {
  if (!platformId.value) {
    ElMessage.warning('请先选择平台后再同步')
    return null
  }
  return platformId.value
}

function resolveCategoryIdForPlatform(
  node: DisplayCategoryNode | null,
  platform: PlatformId,
): string | null {
  if (!node || node.sources.length === 0) return null
  const matched = node.sources.find((s) => s.platform === platform)
  if (matched) return matched.id
  return node.sources[0]?.id ?? null
}

async function loadCategories() {
  const reqId = ++categoryRequestId.value
  categoryState.value = 'loading'
  categoryError.value = ''

  try {
    const data = await getCategoryTree(platformId.value || undefined)
    if (reqId !== categoryRequestId.value) return

    const items = data.items || []
    categoryRaw.value = platformId.value
      ? toDisplayTree(items)
      : mergeCategoryTrees(items)

    if (
      selectedCategoryKey.value &&
      !findDisplayNode(categoryRaw.value, selectedCategoryKey.value)
    ) {
      selectedCategoryKey.value = null
    }

    categoryState.value = categoryRaw.value.length === 0 ? 'empty' : 'success'
  } catch (err) {
    if (reqId !== categoryRequestId.value) return
    categoryRaw.value = []
    categoryState.value = 'error'
    categoryError.value = err instanceof Error ? err.message : '品类加载失败'
  }
}

function productSort(): {
  sort_by: 'price' | 'rating' | 'sales_rank'
  sort_order: 'asc' | 'desc'
} {
  if (sortMode.value === 'price_asc') {
    return { sort_by: 'price', sort_order: 'asc' }
  }
  if (sortMode.value === 'price_desc') {
    return { sort_by: 'price', sort_order: 'desc' }
  }
  if (sortMode.value === 'sales_asc') {
    return { sort_by: 'sales_rank', sort_order: 'asc' }
  }
  return { sort_by: 'rating', sort_order: 'desc' }
}

function sortMergedProducts(items: ProductListItem[]): void {
  items.sort((a, b) => {
    if (sortMode.value === 'rating_desc') {
      return (toNumber(b.rating) ?? -1) - (toNumber(a.rating) ?? -1)
    }
    if (sortMode.value === 'price_asc') {
      return (toNumber(a.price) ?? Number.MAX_SAFE_INTEGER) -
        (toNumber(b.price) ?? Number.MAX_SAFE_INTEGER)
    }
    if (sortMode.value === 'price_desc') {
      return (toNumber(b.price) ?? -1) - (toNumber(a.price) ?? -1)
    }
    return (a.bsr ?? Number.MAX_SAFE_INTEGER) - (b.bsr ?? Number.MAX_SAFE_INTEGER)
  })
}

async function loadProducts(options?: { soft?: boolean }) {
  const soft = Boolean(options?.soft)
  const reqId = ++productRequestId.value

  if (soft && products.value.length > 0) {
    productRefreshing.value = true
  } else {
    productState.value = 'loading'
  }
  productError.value = ''

  try {
    const selected = selectedCategory.value
    let items: ProductListItem[] = []
    let total = 0

    if (selected && selected.sources.length > 1 && !platformId.value) {
      const pages = await Promise.all(
        selected.sources.map((source) =>
          getProducts({
            page: 1,
            page_size: 100,
            category_id: source.id,
            q: keyword.value.trim() || undefined,
            ...productSort(),
          }),
        ),
      )
      if (reqId !== productRequestId.value) return

      const merged = pages.flatMap((p) => p.items)
      sortMergedProducts(merged)
      total = merged.length
      const start = (page.value - 1) * pageSize.value
      items = merged.slice(start, start + pageSize.value)
    } else {
      let categoryId: string | undefined
      if (selected) {
        if (platformId.value) {
          categoryId =
            resolveCategoryIdForPlatform(selected, platformId.value) || undefined
        } else {
          categoryId = selected.sources[0]?.id
        }
      }

      const data = await getProducts({
        page: page.value,
        page_size: pageSize.value,
        platform_id: platformId.value || undefined,
        category_id: categoryId,
        q: keyword.value.trim() || undefined,
        ...productSort(),
      })
      if (reqId !== productRequestId.value) return
      items = data.items
      total = data.meta.total
    }

    products.value = items
    productTotal.value = total
    productState.value = items.length === 0 ? 'empty' : 'success'
  } catch (err) {
    if (reqId !== productRequestId.value) return
    if (!soft) products.value = []
    productState.value = products.value.length > 0 ? 'success' : 'error'
    productError.value = err instanceof Error ? err.message : '商品加载失败'
  } finally {
    if (reqId === productRequestId.value) {
      productRefreshing.value = false
    }
  }
}

function resetPageAndReload() {
  page.value = 1
  void loadProducts()
}

function onSelectCategory(node: DisplayCategoryNode) {
  selectedCategoryKey.value = node.key
  resetPageAndReload()
}

function onCategorySelect(key: string) {
  if (!key) {
    clearCategorySelection()
    return
  }
  const node = findDisplayNode(categoryRaw.value, key)
  if (node) onSelectCategory(node)
}

function clearCategorySelection() {
  selectedCategoryKey.value = null
  resetPageAndReload()
}

async function handleSyncCategories() {
  const platform = requirePlatform()
  if (!platform) return

  syncingCategories.value = true
  try {
    const log = await syncCategories(platform)
    ElMessage.success(
      log.status === 'success'
        ? `品类同步完成，共 ${log.items_count} 项`
        : `品类同步结束：${log.status}`,
    )
    await loadCategories()
    await loadProducts({ soft: true })
  } catch {
    // 错误已由拦截器提示
  } finally {
    syncingCategories.value = false
  }
}

async function openCollectionConfig() {
  if (platformId.value) {
    collectionPlatform.value = platformId.value
  }
  if (selectedCategoryKey.value) {
    collectionCategoryKeys.value = [selectedCategoryKey.value]
  }
  collectionVisible.value = true
  collectionTasksLoading.value = true
  try {
    const status = await getSyncStatus(6)
    collectionTasks.value = status.items
  } catch {
    collectionTasks.value = []
  } finally {
    collectionTasksLoading.value = false
  }
}

function syncStatusLabel(status: SyncLog['status']): string {
  return {
    pending: '等待中',
    running: '进行中',
    success: '成功',
    failed: '失败',
  }[status]
}

function syncStatusType(
  status: SyncLog['status'],
): 'success' | 'warning' | 'danger' | 'info' {
  return {
    pending: 'info',
    running: 'warning',
    success: 'success',
    failed: 'danger',
  }[status] as 'success' | 'warning' | 'danger' | 'info'
}

function taskProgress(status: SyncLog['status']): number {
  if (status === 'success') return 100
  if (status === 'running') return 68
  if (status === 'failed') return 32
  return 0
}

function loadCollectionConfig() {
  try {
    const raw = localStorage.getItem('hpzx_collection_config_v1')
    if (!raw) return
    const saved = JSON.parse(raw) as {
      platform?: PlatformId
      categoryKeys?: string[]
      frequency?: 'hourly' | 'daily'
      trigger?: 'scheduled' | 'manual'
      enabled?: boolean
    }
    if (saved.platform) collectionPlatform.value = saved.platform
    if (Array.isArray(saved.categoryKeys)) {
      collectionCategoryKeys.value = saved.categoryKeys
    }
    if (saved.frequency) collectionFrequency.value = saved.frequency
    if (saved.trigger) collectionTrigger.value = saved.trigger
    if (typeof saved.enabled === 'boolean') collectionEnabled.value = saved.enabled
  } catch {
    localStorage.removeItem('hpzx_collection_config_v1')
  }
}

async function saveCollectionConfig() {
  if (collectionCategoryKeys.value.length === 0) {
    ElMessage.warning('请至少选择一个关注品类')
    return
  }

  collectionSaving.value = true
  try {
    localStorage.setItem(
      'hpzx_collection_config_v1',
      JSON.stringify({
        platform: collectionPlatform.value,
        categoryKeys: collectionCategoryKeys.value,
        frequency: collectionFrequency.value,
        trigger: collectionTrigger.value,
        enabled: collectionEnabled.value,
      }),
    )
    collectionVisible.value = false
    ElMessage.success('采集配置已保存')
  } catch {
    ElMessage.error('采集配置保存失败，请重试')
  } finally {
    collectionSaving.value = false
  }
}

async function handleSyncProducts() {
  const platform = requirePlatform()
  if (!platform) return

  const selected = selectedCategory.value
  if (!selected) {
    ElMessage.warning('请先选择品类后再同步商品')
    return
  }

  const categoryId = resolveCategoryIdForPlatform(selected, platform)
  if (!categoryId) {
    ElMessage.warning('当前品类在所选平台下无对应节点，请换一个品类')
    return
  }

  syncingProducts.value = true
  try {
    const log = await syncProducts({
      platform_id: platform,
      category_id: categoryId,
    })
    ElMessage.success(
      log.status === 'success'
        ? `商品同步完成，共 ${log.items_count} 件`
        : `商品同步结束：${log.status}`,
    )
    await loadProducts({ soft: true })
  } catch {
    // 错误已由拦截器提示
  } finally {
    syncingProducts.value = false
  }
}

async function handleSyncDetail(row: ProductListItem) {
  syncingDetailId.value = row.id
  try {
    const log = await syncProducts({
      platform_id: row.platform,
      product_id: row.id,
    })
    ElMessage.success(
      log.status === 'success' ? '商品详情已同步' : `同步结束：${log.status}`,
    )
    await loadProducts({ soft: true })
  } catch {
    // 错误已由拦截器提示
  } finally {
    syncingDetailId.value = null
  }
}

function disposeChart() {
  if (chartInstance) {
    chartInstance.dispose()
    chartInstance = null
  }
}

function renderHistoryChart() {
  if (!chartRef.value) return
  disposeChart()
  chartInstance = echarts.init(chartRef.value)

  const points = [...historyPoints.value].sort((a, b) =>
    a.recorded_at.localeCompare(b.recorded_at),
  )
  const dates = points.map((p) => {
    const d = new Date(p.recorded_at)
    const mm = String(d.getMonth() + 1).padStart(2, '0')
    const dd = String(d.getDate()).padStart(2, '0')
    return `${mm}-${dd}`
  })
  const prices = points.map((p) => toNumber(p.price))

  chartInstance.setOption({
    color: ['#4F46E5'],
    grid: { left: 48, right: 24, top: 32, bottom: 40 },
    tooltip: {
      trigger: 'axis',
      backgroundColor: '#fff',
      borderColor: '#E5E7EB',
      borderWidth: 1,
      textStyle: { color: '#111827', fontSize: 13 },
    },
    xAxis: {
      type: 'category',
      data: dates,
      axisLine: { lineStyle: { color: '#E5E7EB' } },
      axisLabel: { color: '#6B7280', fontSize: 12 },
      axisTick: { show: false },
    },
    yAxis: {
      type: 'value',
      scale: true,
      axisLine: { show: false },
      splitLine: { lineStyle: { color: '#E5E7EB' } },
      axisLabel: {
        color: '#6B7280',
        fontSize: 12,
        formatter: (v: number) => `$${v}`,
      },
    },
    series: [
      {
        type: 'line',
        data: prices,
        smooth: true,
        showSymbol: points.length <= 24,
        symbolSize: 6,
        lineStyle: { width: 2 },
        areaStyle: { color: 'rgba(79,70,229,0.10)' },
      },
    ],
  })
}

const historyStats = computed(() => {
  const nums = historyPoints.value
    .map((p) => toNumber(p.price))
    .filter((n): n is number => n != null)
  if (nums.length === 0) {
    return { current: null as number | null, min: null as number | null, max: null as number | null }
  }
  return {
    current: nums[nums.length - 1] ?? null,
    min: Math.min(...nums),
    max: Math.max(...nums),
  }
})

async function openHistory(row: ProductListItem) {
  historyProduct.value = row
  historyVisible.value = true
  historyLoading.value = true
  historyError.value = ''
  historyPoints.value = []
  await nextTick()
  disposeChart()

  try {
    const data = await getProductHistory(row.id, 90)
    historyPoints.value = data.items || []
    if (historyPoints.value.length === 0) {
      historyError.value = '暂无价格历史数据'
    } else {
      await nextTick()
      renderHistoryChart()
    }
  } catch (err) {
    historyError.value = err instanceof Error ? err.message : '价格历史加载失败'
  } finally {
    historyLoading.value = false
  }
}

function closeHistory() {
  historyVisible.value = false
  disposeChart()
}

function onPageSizeChange() {
  page.value = 1
  void loadProducts({ soft: true })
}

function onPageChange() {
  void loadProducts({ soft: true })
}

watch(platformId, async () => {
  selectedCategoryKey.value = null
  page.value = 1
  await loadCategories()
  await loadProducts()
})

let searchTimer: ReturnType<typeof setTimeout> | null = null
watch([keyword, sortMode], () => {
  if (searchTimer) clearTimeout(searchTimer)
  searchTimer = setTimeout(() => {
    page.value = 1
    void loadProducts({ soft: true })
  }, 320)
})

function onResize() {
  chartInstance?.resize()
}

onMounted(async () => {
  window.addEventListener('resize', onResize)
  loadCollectionConfig()
  await loadCategories()
  await loadProducts()
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', onResize)
  if (searchTimer) clearTimeout(searchTimer)
  disposeChart()
})
</script>

<template>
  <div class="products-page">
    <div class="page-toolbar">
      <h1 class="page-title">商品管理</h1>
      <div class="toolbar-actions">
        <el-button
          :loading="syncingCategories"
          :disabled="syncingProducts"
          @click="handleSyncCategories"
        >
          {{ syncingCategories ? '同步中…' : '同步品类' }}
        </el-button>
        <el-button
          :loading="syncingProducts"
          :disabled="syncingCategories"
          @click="handleSyncProducts"
        >
          {{ syncingProducts ? '同步中…' : '同步商品' }}
        </el-button>
        <el-button type="primary" @click="openCollectionConfig">配置采集</el-button>
      </div>
    </div>

    <div class="filter-bar page-card">
      <div class="filter-controls">
        <el-input
          v-model="keyword"
          class="filter-search"
          clearable
          placeholder="搜索标题 / ASIN"
          :prefix-icon="Search"
        />
        <el-select v-model="platformId" class="filter-platform" placeholder="全部平台">
          <el-option
            v-for="opt in PLATFORM_OPTIONS"
            :key="String(opt.value)"
            :label="opt.label"
            :value="opt.value"
          />
        </el-select>
        <el-select
          :model-value="selectedCategoryKey || ''"
          class="filter-category"
          placeholder="全部品类"
          @change="onCategorySelect"
        >
          <el-option label="全部品类" value="" />
          <el-option
            v-for="option in categoryOptions"
            :key="option.key"
            :label="`${'　'.repeat(option.depth)}${option.label}`"
            :value="option.key"
          />
        </el-select>
        <el-select v-model="sortMode" class="filter-sort">
          <el-option label="评分从高到低" value="rating_desc" />
          <el-option label="价格从低到高" value="price_asc" />
          <el-option label="价格从高到低" value="price_desc" />
          <el-option label="销量排名优先" value="sales_asc" />
        </el-select>
        <el-checkbox v-model="watchedOnly" class="watched-check">
          仅看自营关注
        </el-checkbox>
      </div>
      <div class="last-sync">最近同步：{{ formatSyncTime(recentSyncedAt || null) }}</div>
    </div>

    <div class="workspace">
      <aside class="category-panel page-card">
        <div class="panel-head">
          <div class="panel-title-row">
            <span class="panel-title">品类</span>
            <span class="panel-meta">共 {{ categoryTotal }}</span>
          </div>
          <el-input
            v-model="categoryFilter"
            size="small"
            clearable
            placeholder="过滤品类"
            :prefix-icon="Search"
          />
        </div>

        <div v-if="categoryState === 'loading'" class="panel-body">
          <el-skeleton animated :rows="8" />
        </div>

        <div v-else-if="categoryState === 'error'" class="state-block">
          <el-icon class="state-icon danger"><WarningFilled /></el-icon>
          <p class="state-title">品类加载失败</p>
          <p class="state-desc">{{ categoryError }}</p>
          <el-button type="primary" size="small" @click="loadCategories">重试</el-button>
        </div>

        <div v-else-if="categoryState === 'empty'" class="state-block">
          <el-icon class="state-icon"><Box /></el-icon>
          <p class="state-title">还没有同步品类</p>
          <p class="state-desc">选择平台后点击「同步品类」拉取数据</p>
        </div>

        <div v-else class="category-scroll">
          <button
            type="button"
            class="category-item all"
            :class="{ active: !selectedCategoryKey }"
            @click="clearCategorySelection"
          >
            <el-icon class="cat-icon"><Goods /></el-icon>
            <span class="cat-name">全部商品</span>
            <span class="cat-count">{{ productTotal }}</span>
          </button>

          <div v-if="displayCategories.length === 0" class="filter-empty">无匹配品类</div>

          <el-tree
            v-else
            :data="displayCategories"
            node-key="key"
            :props="{ label: 'name', children: 'children' }"
            :default-expanded-keys="defaultExpandedKeys"
            highlight-current
            :expand-on-click-node="false"
            :current-node-key="selectedCategoryKey || undefined"
            class="category-tree"
            @node-click="onSelectCategory"
          >
            <template #default="{ data }">
              <div
                class="category-node"
                :class="{ active: selectedCategoryKey === data.key }"
              >
                <el-icon class="cat-icon">
                  <component :is="categoryIcon(data.iconKey)" />
                </el-icon>
                <span class="cat-name" :title="data.name">{{ data.name }}</span>
                <span class="cat-count">{{ data.productCount }}</span>
              </div>
            </template>
          </el-tree>
        </div>

        <div class="collection-card">
          <div class="collection-card-label">找新品 · 安排采集</div>
          <el-icon class="collection-card-icon"><MessageBox /></el-icon>
          <strong>还没有同步商品</strong>
          <span>去配置要重点采集的品类</span>
          <el-button type="primary" size="small" @click="openCollectionConfig">
            配置采集
          </el-button>
          <small>单品跟踪 · 监控价格 · 一键管理</small>
        </div>
      </aside>

      <section class="table-panel page-card">
        <div class="panel-head table-head">
          <div class="panel-title-row">
            <span class="panel-title">
              {{ selectedCategory?.name || '全部商品' }}
            </span>
            <span class="panel-meta">{{ productTotal }} 件商品</span>
          </div>
        </div>

        <div v-if="productState === 'loading'" class="table-skeleton">
          <el-skeleton animated :rows="6" />
        </div>

        <div v-else-if="productState === 'error' && products.length === 0" class="state-block">
          <el-icon class="state-icon danger"><WarningFilled /></el-icon>
          <p class="state-title">商品加载失败</p>
          <p class="state-desc">{{ productError }}</p>
          <el-button type="primary" size="small" @click="loadProducts()">重试</el-button>
        </div>

        <div v-else class="table-wrap" :class="{ refreshing: productRefreshing }">
          <div v-if="productError && products.length > 0" class="inline-alert">
            <span>{{ productError }}</span>
            <el-button link type="primary" @click="loadProducts({ soft: true })">重试</el-button>
          </div>

          <el-table
            v-if="productState !== 'empty'"
            :data="products"
            row-key="id"
            class="product-table"
            empty-text="暂无商品"
          >
            <el-table-column label="商品标题与 ASIN" min-width="248">
              <template #default="{ row }">
                <div class="product-cell">
                  <div class="product-thumb">
                    <img
                      v-if="row.image_url"
                      :src="row.image_url"
                      :alt="row.title"
                      loading="lazy"
                    />
                    <el-icon v-else class="thumb-fallback"><PictureFilled /></el-icon>
                  </div>
                  <div class="product-meta">
                    <div class="product-title" :title="row.title">{{ row.title }}</div>
                    <div class="product-id">{{ row.external_id }}</div>
                  </div>
                </div>
              </template>
            </el-table-column>

            <el-table-column label="平台" width="100">
              <template #default="{ row }">
                <span class="platform-tag" :class="platformTagClass(row.platform)">
                  {{ platformLabel(row.platform) }}
                </span>
              </template>
            </el-table-column>

            <el-table-column label="所属品类" min-width="112">
              <template #default="{ row }">
                <span class="category-label">{{ row.category.name }}</span>
              </template>
            </el-table-column>

            <el-table-column label="价格" width="88" align="right">
              <template #default="{ row }">
                <span class="price-text">{{ formatPrice(row) }}</span>
              </template>
            </el-table-column>

            <el-table-column label="评分" width="96">
              <template #default="{ row }">
                <span
                  class="rating-text"
                  :class="`tone-${ratingTone(toNumber(row.rating))}`"
                >
                  <el-icon><StarFilled /></el-icon>
                  {{ toNumber(row.rating)?.toFixed(1) ?? '—' }}
                </span>
              </template>
            </el-table-column>

            <el-table-column label="销量排名" width="96" align="right">
              <template #default="{ row }">
                <span v-if="row.bsr != null">#{{ formatCount(row.bsr) }}</span>
                <span v-else class="muted">—</span>
              </template>
            </el-table-column>

            <el-table-column label="最近同步" width="104">
              <template #default="{ row }">
                <span class="sync-time">{{ formatSyncTime(row.last_synced_at) }}</span>
              </template>
            </el-table-column>

            <el-table-column label="操作" width="160" fixed="right">
              <template #default="{ row }">
                <div class="row-actions">
                  <el-button
                    link
                    type="primary"
                    :loading="syncingDetailId === row.id"
                    @click.stop="handleSyncDetail(row)"
                  >
                    同步详情
                  </el-button>
                  <el-button link type="primary" @click.stop="openHistory(row)">
                    查看历史
                  </el-button>
                </div>
              </template>
            </el-table-column>
          </el-table>

          <div v-else class="state-block in-table">
            <el-icon class="state-icon"><Box /></el-icon>
            <p class="state-title">还没有同步商品</p>
            <p class="state-desc">
              {{
                selectedCategory
                  ? '选择平台后点击「同步商品」拉取该品类数据'
                  : '可先选择品类，或同步品类后再同步商品'
              }}
            </p>
          </div>

          <div v-if="productTotal > 0" class="table-footer">
            <span class="footer-total">共 {{ productTotal }} 条</span>
            <el-pagination
              v-model:current-page="page"
              v-model:page-size="pageSize"
              :total="productTotal"
              :page-sizes="PAGE_SIZE_OPTIONS"
              layout="sizes, prev, pager, next"
              background
              @current-change="onPageChange"
              @size-change="onPageSizeChange"
            />
          </div>

          <div v-if="productRefreshing" class="refresh-mask">
            <el-icon class="is-loading"><Refresh /></el-icon>
          </div>
        </div>
      </section>
    </div>

    <el-drawer
      v-model="collectionVisible"
      title="数据采集配置"
      size="480px"
      class="collection-drawer"
      destroy-on-close
    >
      <div class="collection-form">
        <label class="form-label">平台</label>
        <el-select v-model="collectionPlatform" class="drawer-control">
          <el-option label="Amazon" value="amazon" />
          <el-option label="Shopee" value="shopee" />
          <el-option label="Mock" value="mock" />
          <el-option label="DummyJSON" value="dummyjson" />
          <el-option label="FakeStore" value="fakestore" />
        </el-select>

        <label class="form-label">关注品类</label>
        <el-select
          v-model="collectionCategoryKeys"
          class="drawer-control"
          multiple
          collapse-tags
          collapse-tags-tooltip
          placeholder="请选择要采集的品类"
        >
          <el-option
            v-for="option in categoryOptions"
            :key="option.key"
            :label="`${'　'.repeat(option.depth)}${option.label}`"
            :value="option.key"
          />
        </el-select>

        <label class="form-label">采集频率</label>
        <el-radio-group v-model="collectionFrequency" class="radio-row">
          <el-radio value="hourly">每小时</el-radio>
          <el-radio value="daily">每日</el-radio>
        </el-radio-group>

        <label class="form-label">触发方式</label>
        <el-radio-group v-model="collectionTrigger" class="radio-row">
          <el-radio value="scheduled">定时</el-radio>
          <el-radio value="manual">手动</el-radio>
        </el-radio-group>

        <div class="switch-row">
          <span class="form-label">启用采集</span>
          <el-switch v-model="collectionEnabled" />
        </div>

        <div class="schedule-note">
          <span>辅助说明</span>
          <strong>
            下次执行：{{
              collectionFrequency === 'hourly' ? '今天 20:00' : '明天 09:00'
            }}
          </strong>
        </div>

        <div class="tasks-section">
          <h3>最近采集任务</h3>
          <el-table
            v-loading="collectionTasksLoading"
            :data="collectionTasks"
            size="small"
            class="task-table"
            empty-text="暂无采集任务"
          >
            <el-table-column label="任务 ID" min-width="104">
              <template #default="{ row }">
                <span class="task-id">{{ row.id.slice(0, 12) }}</span>
              </template>
            </el-table-column>
            <el-table-column label="品类" min-width="78">
              <template #default="{ row }">
                {{ row.sync_type === 'categories' ? '品类' : '商品' }}
              </template>
            </el-table-column>
            <el-table-column label="触发" width="58">
              {{ collectionTrigger === 'scheduled' ? '定时' : '手动' }}
            </el-table-column>
            <el-table-column label="开始时间" width="72">
              <template #default="{ row }">
                {{ formatSyncTime(row.started_at).replace('今天 ', '') }}
              </template>
            </el-table-column>
            <el-table-column label="状态" width="68">
              <template #default="{ row }">
                <el-tag :type="syncStatusType(row.status)" size="small">
                  {{ syncStatusLabel(row.status) }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="完成率" min-width="82">
              <template #default="{ row }">
                <div class="progress-cell">
                  <el-progress
                    :percentage="taskProgress(row.status)"
                    :show-text="false"
                    :stroke-width="4"
                    :status="row.status === 'failed' ? 'exception' : undefined"
                  />
                  <span>{{ taskProgress(row.status) }}%</span>
                </div>
              </template>
            </el-table-column>
          </el-table>
        </div>
      </div>

      <template #footer>
        <div class="drawer-footer">
          <el-button @click="collectionVisible = false">取消</el-button>
          <el-button
            type="primary"
            :loading="collectionSaving"
            @click="saveCollectionConfig"
          >
            保存配置
          </el-button>
        </div>
      </template>
    </el-drawer>

    <el-dialog
      v-model="historyVisible"
      :title="historyProduct?.title || '价格历史'"
      width="640px"
      destroy-on-close
      class="history-dialog"
      @closed="closeHistory"
    >
      <p v-if="historyProduct" class="history-sub">
        {{ platformLabel(historyProduct.platform) }} · {{ historyProduct.external_id }}
      </p>

      <div v-if="historyLoading" class="history-body">
        <el-skeleton animated :rows="5" />
      </div>
      <div v-else-if="historyError" class="state-block">
        <p class="state-title">{{ historyError }}</p>
      </div>
      <div v-else class="history-body">
        <div ref="chartRef" class="history-chart" />
        <div class="history-stats">
          <div class="stat">
            <span class="stat-label">当前价</span>
            <span class="stat-value">
              {{ historyStats.current != null ? `$${historyStats.current.toFixed(2)}` : '—' }}
            </span>
          </div>
          <div class="stat">
            <span class="stat-label">最低价</span>
            <span class="stat-value">
              {{ historyStats.min != null ? `$${historyStats.min.toFixed(2)}` : '—' }}
            </span>
          </div>
          <div class="stat">
            <span class="stat-label">最高价</span>
            <span class="stat-value">
              {{ historyStats.max != null ? `$${historyStats.max.toFixed(2)}` : '—' }}
            </span>
          </div>
        </div>
      </div>

      <template #footer>
        <el-button @click="historyVisible = false">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.products-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
  min-height: calc(100vh - var(--header-height) - 48px);
}

.page-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.page-title {
  margin: 0;
}

.toolbar-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}

.filter-bar {
  display: flex;
  flex-direction: column;
  align-items: stretch;
  gap: 12px;
  padding: 12px 16px;
}

.filter-controls {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 12px;
}

.filter-search {
  width: 260px;
}

.filter-platform {
  width: 128px;
}

.filter-category {
  width: 140px;
}

.filter-sort {
  width: 156px;
}

.watched-check {
  margin-left: 0;
}

.last-sync {
  font-size: 12px;
  color: var(--color-ink-muted);
}

.workspace {
  display: grid;
  grid-template-columns: 260px minmax(0, 1fr);
  gap: 16px;
  align-items: stretch;
  flex: 1;
  min-height: 0;
}

.category-panel,
.table-panel {
  display: flex;
  flex-direction: column;
  min-height: 520px;
  padding: 0;
  overflow: hidden;
}

.panel-head {
  padding: 16px 16px 12px;
  border-bottom: 1px solid var(--color-hairline);
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.table-head {
  border-bottom: 1px solid var(--color-hairline);
}

.panel-title-row {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 8px;
}

.panel-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--color-ink);
}

.panel-meta {
  font-size: 12px;
  color: var(--color-ink-muted);
}

.panel-body {
  padding: 16px;
}

.category-scroll {
  flex: 1;
  overflow: auto;
  padding: 8px;
}

.category-item.all {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 8px;
  height: 36px;
  padding: 0 10px 0 12px;
  margin-bottom: 4px;
  border: none;
  border-radius: 6px;
  background: transparent;
  color: var(--color-ink-secondary);
  cursor: pointer;
  text-align: left;
  transition: background-color 120ms ease;
}

.category-item.all:hover {
  background: var(--color-surface-sunken);
}

.category-item.all.active {
  background: var(--color-primary-subtle);
  color: var(--color-primary);
  box-shadow: inset 3px 0 0 var(--color-primary);
}

.category-tree {
  background: transparent;
}

.category-tree :deep(.el-tree-node__content) {
  height: 36px;
  border-radius: 6px;
  padding-right: 8px;
  transition: background-color 120ms ease;
}

.category-tree :deep(.el-tree-node__content:hover) {
  background: var(--color-surface-sunken);
}

.category-tree :deep(.el-tree-node.is-current > .el-tree-node__content) {
  background: var(--color-primary-subtle);
  box-shadow: inset 3px 0 0 var(--color-primary);
}

.category-node {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  min-width: 0;
  padding-right: 4px;
  color: var(--color-ink-secondary);
}

.category-node.active {
  color: var(--color-primary);
}

.cat-icon {
  font-size: 16px;
  flex-shrink: 0;
  color: inherit;
}

.cat-name {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 14px;
}

.cat-count {
  flex-shrink: 0;
  min-width: 32px;
  text-align: right;
  color: var(--color-ink-muted);
  font-size: 12px;
  font-variant-numeric: tabular-nums;
}

.filter-empty {
  padding: 24px 8px;
  text-align: center;
  color: var(--color-ink-muted);
  font-size: 12px;
}

.collection-card {
  margin: 8px;
  padding: 12px;
  border: 1px solid var(--color-hairline);
  border-radius: 6px;
  background: var(--color-surface-sunken);
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  text-align: center;
}

.collection-card-label {
  width: 100%;
  color: var(--color-primary);
  font-size: 12px;
  font-weight: 600;
  text-align: left;
}

.collection-card-icon {
  margin-top: 4px;
  font-size: 30px;
  color: var(--color-ink-disabled);
}

.collection-card strong {
  font-size: 13px;
  color: var(--color-ink);
}

.collection-card span,
.collection-card small {
  color: var(--color-ink-muted);
  font-size: 11px;
}

.table-wrap {
  position: relative;
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
  overflow-x: auto;
  -webkit-overflow-scrolling: touch;
}

.table-wrap .product-table {
  min-width: 860px;
  flex: 1;
}

.table-skeleton {
  padding: 16px;
}

.product-table :deep(.el-table__header th) {
  background: var(--color-surface-sunken);
  color: var(--color-ink-muted);
  font-size: 12px;
  font-weight: 500;
}

.product-table :deep(.el-table__row) {
  height: 56px;
}

.product-table :deep(.el-table__row:hover > td) {
  background: var(--color-surface-sunken) !important;
}

.product-cell {
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 0;
}

.product-thumb {
  width: 40px;
  height: 40px;
  border-radius: 6px;
  border: 1px solid var(--color-hairline);
  background: var(--color-surface-sunken);
  overflow: hidden;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
}

.product-thumb img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.thumb-fallback {
  color: var(--color-ink-disabled);
  font-size: 18px;
}

.product-meta {
  min-width: 0;
}

.product-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--color-ink);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.product-id {
  margin-top: 2px;
  font-size: 12px;
  color: var(--color-ink-muted);
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
}

.category-label,
.sync-time {
  color: var(--color-ink-secondary);
  font-size: 12px;
}

.platform-tag {
  display: inline-flex;
  align-items: center;
  height: 22px;
  padding: 0 8px;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 500;
}

.tag-amazon {
  background: #f3f4f6;
  color: #374151;
}

.tag-shopee {
  background: #fff7ed;
  color: #ea580c;
}

.tag-neutral {
  background: var(--color-surface-sunken);
  color: var(--color-ink-secondary);
}

.price-text {
  color: var(--color-primary);
  font-weight: 600;
  font-variant-numeric: tabular-nums;
}

.rating-text {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
}

.rating-text .el-icon {
  font-size: 14px;
}

.tone-high {
  color: var(--color-success);
}

.tone-mid {
  color: var(--color-warning);
}

.tone-low {
  color: var(--color-danger);
}

.tone-none {
  color: var(--color-ink-muted);
}

.muted {
  color: var(--color-ink-muted);
}

.row-actions {
  display: flex;
  align-items: center;
  gap: 4px;
  flex-wrap: wrap;
}

.table-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 12px 16px;
  border-top: 1px solid var(--color-hairline);
}

.footer-total {
  font-size: 13px;
  color: var(--color-ink-muted);
}

.refresh-mask {
  position: absolute;
  inset: 0;
  background: rgba(255, 255, 255, 0.55);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 2;
}

.refresh-mask .el-icon {
  font-size: 22px;
  color: var(--color-primary);
}

.inline-alert {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin: 12px 16px 0;
  padding: 10px 12px;
  border-radius: 6px;
  background: #fef2f2;
  color: var(--color-danger);
  font-size: 13px;
}

.state-block {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 40px 24px;
  text-align: center;
}

.state-block.in-table {
  min-height: 280px;
}

.state-icon {
  font-size: 36px;
  color: var(--color-ink-disabled);
}

.state-icon.danger {
  color: var(--color-danger);
}

.state-title {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  color: var(--color-ink);
}

.state-desc {
  margin: 0 0 8px;
  font-size: 12px;
  color: var(--color-ink-muted);
  max-width: 280px;
}

.history-sub {
  margin: -8px 0 16px;
  font-size: 12px;
  color: var(--color-ink-muted);
}

.history-body {
  min-height: 280px;
}

.history-chart {
  width: 100%;
  height: 280px;
}

.history-stats {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px solid var(--color-hairline);
}

.stat {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.stat-label {
  font-size: 12px;
  color: var(--color-ink-muted);
}

.stat-value {
  font-size: 16px;
  font-weight: 600;
  color: var(--color-ink);
  font-variant-numeric: tabular-nums;
}

.collection-form {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.form-label {
  color: var(--color-ink-secondary);
  font-size: 13px;
  font-weight: 500;
}

.drawer-control {
  width: 100%;
  margin-bottom: 8px;
}

.radio-row {
  display: flex;
  gap: 24px;
  margin-bottom: 8px;
}

.switch-row {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 8px;
}

.schedule-note {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 12px 0 16px;
  border-bottom: 1px solid var(--color-hairline);
  color: var(--color-ink-muted);
  font-size: 12px;
}

.schedule-note strong {
  color: var(--color-ink-secondary);
  font-weight: 500;
}

.tasks-section {
  margin-top: 8px;
}

.tasks-section h3 {
  margin: 0 0 12px;
  color: var(--color-ink);
  font-size: 14px;
  font-weight: 600;
}

.task-table :deep(.el-table__header th) {
  background: var(--color-surface-sunken);
  color: var(--color-ink-muted);
  font-size: 11px;
}

.task-table :deep(.el-table__cell) {
  padding: 8px 0;
  font-size: 11px;
}

.task-id {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 10px;
}

.progress-cell {
  display: grid;
  grid-template-columns: minmax(36px, 1fr) 28px;
  align-items: center;
  gap: 6px;
  color: var(--color-ink-muted);
  font-size: 10px;
}

.drawer-footer {
  display: flex;
  justify-content: space-between;
  width: 100%;
}

:deep(.collection-drawer .el-drawer__header) {
  margin-bottom: 0;
  padding: 18px 24px;
  border-bottom: 1px solid var(--color-hairline);
  color: var(--color-ink);
  font-weight: 600;
}

:deep(.collection-drawer .el-drawer__body) {
  padding: 20px 24px;
}

:deep(.collection-drawer .el-drawer__footer) {
  padding: 16px 24px;
  border-top: 1px solid var(--color-hairline);
}

@media (max-width: 1100px) {
  .workspace {
    grid-template-columns: 220px minmax(0, 1fr);
  }
}

@media (max-width: 900px) {
  .workspace {
    grid-template-columns: 1fr;
  }

  .category-panel {
    min-height: 280px;
    max-height: 360px;
  }

  .filter-search {
    width: 100%;
  }
}
</style>
