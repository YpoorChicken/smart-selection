<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Lightning,
  Refresh,
  Sort,
  WarningFilled,
} from '@element-plus/icons-vue'
import ScoreRing from '@/components/ScoreRing.vue'
import {
  acceptRecommendation,
  generateRecommendations,
  generateSelectionAIAnalysis,
  getBlueOceanCategories,
  getRecommendationStats,
  getRecommendations,
  rejectRecommendation,
} from '@/api/recommendations'
import { getCategoryTree } from '@/api/products'
import { useAuthStore } from '@/stores/auth'
import type { PlatformId } from '@/types/products'
import type {
  BlueOceanCategoryItem,
  RecommendationItem,
  RecommendationStats,
  RecommendationStatus,
  SelectionAIAnalysis,
} from '@/types/recommendations'

type TabKey = 'blue-ocean' | 'list' | 'accepted'
type LoadState = 'idle' | 'loading' | 'success' | 'empty' | 'error'

const PLATFORM_OPTIONS: { label: string; value: PlatformId | '' }[] = [
  { label: '全部平台', value: '' },
  { label: 'FakeStore', value: 'fakestore' },
  { label: 'Amazon', value: 'amazon' },
  { label: 'Shopee', value: 'shopee' },
  { label: 'Mock', value: 'mock' },
]

const SCORE_OPTIONS = [
  { label: '全部评分', value: 0 },
  { label: '蓝海指数 ≥ 80', value: 80 },
  { label: '蓝海指数 ≥ 60', value: 60 },
  { label: '蓝海指数 ≥ 40', value: 40 },
]

const SALES_OPTIONS = [
  { label: '全部销量', value: 0 },
  { label: '样本 ≥ 5', value: 5 },
  { label: '样本 ≥ 10', value: 10 },
  { label: '样本 ≥ 20', value: 20 },
]

const PRICE_OPTIONS = [
  { label: '全部价格', value: 'all' },
  { label: '$0 – $25', value: '0-25' },
  { label: '$25 – $50', value: '25-50' },
  { label: '$50 – $100', value: '50-100' },
  { label: '$100+', value: '100+' },
]

const SORT_OPTIONS = [
  { label: '蓝海指数从高到低', value: 'score_desc' },
  { label: '蓝海指数从低到高', value: 'score_asc' },
  { label: '样本销量从高到低', value: 'sales_desc' },
  { label: '均价从高到低', value: 'price_desc' },
]

const SCORE_HIGH = '#059669'
const SCORE_MID = '#D97706'
const SCORE_LOW = '#DC2626'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

const activeTab = ref<TabKey>('blue-ocean')
const stats = ref<RecommendationStats>({
  pending: 0,
  accepted: 0,
  rejected: 0,
  total: 0,
})

const canDecide = computed(() => {
  const role = auth.user?.role
  return role === 'selection_manager' || role === 'ops_lead'
})

/** —— 蓝海发现 —— */
const oceanState = ref<LoadState>('idle')
const oceanError = ref('')
const oceanRaw = ref<BlueOceanCategoryItem[]>([])
const categoryOptions = ref<{ label: string; value: string }[]>([
  { label: '全部品类', value: '' },
])
const oceanFilters = reactive({
  categoryId: '',
  platformId: '' as PlatformId | '',
  minScore: 60,
  minSales: 0,
  priceRange: 'all',
  sortBy: 'score_desc',
})
const oceanPage = ref(1)
const oceanPageSize = ref(6)
const oceanActionId = ref<string | null>(null)

/** —— 推荐列表 / 已接受 —— */
const listState = ref<LoadState>('idle')
const listError = ref('')
const listItems = ref<RecommendationItem[]>([])
const listPage = ref(1)
const listPageSize = ref(10)
const listTotal = ref(0)
const listPlatform = ref<PlatformId | ''>('')

/** —— AI 抽屉 —— */
const drawerVisible = ref(false)
const drawerLoading = ref(false)
const drawerError = ref('')
const drawerContext = ref<{
  title: string
  categoryName: string
  platformId: PlatformId | null
  score: number
  recommendationId: string
} | null>(null)
const drawerAnalysis = ref<SelectionAIAnalysis | null>(null)
const deciding = ref(false)

function toNumber(value: string | number | null | undefined): number | null {
  if (value == null || value === '') return null
  const num = typeof value === 'number' ? value : Number(value)
  return Number.isFinite(num) ? num : null
}

function scoreTone(score: number | null): string {
  if (score == null) return SCORE_MID
  if (score >= 80) return SCORE_HIGH
  if (score >= 60) return SCORE_MID
  return SCORE_LOW
}

function formatPrice(value: string | number | null | undefined): string {
  const num = toNumber(value)
  if (num == null) return '—'
  return `$${num.toFixed(2)}`
}

function formatPercent(value: string | number | null | undefined): string {
  const num = toNumber(value)
  if (num == null) return '—'
  const sign = num > 0 ? '+' : ''
  return `${sign}${(num * 100).toFixed(1)}%`
}

function formatDateTime(value: string | null | undefined): string {
  if (!value) return '—'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  const mm = String(date.getMonth() + 1).padStart(2, '0')
  const dd = String(date.getDate()).padStart(2, '0')
  const hh = String(date.getHours()).padStart(2, '0')
  const mi = String(date.getMinutes()).padStart(2, '0')
  return `${mm}-${dd} ${hh}:${mi}`
}

function platformLabel(platform: PlatformId | string | null | undefined): string {
  if (!platform) return '—'
  const map: Record<string, string> = {
    amazon: 'Amazon',
    shopee: 'Shopee',
    fakestore: 'FakeStore',
    mock: 'Mock',
  }
  return map[platform] || platform
}

function statusLabel(status: RecommendationStatus): string {
  if (status === 'pending') return '待审'
  if (status === 'accepted') return '已接受'
  return '已拒绝'
}

function statusTagType(status: RecommendationStatus): 'warning' | 'success' | 'danger' {
  if (status === 'pending') return 'warning'
  if (status === 'accepted') return 'success'
  return 'danger'
}

function estimateMonthlySales(item: BlueOceanCategoryItem): number {
  // 无真实月销字段时，用评论/样本量作运营可读代理
  return Math.max(1, Math.round(item.sample_size * 12))
}

function riskTags(item: BlueOceanCategoryItem): { text: string; tone: 'ok' | 'warn' | 'bad' }[] {
  const demand = toNumber(item.scores.demand) ?? 0
  const competition = toNumber(item.scores.competition) ?? 0
  const margin = toNumber(item.scores.margin) ?? 0
  const trend = toNumber(item.scores.trend) ?? 0
  const tags: { text: string; tone: 'ok' | 'warn' | 'bad' }[] = []

  if (competition >= 70) tags.push({ text: '竞争缓和', tone: 'ok' })
  else if (competition >= 45) tags.push({ text: '竞争中等', tone: 'warn' })
  else tags.push({ text: '竞争激烈', tone: 'bad' })

  if (margin >= 70) tags.push({ text: '利润空间充足', tone: 'ok' })
  else if (margin >= 45) tags.push({ text: '利润一般', tone: 'warn' })
  else tags.push({ text: '利润承压', tone: 'bad' })

  if (trend >= 60) tags.push({ text: '趋势向好', tone: 'ok' })
  else if (demand < 50) tags.push({ text: '需求偏弱', tone: 'warn' })
  else tags.push({ text: '趋势观望', tone: 'warn' })

  return tags.slice(0, 3)
}

function riskLevel(item: BlueOceanCategoryItem): { text: string; tone: 'ok' | 'warn' | 'bad' } {
  const score = toNumber(item.blue_ocean_index) ?? 0
  if (score >= 80) return { text: '低风险', tone: 'ok' }
  if (score >= 60) return { text: '中风险', tone: 'warn' }
  return { text: '高风险', tone: 'bad' }
}

function dimensionRows(item: BlueOceanCategoryItem) {
  return [
    { key: 'demand', label: '市场需求', value: toNumber(item.scores.demand) },
    { key: 'competition', label: '竞争强度', value: toNumber(item.scores.competition) },
    { key: 'margin', label: '利润空间', value: toNumber(item.scores.margin) },
    { key: 'trend', label: '趋势方向', value: toNumber(item.scores.trend) },
  ]
}

const filteredOcean = computed(() => {
  let rows = [...oceanRaw.value]

  if (oceanFilters.categoryId) {
    rows = rows.filter((item) => item.category_id === oceanFilters.categoryId)
  }
  if (oceanFilters.platformId) {
    rows = rows.filter((item) => item.platform_id === oceanFilters.platformId)
  }
  rows = rows.filter((item) => {
    const score = toNumber(item.blue_ocean_index) ?? 0
    return score >= oceanFilters.minScore
  })
  if (oceanFilters.minSales > 0) {
    rows = rows.filter((item) => item.sample_size >= oceanFilters.minSales)
  }
  if (oceanFilters.priceRange !== 'all') {
    rows = rows.filter((item) => {
      const price = toNumber(item.avg_price)
      if (price == null) return false
      if (oceanFilters.priceRange === '0-25') return price < 25
      if (oceanFilters.priceRange === '25-50') return price >= 25 && price < 50
      if (oceanFilters.priceRange === '50-100') return price >= 50 && price < 100
      if (oceanFilters.priceRange === '100+') return price >= 100
      return true
    })
  }

  rows.sort((a, b) => {
    const scoreA = toNumber(a.blue_ocean_index) ?? 0
    const scoreB = toNumber(b.blue_ocean_index) ?? 0
    const priceA = toNumber(a.avg_price) ?? 0
    const priceB = toNumber(b.avg_price) ?? 0
    if (oceanFilters.sortBy === 'score_asc') return scoreA - scoreB
    if (oceanFilters.sortBy === 'sales_desc') return b.sample_size - a.sample_size
    if (oceanFilters.sortBy === 'price_desc') return priceB - priceA
    return scoreB - scoreA
  })

  return rows
})

const pagedOcean = computed(() => {
  const start = (oceanPage.value - 1) * oceanPageSize.value
  return filteredOcean.value.slice(start, start + oceanPageSize.value)
})

const oceanTotal = computed(() => filteredOcean.value.length)

watch(
  () => [
    oceanFilters.categoryId,
    oceanFilters.platformId,
    oceanFilters.minScore,
    oceanFilters.minSales,
    oceanFilters.priceRange,
    oceanFilters.sortBy,
  ],
  () => {
    oceanPage.value = 1
  },
)

async function loadStats() {
  try {
    stats.value = await getRecommendationStats()
  } catch {
    // 角标失败不阻断主列表
  }
}

async function loadCategoryOptions() {
  try {
    const platform = oceanFilters.platformId || undefined
    const tree = await getCategoryTree(platform)
    const flat: { label: string; value: string }[] = [{ label: '全部品类', value: '' }]
    const walk = (nodes: typeof tree.items, depth = 0) => {
      for (const node of nodes) {
        const prefix = depth > 0 ? `${'· '.repeat(depth)}` : ''
        flat.push({ label: `${prefix}${node.name}`, value: node.id })
        if (node.children?.length) walk(node.children, depth + 1)
      }
    }
    walk(tree.items)
    categoryOptions.value = flat
  } catch {
    categoryOptions.value = [{ label: '全部品类', value: '' }]
  }
}

async function loadBlueOcean() {
  const requestId = Date.now()
  oceanState.value = 'loading'
  oceanError.value = ''
  try {
    const data = await getBlueOceanCategories({
      platform_id: oceanFilters.platformId || undefined,
      min_demand: 0,
      min_competition: 0,
      limit: 100,
    })
    oceanRaw.value = data.items
    oceanState.value = data.items.length ? 'success' : 'empty'
    void requestId
  } catch (error) {
    oceanState.value = 'error'
    oceanError.value = error instanceof Error ? error.message : '加载蓝海机会失败'
  }
}

async function loadList(status?: RecommendationStatus) {
  listState.value = 'loading'
  listError.value = ''
  try {
    const data = await getRecommendations({
      page: listPage.value,
      page_size: listPageSize.value,
      status,
      platform_id: listPlatform.value || undefined,
    })
    listItems.value = data.items
    listTotal.value = data.meta.total
    listState.value = data.items.length ? 'success' : 'empty'
  } catch (error) {
    listState.value = 'error'
    listError.value = error instanceof Error ? error.message : '加载推荐列表失败'
  }
}

async function refreshCurrentTab() {
  await loadStats()
  if (activeTab.value === 'blue-ocean') {
    await Promise.all([loadCategoryOptions(), loadBlueOcean()])
    return
  }
  if (activeTab.value === 'accepted') {
    await loadList('accepted')
    return
  }
  await loadList()
}

async function ensureRecommendationId(item: BlueOceanCategoryItem): Promise<string> {
  if (item.recommendation_id) return item.recommendation_id
  const generated = await generateRecommendations({
    category_id: item.category_id,
    platform_id: item.platform_id,
    limit: 1,
  })
  const row = generated.items[0]
  if (!row) throw new Error('未能生成推荐记录')
  item.recommendation_id = row.id
  return row.id
}

async function openAIAnalysis(item: BlueOceanCategoryItem) {
  oceanActionId.value = item.category_id
  drawerVisible.value = true
  drawerLoading.value = true
  drawerError.value = ''
  drawerAnalysis.value = null
  const score = toNumber(item.blue_ocean_index) ?? 0
  drawerContext.value = {
    title: item.title,
    categoryName: item.category_name,
    platformId: item.platform_id,
    score,
    recommendationId: item.recommendation_id || '',
  }

  try {
    const id = await ensureRecommendationId(item)
    drawerContext.value.recommendationId = id
    const data = await generateSelectionAIAnalysis(id)
    drawerAnalysis.value = data.analysis
  } catch (error) {
    drawerError.value = error instanceof Error ? error.message : 'AI 分析失败'
  } finally {
    drawerLoading.value = false
    oceanActionId.value = null
  }
}

async function openAIFromList(row: RecommendationItem) {
  drawerVisible.value = true
  drawerLoading.value = true
  drawerError.value = ''
  drawerAnalysis.value = null
  drawerContext.value = {
    title: row.title,
    categoryName: row.category_name || '—',
    platformId: row.platform_id,
    score: toNumber(row.score_total) ?? 0,
    recommendationId: row.id,
  }
  try {
    if (row.reason) {
      try {
        const parsed = JSON.parse(row.reason) as SelectionAIAnalysis
        if (parsed.market_opportunity) {
          drawerAnalysis.value = parsed
          drawerLoading.value = false
          return
        }
      } catch {
        // fall through to regenerate
      }
    }
    const data = await generateSelectionAIAnalysis(row.id)
    drawerAnalysis.value = data.analysis
  } catch (error) {
    drawerError.value = error instanceof Error ? error.message : 'AI 分析失败'
  } finally {
    drawerLoading.value = false
  }
}

async function handleAcceptFromOcean(item: BlueOceanCategoryItem) {
  if (!canDecide.value) {
    ElMessage.warning('当前账号无选品决策权限（需选品经理或运营主管）')
    return
  }
  try {
    await ElMessageBox.confirm(
      `确认接受「${item.category_name}」选品推荐？`,
      '接受选品',
      { type: 'warning', confirmButtonText: '接受', cancelButtonText: '取消' },
    )
  } catch {
    return
  }

  oceanActionId.value = item.category_id
  try {
    const id = await ensureRecommendationId(item)
    await acceptRecommendation(id)
    ElMessage.success('已接受该选品')
    await refreshCurrentTab()
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '接受失败')
  } finally {
    oceanActionId.value = null
  }
}

async function handleAcceptFromDrawer() {
  if (!drawerContext.value?.recommendationId) return
  if (!canDecide.value) {
    ElMessage.warning('当前账号无选品决策权限（需选品经理或运营主管）')
    return
  }
  try {
    await ElMessageBox.confirm('确认接受该选品？决策后不可撤销。', '接受选品', {
      type: 'warning',
      confirmButtonText: '接受该选品',
      cancelButtonText: '取消',
    })
  } catch {
    return
  }
  deciding.value = true
  try {
    await acceptRecommendation(drawerContext.value.recommendationId)
    ElMessage.success('已接受，记录已同步')
    drawerVisible.value = false
    activeTab.value = 'accepted'
    await syncTabQuery('accepted')
    await refreshCurrentTab()
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '接受失败')
  } finally {
    deciding.value = false
  }
}

async function handleRejectFromDrawer() {
  if (!drawerContext.value?.recommendationId) return
  if (!canDecide.value) {
    ElMessage.warning('当前账号无选品决策权限（需选品经理或运营主管）')
    return
  }
  let reason = ''
  try {
    const { value } = await ElMessageBox.prompt('可选填写拒绝原因', '拒绝选品', {
      confirmButtonText: '确认拒绝',
      cancelButtonText: '取消',
      inputPlaceholder: '例如：毛利不足 / 专利风险',
      inputValidator: () => true,
    })
    reason = value || ''
  } catch {
    return
  }
  deciding.value = true
  try {
    await rejectRecommendation(drawerContext.value.recommendationId, reason || undefined)
    ElMessage.success('已拒绝该选品')
    drawerVisible.value = false
    await refreshCurrentTab()
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '拒绝失败')
  } finally {
    deciding.value = false
  }
}

async function syncTabQuery(tab: TabKey) {
  const query = { ...route.query, tab }
  await router.replace({ query })
}

const tabReady = ref(false)

watch(activeTab, async (tab) => {
  if (!tabReady.value) return
  await syncTabQuery(tab)
  listPage.value = 1
  await refreshCurrentTab()
})

watch([listPage, listPageSize, listPlatform], async () => {
  if (!tabReady.value || activeTab.value === 'blue-ocean') return
  await loadList(activeTab.value === 'accepted' ? 'accepted' : undefined)
})

watch(
  () => oceanFilters.platformId,
  async () => {
    if (!tabReady.value || activeTab.value !== 'blue-ocean') return
    await loadCategoryOptions()
    await loadBlueOcean()
  },
)

onMounted(async () => {
  const tab = route.query.tab
  if (tab === 'list' || tab === 'accepted' || tab === 'blue-ocean') {
    activeTab.value = tab
  }
  tabReady.value = true
  await refreshCurrentTab()
})
</script>

<template>
  <div class="selections-page">
    <header class="page-head">
      <div>
        <h1 class="page-title">选品推荐</h1>
        <p class="page-desc">蓝海指数与四维评分，辅助跨境选品决策</p>
      </div>
      <el-button :icon="Refresh" @click="refreshCurrentTab">刷新</el-button>
    </header>

    <el-tabs v-model="activeTab" class="sel-tabs">
      <el-tab-pane name="blue-ocean">
        <template #label>
          <span>蓝海发现</span>
          <span class="tab-count">{{ oceanTotal || oceanRaw.length }}</span>
        </template>
      </el-tab-pane>
      <el-tab-pane name="list">
        <template #label>
          <span>推荐列表</span>
          <span class="tab-count">{{ stats.total }}</span>
        </template>
      </el-tab-pane>
      <el-tab-pane name="accepted">
        <template #label>
          <span>已接受</span>
          <span class="tab-count">{{ stats.accepted }}</span>
        </template>
      </el-tab-pane>
    </el-tabs>

    <!-- 蓝海发现 -->
    <section v-if="activeTab === 'blue-ocean'" class="panel">
      <div class="filter-bar">
        <el-select v-model="oceanFilters.categoryId" placeholder="品类" clearable filterable class="filter-item">
          <el-option
            v-for="opt in categoryOptions"
            :key="opt.value || 'all'"
            :label="opt.label"
            :value="opt.value"
          />
        </el-select>
        <el-select v-model="oceanFilters.platformId" placeholder="平台" class="filter-item">
          <el-option
            v-for="opt in PLATFORM_OPTIONS"
            :key="opt.label"
            :label="opt.label"
            :value="opt.value"
          />
        </el-select>
        <el-select v-model="oceanFilters.minScore" placeholder="评分" class="filter-item">
          <el-option
            v-for="opt in SCORE_OPTIONS"
            :key="opt.value"
            :label="opt.label"
            :value="opt.value"
          />
        </el-select>
        <el-select v-model="oceanFilters.minSales" placeholder="销量" class="filter-item">
          <el-option
            v-for="opt in SALES_OPTIONS"
            :key="opt.value"
            :label="opt.label"
            :value="opt.value"
          />
        </el-select>
        <el-select v-model="oceanFilters.priceRange" placeholder="价格区间" class="filter-item">
          <el-option
            v-for="opt in PRICE_OPTIONS"
            :key="opt.value"
            :label="opt.label"
            :value="opt.value"
          />
        </el-select>
        <el-select v-model="oceanFilters.sortBy" placeholder="排序" class="filter-item filter-item--sort">
          <template #prefix>
            <el-icon><Sort /></el-icon>
          </template>
          <el-option
            v-for="opt in SORT_OPTIONS"
            :key="opt.value"
            :label="opt.label"
            :value="opt.value"
          />
        </el-select>
      </div>

      <div class="result-meta">
        <span>共找到 <strong>{{ oceanTotal }}</strong> 个蓝海机会</span>
        <span class="meta-hint">圆环：≥80 绿 · 60–79 黄 · &lt;60 红</span>
      </div>

      <div v-if="oceanState === 'loading'" class="state-box">
        <el-skeleton :rows="4" animated />
      </div>
      <div v-else-if="oceanState === 'error'" class="state-box state-box--error">
        <el-icon :size="20"><WarningFilled /></el-icon>
        <span>{{ oceanError }}</span>
        <el-button type="primary" link @click="loadBlueOcean">重试</el-button>
      </div>
      <div v-else-if="oceanState === 'empty' || oceanTotal === 0" class="state-box">
        暂无蓝海机会，可先同步商品并触发打分后再试。
      </div>

      <div v-else class="ocean-grid">
        <article
          v-for="(item, index) in pagedOcean"
          :key="item.category_id"
          class="ocean-card"
        >
          <div class="ocean-card__rank" :class="`rank-${(oceanPage - 1) * oceanPageSize + index + 1}`">
            {{ (oceanPage - 1) * oceanPageSize + index + 1 }}
          </div>
          <header class="ocean-card__head">
            <h3 class="ocean-card__title" :title="item.title">{{ item.title }}</h3>
            <div class="ocean-card__sub">
              <span>{{ item.category_name }}</span>
              <el-tag size="small" effect="plain" class="platform-tag">
                {{ platformLabel(item.platform_id) }}
              </el-tag>
            </div>
          </header>

          <div class="ocean-card__score-row">
            <ScoreRing :score="toNumber(item.blue_ocean_index)" :size="88" />
            <dl class="kpi-list">
              <div class="kpi">
                <dt>预计月销</dt>
                <dd>{{ estimateMonthlySales(item).toLocaleString() }}</dd>
              </div>
              <div class="kpi">
                <dt>需求增长</dt>
                <dd
                  :class="{
                    'is-up': (toNumber(item.growth_rate) ?? 0) > 0,
                    'is-down': (toNumber(item.growth_rate) ?? 0) < 0,
                  }"
                >
                  {{ formatPercent(item.growth_rate) }}
                </dd>
              </div>
              <div class="kpi">
                <dt>样本数</dt>
                <dd>{{ item.sample_size }}</dd>
              </div>
              <div class="kpi">
                <dt>均价</dt>
                <dd>{{ formatPrice(item.avg_price) }}</dd>
              </div>
            </dl>
          </div>

          <div class="dims">
            <div class="dims__title">四维评估</div>
            <div v-for="dim in dimensionRows(item)" :key="dim.key" class="dim-row">
              <span class="dim-row__label">{{ dim.label }}</span>
              <el-progress
                :percentage="dim.value ?? 0"
                :stroke-width="8"
                :show-text="false"
                :color="scoreTone(dim.value)"
              />
              <span class="dim-row__score" :style="{ color: scoreTone(dim.value) }">
                {{ dim.value ?? '—' }}
              </span>
            </div>
          </div>

          <div class="tag-row">
            <span class="risk-level" :class="`tone-${riskLevel(item).tone}`">
              {{ riskLevel(item).text }}
            </span>
            <span
              v-for="tag in riskTags(item)"
              :key="tag.text"
              class="risk-tag"
              :class="`tone-${tag.tone}`"
            >
              {{ tag.text }}
            </span>
          </div>

          <footer class="ocean-card__actions">
            <el-button
              :loading="oceanActionId === item.category_id && drawerLoading"
              @click="openAIAnalysis(item)"
            >
              <el-icon class="btn-icon"><Lightning /></el-icon>
              AI 分析
            </el-button>
            <el-button
              type="primary"
              :disabled="!canDecide"
              :loading="oceanActionId === item.category_id && !drawerLoading"
              @click="handleAcceptFromOcean(item)"
            >
              接受
            </el-button>
          </footer>
        </article>
      </div>

      <div v-if="oceanTotal > oceanPageSize" class="pager">
        <el-pagination
          v-model:current-page="oceanPage"
          v-model:page-size="oceanPageSize"
          :total="oceanTotal"
          :page-sizes="[6, 9, 12]"
          layout="total, sizes, prev, pager, next"
          background
        />
      </div>
    </section>

    <!-- 推荐列表 / 已接受 -->
    <section v-else class="panel">
      <div class="filter-bar">
        <el-select v-model="listPlatform" placeholder="平台" clearable class="filter-item">
          <el-option
            v-for="opt in PLATFORM_OPTIONS"
            :key="opt.label"
            :label="opt.label"
            :value="opt.value"
          />
        </el-select>
        <span v-if="activeTab === 'accepted'" class="meta-hint">
          决策记录已同步至运营看板
        </span>
      </div>

      <div v-if="listState === 'loading'" class="state-box">
        <el-skeleton :rows="5" animated />
      </div>
      <div v-else-if="listState === 'error'" class="state-box state-box--error">
        {{ listError }}
        <el-button type="primary" link @click="refreshCurrentTab">重试</el-button>
      </div>
      <div v-else-if="listState === 'empty'" class="state-box">
        {{ activeTab === 'accepted' ? '暂无已接受选品' : '暂无推荐记录' }}
      </div>

      <el-table
        v-else
        :data="listItems"
        stripe
        class="rec-table"
        empty-text="暂无数据"
      >
        <el-table-column prop="title" label="推荐标题" min-width="220" show-overflow-tooltip />
        <el-table-column label="品类" min-width="120" show-overflow-tooltip>
          <template #default="{ row }">{{ row.category_name || '—' }}</template>
        </el-table-column>
        <el-table-column label="平台" width="110">
          <template #default="{ row }">{{ platformLabel(row.platform_id) }}</template>
        </el-table-column>
        <el-table-column label="综合分" width="100" align="center">
          <template #default="{ row }">
            <span class="score-cell" :style="{ color: scoreTone(toNumber(row.score_total)) }">
              {{ toNumber(row.score_total) ?? '—' }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="四维" min-width="180">
          <template #default="{ row }">
            <span class="dim-mini">
              需{{ toNumber(row.score_demand) ?? '—' }}
              · 竞{{ toNumber(row.score_competition) ?? '—' }}
              · 利{{ toNumber(row.score_margin) ?? '—' }}
              · 趋{{ toNumber(row.score_trend) ?? '—' }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="statusTagType(row.status)" size="small" effect="light">
              {{ statusLabel(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column
          v-if="activeTab === 'accepted'"
          label="决策时间"
          width="120"
        >
          <template #default="{ row }">{{ formatDateTime(row.decided_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="120" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" link @click="openAIFromList(row)">查看分析</el-button>
          </template>
        </el-table-column>
      </el-table>

      <div v-if="listTotal > 0" class="pager">
        <el-pagination
          v-model:current-page="listPage"
          v-model:page-size="listPageSize"
          :total="listTotal"
          :page-sizes="[10, 20, 50]"
          layout="total, sizes, prev, pager, next"
          background
        />
      </div>
    </section>

    <!-- AI 分析抽屉 -->
    <el-drawer
      v-model="drawerVisible"
      size="520px"
      append-to-body
      destroy-on-close
      class="ai-drawer"
      :close-on-click-modal="true"
    >
      <template #header>
        <div class="drawer-head">
          <div>
            <div class="drawer-kicker">AI 选品分析</div>
            <h2 class="drawer-title">{{ drawerContext?.title || '—' }}</h2>
            <div class="drawer-sub">
              <span>{{ drawerContext?.categoryName }}</span>
              <el-tag v-if="drawerContext?.platformId" size="small" effect="plain">
                {{ platformLabel(drawerContext.platformId) }}
              </el-tag>
            </div>
          </div>
          <ScoreRing :score="drawerContext?.score ?? null" :size="72" />
        </div>
      </template>

      <div v-if="drawerLoading" class="drawer-body">
        <el-skeleton :rows="8" animated />
      </div>
      <div v-else-if="drawerError" class="drawer-body state-box state-box--error">
        {{ drawerError }}
      </div>
      <div v-else-if="drawerAnalysis" class="drawer-body">
        <section class="ai-block">
          <h3>市场机会</h3>
          <p>{{ drawerAnalysis.market_opportunity }}</p>
        </section>
        <section class="ai-block">
          <h3>竞品格局</h3>
          <ul>
            <li
              v-for="comp in drawerAnalysis.competitive_landscape"
              :key="`${comp.rank}-${comp.name}`"
            >
              <strong>#{{ comp.rank }} {{ comp.name }}</strong>
              — {{ comp.differentiation }}
            </li>
          </ul>
        </section>
        <section class="ai-block">
          <h3>入局建议</h3>
          <p>{{ drawerAnalysis.entry_advice }}</p>
        </section>
        <section class="ai-block">
          <h3>风险提示</h3>
          <ul>
            <li v-for="(risk, idx) in drawerAnalysis.risks" :key="idx">{{ risk }}</li>
          </ul>
        </section>
      </div>

      <template #footer>
        <div class="drawer-footer">
          <el-button
            :disabled="!canDecide || !drawerContext?.recommendationId"
            :loading="deciding"
            @click="handleRejectFromDrawer"
          >
            拒绝
          </el-button>
          <el-button
            type="primary"
            :disabled="!canDecide || !drawerContext?.recommendationId"
            :loading="deciding"
            @click="handleAcceptFromDrawer"
          >
            接受该选品
          </el-button>
        </div>
      </template>
    </el-drawer>
  </div>
</template>

<style scoped>
.selections-page {
  --ink: #111827;
  --ink-muted: #6b7280;
  --hairline: #e5e7eb;
  --surface: #ffffff;
  --primary: #4f46e5;
  --score-high: #059669;
  --score-mid: #d97706;
  --score-low: #dc2626;

  display: flex;
  flex-direction: column;
  gap: 16px;
  min-height: 100%;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial,
    'Noto Sans SC', 'PingFang SC', 'Microsoft YaHei', sans-serif;
}

.page-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

.page-title {
  margin: 0;
  font-size: 22px;
  font-weight: 600;
  line-height: 1.3;
  color: var(--ink);
}

.page-desc {
  margin: 4px 0 0;
  font-size: 13px;
  color: var(--ink-muted);
}

.sel-tabs :deep(.el-tabs__header) {
  margin: 0;
}

.sel-tabs :deep(.el-tabs__item) {
  font-weight: 500;
}

.sel-tabs :deep(.el-tabs__item.is-active) {
  color: var(--primary);
  font-weight: 600;
}

.sel-tabs :deep(.el-tabs__active-bar) {
  background-color: var(--primary);
  height: 2px;
}

.tab-count {
  margin-left: 6px;
  padding: 0 6px;
  border-radius: 4px;
  background: #eef2ff;
  color: var(--primary);
  font-size: 12px;
  font-variant-numeric: tabular-nums;
}

.panel {
  background: var(--surface);
  border: 1px solid var(--hairline);
  border-radius: 8px;
  padding: 16px;
  box-shadow: 0 1px 2px rgba(17, 24, 39, 0.04);
}

.filter-bar {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
  margin-bottom: 12px;
}

.filter-item {
  width: 148px;
}

.filter-item--sort {
  width: 180px;
}

.result-meta {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
  font-size: 13px;
  color: var(--ink-muted);
}

.result-meta strong {
  color: var(--ink);
  font-variant-numeric: tabular-nums;
}

.meta-hint {
  font-size: 12px;
  color: var(--ink-muted);
}

.state-box {
  padding: 32px 16px;
  text-align: center;
  color: var(--ink-muted);
  font-size: 14px;
}

.state-box--error {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  color: var(--score-low);
}

.ocean-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 16px;
}

.ocean-card {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 16px;
  border: 1px solid var(--hairline);
  border-radius: 8px;
  background: var(--surface);
  box-shadow: 0 1px 2px rgba(17, 24, 39, 0.06);
  transition:
    transform 120ms ease-out,
    box-shadow 120ms ease-out,
    border-color 120ms ease-out;
}

.ocean-card:hover {
  transform: translateY(-2px);
  border-color: #d1d5db;
  box-shadow: 0 8px 20px rgba(17, 24, 39, 0.08);
}

.ocean-card__rank {
  position: absolute;
  top: 12px;
  left: 12px;
  width: 22px;
  height: 22px;
  border-radius: 4px;
  background: #e5e7eb;
  color: var(--ink);
  font-size: 12px;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
}

.ocean-card__rank.rank-1 {
  background: #f59e0b;
  color: #fff;
}

.ocean-card__head {
  padding-left: 28px;
  min-width: 0;
}

.ocean-card__title {
  margin: 0;
  font-size: 14px;
  font-weight: 600;
  line-height: 1.45;
  color: var(--ink);
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.ocean-card__sub {
  margin-top: 4px;
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: var(--ink-muted);
}

.platform-tag {
  border-color: #ffedd5;
  background: #fff7ed;
  color: #c2410c;
}

.ocean-card__score-row {
  display: flex;
  align-items: center;
  gap: 16px;
}

.kpi-list {
  margin: 0;
  flex: 1;
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px 12px;
}

.kpi dt {
  margin: 0;
  font-size: 11px;
  color: var(--ink-muted);
}

.kpi dd {
  margin: 2px 0 0;
  font-size: 14px;
  font-weight: 600;
  color: var(--ink);
  font-variant-numeric: tabular-nums;
}

.kpi dd.is-up {
  color: var(--score-high);
}

.kpi dd.is-down {
  color: var(--score-low);
}

.dims__title {
  margin-bottom: 8px;
  font-size: 12px;
  font-weight: 600;
  color: var(--ink);
}

.dim-row {
  display: grid;
  grid-template-columns: 64px 1fr 28px;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}

.dim-row__label {
  font-size: 12px;
  color: var(--ink-muted);
}

.dim-row__score {
  font-size: 12px;
  font-weight: 600;
  text-align: right;
  font-variant-numeric: tabular-nums;
}

.tag-row {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.risk-level,
.risk-tag {
  display: inline-flex;
  align-items: center;
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 500;
  line-height: 1.4;
}

.tone-ok {
  background: #ecfdf5;
  color: var(--score-high);
}

.tone-warn {
  background: #fffbeb;
  color: var(--score-mid);
}

.tone-bad {
  background: #fef2f2;
  color: var(--score-low);
}

.ocean-card__actions {
  margin-top: auto;
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  padding-top: 4px;
}

.btn-icon {
  margin-right: 4px;
}

.pager {
  display: flex;
  justify-content: flex-end;
  margin-top: 16px;
}

.score-cell {
  font-weight: 700;
  font-variant-numeric: tabular-nums;
}

.dim-mini {
  font-size: 12px;
  color: var(--ink-muted);
  font-variant-numeric: tabular-nums;
}

.rec-table {
  width: 100%;
}

.drawer-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  width: 100%;
  padding-right: 8px;
}

.drawer-kicker {
  font-size: 12px;
  font-weight: 600;
  color: var(--primary);
  letter-spacing: 0.02em;
}

.drawer-title {
  margin: 4px 0 0;
  font-size: 16px;
  font-weight: 600;
  line-height: 1.4;
  color: var(--ink);
}

.drawer-sub {
  margin-top: 6px;
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: var(--ink-muted);
}

.drawer-body {
  padding: 0 4px 8px;
}

.ai-block {
  padding: 16px 0;
  border-bottom: 1px solid var(--hairline);
}

.ai-block:last-child {
  border-bottom: none;
}

.ai-block h3 {
  margin: 0 0 8px;
  font-size: 14px;
  font-weight: 600;
  color: var(--ink);
}

.ai-block p,
.ai-block li {
  margin: 0;
  font-size: 13px;
  line-height: 1.65;
  color: #374151;
}

.ai-block ul {
  margin: 0;
  padding-left: 18px;
}

.ai-block li + li {
  margin-top: 6px;
}

.drawer-footer {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  width: 100%;
}

@media (max-width: 1200px) {
  .ocean-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 768px) {
  .ocean-grid {
    grid-template-columns: 1fr;
  }

  .filter-item,
  .filter-item--sort {
    width: 100%;
  }
}

@media (prefers-reduced-motion: reduce) {
  .ocean-card {
    transition: none;
  }

  .ocean-card:hover {
    transform: none;
  }
}
</style>

<style>
/* 抽屉背景浅蓝紫渐变：与数据区白卡区分（克制，非整页渐变） */
.ai-drawer.el-drawer {
  background: linear-gradient(180deg, #eef2ff 0%, #f8fafc 28%, #ffffff 100%);
}

.ai-drawer .el-drawer__header {
  margin-bottom: 8px;
  padding-bottom: 12px;
  border-bottom: 1px solid #e5e7eb;
}

.ai-drawer .el-drawer__body {
  padding-top: 0;
}

.ai-drawer .el-drawer__footer {
  border-top: 1px solid #e5e7eb;
  background: rgba(255, 255, 255, 0.92);
}
</style>
