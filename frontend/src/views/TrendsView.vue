<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import * as echarts from 'echarts/core'
import { BarChart, LineChart } from 'echarts/charts'
import {
  GridComponent,
  LegendComponent,
  TooltipComponent,
} from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import {
  DataAnalysis,
  Lightning,
  Refresh,
  Right,
  StarFilled,
  WarningFilled,
} from '@element-plus/icons-vue'
import { getCategoryTree, syncCategories, syncProducts } from '@/api/products'
import {
  calculateCategoryTrend,
  generateTrendAIReport,
  getGrowthCategories,
  getPriceDistribution,
} from '@/api/trends'
import type { PlatformId } from '@/types/products'
import type {
  CompetitionLevel,
  GrowthCategoryItem,
  PriceDistributionData,
  TrendAIReportData,
} from '@/types/trends'

echarts.use([
  BarChart,
  LineChart,
  GridComponent,
  LegendComponent,
  TooltipComponent,
  CanvasRenderer,
])

type LoadState = 'idle' | 'loading' | 'success' | 'empty' | 'error'

const PLATFORM_OPTIONS: { label: string; value: PlatformId }[] = [
  { label: 'Amazon', value: 'amazon' },
  { label: 'Shopee', value: 'shopee' },
  { label: 'Mock', value: 'mock' },
  { label: 'DummyJSON', value: 'dummyjson' },
  { label: 'FakeStore', value: 'fakestore' },
]

const DAYS_OPTIONS = [
  { label: '近 30 天', value: 30 },
  { label: '近 90 天', value: 90 },
  { label: '近 12 个月', value: 365 },
]

const router = useRouter()
/** 与当前 .env DATA_SOURCE=dummyjson 对齐；可在筛选中切换 */
const platformId = ref<PlatformId>('dummyjson')
const days = ref(365)
const bootstrapping = ref(false)

const listState = ref<LoadState>('idle')
const listError = ref('')
const listRequestId = ref(0)
const categories = ref<GrowthCategoryItem[]>([])
const selectedId = ref<string | null>(null)

const chartState = ref<LoadState>('idle')
const chartError = ref('')
const chartRequestId = ref(0)
const distribution = ref<PriceDistributionData | null>(null)

const aiState = ref<LoadState>('idle')
const aiError = ref('')
const aiRequestId = ref(0)
const aiReport = ref<TrendAIReportData | null>(null)
const aiVisible = ref(false)

const distChartRef = ref<HTMLDivElement | null>(null)
const curveChartRef = ref<HTMLDivElement | null>(null)
let distChart: echarts.ECharts | null = null
let curveChart: echarts.ECharts | null = null

const selectedCategory = computed(
  () => categories.value.find((item) => item.category_id === selectedId.value) || null,
)

const sampleSizes = computed(() =>
  categories.value.map((item) => item.sample_size ?? 0),
)

const updatedAtText = computed(() => {
  const times = categories.value
    .map((item) => item.computed_at)
    .filter(Boolean)
    .sort()
  const latest = times[times.length - 1]
  return latest ? formatDateTime(latest) : '—'
})

function toNumber(value: string | number | null | undefined): number | null {
  if (value == null || value === '') return null
  const num = typeof value === 'number' ? value : Number(value)
  return Number.isFinite(num) ? num : null
}

function formatPrice(value: string | number | null | undefined): string {
  const num = toNumber(value)
  if (num == null) return '—'
  return `$${num.toFixed(2)}`
}

function formatPercent(value: string | number | null | undefined): string {
  const num = toNumber(value)
  if (num == null) return '—'
  return `${(Math.abs(num) * 100).toFixed(1)}%`
}

function formatDateTime(value: string): string {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  const mm = String(date.getMonth() + 1).padStart(2, '0')
  const dd = String(date.getDate()).padStart(2, '0')
  const hh = String(date.getHours()).padStart(2, '0')
  const mi = String(date.getMinutes()).padStart(2, '0')
  return `${mm}-${dd} ${hh}:${mi}`
}

function formatMonth(value: string): string {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return `${date.getMonth() + 1}月`
}

function growthTone(value: string | number | null | undefined): 'up' | 'down' | 'flat' {
  const num = toNumber(value)
  if (num == null || Math.abs(num) < 0.005) return 'flat'
  return num > 0 ? 'up' : 'down'
}

function competitionLevel(sampleSize: number | null): CompetitionLevel {
  const sizes = sampleSizes.value.filter((size) => size > 0).sort((a, b) => a - b)
  const sample = sampleSize ?? 0
  if (sizes.length === 0 || sample <= 0) return 'low'
  const p33 = sizes[Math.floor((sizes.length - 1) * 0.33)] ?? 0
  const p66 = sizes[Math.floor((sizes.length - 1) * 0.66)] ?? 0
  if (sample >= p66) return 'high'
  if (sample >= p33) return 'mid'
  return 'low'
}

function competitionLabel(level: CompetitionLevel): string {
  if (level === 'high') return '高'
  if (level === 'mid') return '中'
  return '低'
}

function seasonalityTag(hint: string | null | undefined): string {
  if (!hint) return '待分析'
  if (hint.includes('旺季')) {
    const match = hint.match(/(\d{1,2}月|Q[1-4])/)
    return match ? `${match[1]}旺季` : '季节旺季'
  }
  if (hint.includes('轻度季节性')) return '轻度季节'
  if (hint.includes('稳定') || hint.includes('暂未发现')) return '全年平稳'
  if (hint.includes('不足')) return '样本不足'
  return hint.length > 8 ? `${hint.slice(0, 8)}…` : hint
}

async function loadCategories() {
  const requestId = ++listRequestId.value
  listState.value = 'loading'
  listError.value = ''
  try {
    const data = await getGrowthCategories({
      platform_id: platformId.value,
      days: days.value,
      limit: 50,
    })
    if (requestId !== listRequestId.value) return
    categories.value = data.items
    if (data.items.length === 0) {
      selectedId.value = null
      listState.value = 'empty'
      resetDetail()
      return
    }
    listState.value = 'success'
    const keep = data.items.find((item) => item.category_id === selectedId.value)
    selectedId.value = keep?.category_id ?? data.items[0].category_id
    await loadDetail(selectedId.value)
  } catch (err) {
    if (requestId !== listRequestId.value) return
    listState.value = 'error'
    listError.value = err instanceof Error ? err.message : '品类趋势加载失败'
    categories.value = []
    resetDetail()
  }
}

function resetDetail() {
  chartRequestId.value += 1
  aiRequestId.value += 1
  distribution.value = null
  aiReport.value = null
  aiVisible.value = false
  chartState.value = 'idle'
  aiState.value = 'idle'
  chartError.value = ''
  aiError.value = ''
  disposeCharts()
}

async function loadDetail(categoryId: string) {
  await Promise.all([loadCharts(categoryId), loadAIReport(categoryId)])
}

async function loadCharts(categoryId: string) {
  const requestId = ++chartRequestId.value
  chartState.value = 'loading'
  chartError.value = ''
  distribution.value = null
  disposeCharts()
  try {
    const data = await getPriceDistribution(categoryId)
    if (requestId !== chartRequestId.value) return
    distribution.value = data
    chartState.value = 'success'
    await nextTick()
    renderCharts()
  } catch (err) {
    if (requestId !== chartRequestId.value) return
    chartState.value = 'error'
    chartError.value = err instanceof Error ? err.message : '图表加载失败'
  }
}

async function loadAIReport(categoryId: string) {
  const requestId = ++aiRequestId.value
  aiState.value = 'loading'
  aiError.value = ''
  aiReport.value = null
  aiVisible.value = false
  try {
    const data = await generateTrendAIReport(categoryId)
    if (requestId !== aiRequestId.value) return
    aiReport.value = data
    aiState.value = 'success'
    await nextTick()
    // 触发淡入动画
    requestAnimationFrame(() => {
      if (requestId === aiRequestId.value) aiVisible.value = true
    })
  } catch (err) {
    if (requestId !== aiRequestId.value) return
    aiState.value = 'error'
    aiError.value = err instanceof Error ? err.message : 'AI 解读生成失败'
  }
}

function selectCategory(row: GrowthCategoryItem) {
  if (selectedId.value === row.category_id) return
  selectedId.value = row.category_id
  void loadDetail(row.category_id)
}

function renderCharts() {
  const data = distribution.value
  if (!data) return

  if (distChartRef.value) {
    distChart = echarts.init(distChartRef.value)
    const labels = data.buckets.map((bucket) => bucket.label.replace(/^[A-Z]{3}\s/, ''))
    const values = data.buckets.map((bucket) => bucket.product_count)
    const maxIndex = values.indexOf(Math.max(...values, 0))
    distChart.setOption({
      color: ['#4F46E5'],
      grid: { left: 40, right: 16, top: 28, bottom: 36 },
      tooltip: {
        trigger: 'axis',
        axisPointer: { type: 'shadow' },
        formatter: (params: unknown) => {
          const item = Array.isArray(params) ? params[0] : null
          if (!item || typeof item !== 'object') return ''
          const point = item as { name?: string; value?: number }
          return `${point.name || ''}<br/>商品数 <b>${point.value ?? 0}</b>`
        },
      },
      xAxis: {
        type: 'category',
        data: labels,
        axisLabel: { color: '#6B7280', fontSize: 11, interval: 0 },
        axisLine: { lineStyle: { color: '#E5E7EB' } },
        axisTick: { show: false },
      },
      yAxis: {
        type: 'value',
        minInterval: 1,
        splitLine: { lineStyle: { color: '#F3F4F6' } },
        axisLabel: { color: '#9CA3AF', fontSize: 11 },
      },
      series: [
        {
          type: 'bar',
          data: values.map((value, index) => ({
            value,
            itemStyle: {
              color: index === maxIndex ? '#0EA5E9' : '#4F46E5',
              borderRadius: [4, 4, 0, 0],
            },
          })),
          barMaxWidth: 36,
        },
      ],
    })
  }

  if (curveChartRef.value) {
    curveChart = echarts.init(curveChartRef.value)
    const months = data.price_curve.map((point) => formatMonth(point.period_month))
    const prices = data.price_curve.map((point) => toNumber(point.average_price) ?? 0)
    curveChart.setOption({
      color: ['#4F46E5'],
      grid: { left: 48, right: 16, top: 28, bottom: 36 },
      tooltip: {
        trigger: 'axis',
        formatter: (params: unknown) => {
          const item = Array.isArray(params) ? params[0] : null
          if (!item || typeof item !== 'object') return ''
          const point = item as { name?: string; value?: number }
          return `${point.name || ''}<br/>均价 <b>$${(point.value ?? 0).toFixed(2)}</b>`
        },
      },
      xAxis: {
        type: 'category',
        data: months,
        boundaryGap: false,
        axisLabel: { color: '#6B7280', fontSize: 11 },
        axisLine: { lineStyle: { color: '#E5E7EB' } },
        axisTick: { show: false },
      },
      yAxis: {
        type: 'value',
        splitLine: { lineStyle: { color: '#F3F4F6' } },
        axisLabel: {
          color: '#9CA3AF',
          fontSize: 11,
          formatter: (value: number) => `$${value}`,
        },
      },
      series: [
        {
          type: 'line',
          name: '均价',
          data: prices,
          smooth: true,
          showSymbol: prices.length <= 12,
          symbolSize: 6,
          lineStyle: { width: 2.5, color: '#4F46E5' },
          areaStyle: {
            color: 'rgba(79, 70, 229, 0.12)',
          },
        },
      ],
    })
  }
}

function disposeCharts() {
  distChart?.dispose()
  curveChart?.dispose()
  distChart = null
  curveChart = null
}

function onResize() {
  distChart?.resize()
  curveChart?.resize()
}

function goSelections() {
  void router.push('/selections')
}

async function refreshAll() {
  ElMessage.success('正在刷新趋势数据')
  await loadCategories()
}

/** 一键：同步品类/商品 → 触发各品类趋势计算 → 刷新列表 */
async function bootstrapTrends() {
  if (bootstrapping.value) return
  bootstrapping.value = true
  try {
    ElMessage.info('正在同步品类…')
    await syncCategories(platformId.value)
    const tree = await getCategoryTree(platformId.value)
    const flat: { id: string; name: string }[] = []
    const walk = (nodes: typeof tree.items) => {
      for (const node of nodes) {
        flat.push({ id: node.id, name: node.name })
        if (node.children?.length) walk(node.children)
      }
    }
    walk(tree.items || [])
    if (flat.length === 0) {
      ElMessage.warning('未拉到品类，请检查数据源配置')
      return
    }
    ElMessage.info(`正在同步 ${flat.length} 个品类的商品…`)
    for (const category of flat) {
      await syncProducts({
        platform_id: platformId.value,
        category_id: category.id,
      })
    }
    ElMessage.info('正在计算品类趋势…')
    let ok = 0
    for (const category of flat) {
      try {
        await calculateCategoryTrend({ category_id: category.id })
        ok += 1
      } catch {
        // 无价格样本的品类跳过，不中断整批
      }
    }
    ElMessage.success(`已完成：同步商品并计算 ${ok} 个品类趋势`)
    await loadCategories()
  } catch (err) {
    ElMessage.error(err instanceof Error ? err.message : '同步或计算失败')
  } finally {
    bootstrapping.value = false
  }
}

watch([platformId, days], () => {
  void loadCategories()
})

onMounted(() => {
  window.addEventListener('resize', onResize)
  void loadCategories()
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', onResize)
  disposeCharts()
})
</script>

<template>
  <div class="trends-page">
    <div class="filter-bar page-card">
      <div class="filter-controls">
        <el-select v-model="platformId" class="filter-select">
          <el-option
            v-for="opt in PLATFORM_OPTIONS"
            :key="opt.value"
            :label="opt.label"
            :value="opt.value"
          />
        </el-select>
        <el-select v-model="days" class="filter-select">
          <el-option
            v-for="opt in DAYS_OPTIONS"
            :key="opt.value"
            :label="opt.label"
            :value="opt.value"
          />
        </el-select>
        <span class="updated-at">更新于 {{ updatedAtText }}</span>
      </div>
      <div class="filter-actions">
        <el-button :icon="Refresh" @click="refreshAll">刷新</el-button>
        <el-button type="primary" @click="goSelections">
          查看相关推荐
          <el-icon class="btn-arrow"><Right /></el-icon>
        </el-button>
      </div>
    </div>

    <div class="workspace">
      <section class="list-panel page-card">
        <div class="panel-head">
          <div>
            <h2 class="panel-title">品类趋势</h2>
            <p class="panel-meta">共 {{ categories.length }} 个品类</p>
          </div>
        </div>

        <div v-if="listState === 'loading'" class="panel-body">
          <el-skeleton animated :rows="8" />
        </div>

        <div v-else-if="listState === 'error'" class="state-block">
          <el-icon class="state-icon danger"><WarningFilled /></el-icon>
          <p class="state-title">趋势加载失败</p>
          <p class="state-desc">{{ listError }}</p>
          <el-button type="primary" size="small" @click="loadCategories">重试</el-button>
        </div>

        <div v-else-if="listState === 'empty'" class="state-block">
          <el-icon class="state-icon"><DataAnalysis /></el-icon>
          <p class="state-title">暂无品类趋势</p>
          <p class="state-desc">
            当前平台还没有趋势结果。可一键同步商品并触发计算，或确认筛选平台与数据源一致。
          </p>
          <div class="state-actions">
            <el-button
              type="primary"
              size="small"
              :loading="bootstrapping"
              @click="bootstrapTrends"
            >
              {{ bootstrapping ? '同步计算中…' : '同步商品并计算趋势' }}
            </el-button>
            <el-button size="small" :disabled="bootstrapping" @click="loadCategories">
              重新加载
            </el-button>
          </div>
        </div>

        <div v-else class="table-wrap">
          <el-table
            :data="categories"
            row-key="category_id"
            height="100%"
            highlight-current-row
            :current-row-key="selectedId || undefined"
            @row-click="selectCategory"
          >
            <el-table-column prop="category_name" label="品类" min-width="110">
              <template #default="{ row }">
                <span class="cat-name">{{ row.category_name }}</span>
              </template>
            </el-table-column>
            <el-table-column label="商品数" width="72" align="right">
              <template #default="{ row }">
                {{ row.sample_size ?? '—' }}
              </template>
            </el-table-column>
            <el-table-column label="平均价" width="84" align="right">
              <template #default="{ row }">
                <span class="price-cell">{{ formatPrice(row.avg_price) }}</span>
              </template>
            </el-table-column>
            <el-table-column label="增长率" width="96" align="right">
              <template #default="{ row }">
                <span
                  class="growth-cell"
                  :class="growthTone(row.growth_rate)"
                >
                  <template v-if="growthTone(row.growth_rate) === 'up'">▲</template>
                  <template v-else-if="growthTone(row.growth_rate) === 'down'">▼</template>
                  {{ formatPercent(row.growth_rate) }}
                </span>
              </template>
            </el-table-column>
            <el-table-column label="竞争度" width="72" align="center">
              <template #default="{ row }">
                <span
                  class="level-tag"
                  :class="competitionLevel(row.sample_size)"
                >
                  {{ competitionLabel(competitionLevel(row.sample_size)) }}
                </span>
              </template>
            </el-table-column>
            <el-table-column label="季节性" min-width="88">
              <template #default="{ row }">
                <span class="season-tag">{{ seasonalityTag(row.seasonality_hint) }}</span>
              </template>
            </el-table-column>
          </el-table>
        </div>
      </section>

      <section class="detail-panel">
        <div v-if="!selectedCategory" class="page-card detail-empty">
          <el-icon class="state-icon"><DataAnalysis /></el-icon>
          <p class="state-title">选择左侧品类</p>
          <p class="state-desc">查看价格分布、变化曲线与 AI 趋势解读。</p>
        </div>

        <template v-else>
          <div class="page-card chart-card">
            <div class="chart-head">
              <div>
                <h3 class="chart-title">价格分布</h3>
                <p class="chart-sub">
                  {{ selectedCategory.category_name }} · 样本
                  {{ distribution?.sample_size ?? selectedCategory.sample_size ?? '—' }}
                </p>
              </div>
            </div>
            <div v-if="chartState === 'loading'" class="chart-skeleton">
              <el-skeleton animated :rows="5" />
            </div>
            <div v-else-if="chartState === 'error'" class="state-block compact">
              <p class="state-title">价格分布加载失败</p>
              <p class="state-desc">{{ chartError }}</p>
              <el-button
                type="primary"
                size="small"
                @click="loadCharts(selectedCategory.category_id)"
              >
                重试
              </el-button>
            </div>
            <div
              v-else-if="!distribution || distribution.buckets.length === 0"
              class="state-block compact"
            >
              <p class="state-title">暂无价格分布</p>
              <p class="state-desc">该品类缺少有效价格样本。</p>
            </div>
            <div v-else ref="distChartRef" class="chart-box" />
          </div>

          <div class="page-card chart-card">
            <div class="chart-head">
              <div>
                <h3 class="chart-title">价格变化</h3>
                <p class="chart-sub">月度均价走势</p>
              </div>
              <span
                class="growth-badge"
                :class="growthTone(selectedCategory.growth_rate)"
              >
                当前
                <template v-if="growthTone(selectedCategory.growth_rate) === 'up'">▲</template>
                <template v-else-if="growthTone(selectedCategory.growth_rate) === 'down'">▼</template>
                {{ formatPercent(selectedCategory.growth_rate) }}
              </span>
            </div>
            <div v-if="chartState === 'loading'" class="chart-skeleton">
              <el-skeleton animated :rows="4" />
            </div>
            <div
              v-else-if="distribution && distribution.price_curve.length > 0"
              ref="curveChartRef"
              class="chart-box"
            />
            <div v-else-if="chartState === 'success'" class="state-block compact">
              <p class="state-title">暂无价格曲线</p>
              <p class="state-desc">尚无足够的月度趋势点，可先触发趋势计算。</p>
            </div>
          </div>

          <div class="ai-card">
            <div class="ai-head">
              <div class="ai-brand">
                <span class="ai-mark">AI</span>
                <div>
                  <h3 class="ai-title">AI 趋势解读</h3>
                  <p class="ai-sub">{{ selectedCategory.category_name }}</p>
                </div>
              </div>
              <el-button
                text
                type="primary"
                :loading="aiState === 'loading'"
                @click="loadAIReport(selectedCategory.category_id)"
              >
                {{ aiState === 'loading' ? '生成中…' : '重新生成' }}
              </el-button>
            </div>

            <div v-if="aiState === 'loading'" class="ai-loading">
              <el-skeleton animated :rows="4" />
              <p class="ai-loading-text">正在生成解读报告…</p>
            </div>

            <div v-else-if="aiState === 'error'" class="state-block compact">
              <el-icon class="state-icon danger"><WarningFilled /></el-icon>
              <p class="state-title">解读生成失败</p>
              <p class="state-desc">{{ aiError }}</p>
              <el-button
                type="primary"
                size="small"
                @click="loadAIReport(selectedCategory.category_id)"
              >
                重新生成
              </el-button>
            </div>

            <div
              v-else-if="aiReport"
              class="ai-body"
              :class="{ visible: aiVisible }"
            >
              <article class="ai-block">
                <div class="ai-block-head">
                  <el-icon class="ai-icon summary"><DataAnalysis /></el-icon>
                  <h4>摘要</h4>
                </div>
                <p>{{ aiReport.summary }}</p>
              </article>

              <article class="ai-block">
                <div class="ai-block-head">
                  <el-icon class="ai-icon highlight"><StarFilled /></el-icon>
                  <h4>亮点</h4>
                </div>
                <ul>
                  <li v-for="(item, index) in aiReport.highlights" :key="`h-${index}`">
                    {{ item }}
                  </li>
                </ul>
              </article>

              <article class="ai-block">
                <div class="ai-block-head">
                  <el-icon class="ai-icon recommend"><Lightning /></el-icon>
                  <h4>推荐</h4>
                </div>
                <ul>
                  <li
                    v-for="(item, index) in aiReport.recommendations"
                    :key="`r-${index}`"
                  >
                    {{ item }}
                  </li>
                </ul>
              </article>

              <article class="ai-block">
                <div class="ai-block-head">
                  <el-icon class="ai-icon risk"><WarningFilled /></el-icon>
                  <h4>风险</h4>
                </div>
                <ul>
                  <li v-for="(item, index) in aiReport.risks" :key="`k-${index}`">
                    {{ item }}
                  </li>
                </ul>
              </article>

              <footer class="ai-footer">
                生成于 {{ formatDateTime(aiReport.generated_at) }}
                · 基于 {{ distribution?.sample_size ?? selectedCategory.sample_size ?? '—' }} 个商品样本
                <span class="season-chip">
                  季节性：{{ seasonalityTag(selectedCategory.seasonality_hint) }}
                </span>
              </footer>
            </div>
          </div>
        </template>
      </section>
    </div>
  </div>
</template>

<style scoped>
.trends-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
  min-height: calc(100vh - var(--header-height) - 48px);
}

.page-card {
  background: var(--color-surface);
  border: 1px solid var(--color-hairline);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-card);
}

.filter-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 12px 16px;
}

.filter-controls,
.filter-actions {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.filter-select {
  width: 140px;
}

.updated-at {
  font-size: 12px;
  color: var(--color-ink-muted);
}

.btn-arrow {
  margin-left: 4px;
}

.workspace {
  display: grid;
  grid-template-columns: 40% 1fr;
  gap: 16px;
  min-height: 0;
  flex: 1;
}

.list-panel {
  display: flex;
  flex-direction: column;
  min-height: 640px;
  overflow: hidden;
}

.panel-head,
.chart-head,
.ai-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  padding: 16px 16px 12px;
}

.panel-title,
.chart-title,
.ai-title {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  color: var(--color-ink);
}

.panel-meta,
.chart-sub,
.ai-sub {
  margin: 4px 0 0;
  font-size: 12px;
  color: var(--color-ink-muted);
}

.panel-body {
  padding: 8px 16px 16px;
}

.table-wrap {
  flex: 1;
  min-height: 0;
  padding: 0 8px 8px;
  overflow-x: auto;
  -webkit-overflow-scrolling: touch;
}

.table-wrap :deep(.el-table) {
  min-width: 520px;
  --el-table-header-bg-color: var(--color-surface-sunken);
  --el-table-row-hover-bg-color: var(--color-primary-subtle);
  --el-table-current-row-bg-color: #eef2ff;
  font-size: 13px;
}

.table-wrap :deep(.el-table__row) {
  cursor: pointer;
}

.table-wrap :deep(.el-table__body tr.current-row > td.el-table__cell) {
  background: #eef2ff !important;
}

.table-wrap :deep(.el-table__body tr.current-row > td.el-table__cell:first-child) {
  box-shadow: inset 3px 0 0 var(--color-primary);
}

.cat-name {
  font-weight: 600;
  color: var(--color-ink);
}

.price-cell {
  font-weight: 600;
  color: var(--color-primary);
}

.growth-cell {
  font-weight: 700;
  font-variant-numeric: tabular-nums;
}

.growth-cell.up,
.growth-badge.up {
  color: var(--color-success);
}

.growth-cell.down,
.growth-badge.down {
  color: var(--color-danger);
}

.growth-cell.flat,
.growth-badge.flat {
  color: var(--color-ink-muted);
}

.level-tag,
.season-tag,
.season-chip {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 28px;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 500;
  line-height: 1.3;
}

.level-tag.high {
  background: var(--color-success);
  background: #ecfdf5;
  color: #059669;
}

.level-tag.mid {
  background: #fffbeb;
  color: #d97706;
}

.level-tag.low {
  background: #eff6ff;
  color: #2563eb;
}

.season-tag {
  background: var(--color-surface-sunken);
  color: var(--color-ink-secondary);
}

.detail-panel {
  display: flex;
  flex-direction: column;
  gap: 16px;
  min-width: 0;
}

.detail-empty,
.state-block {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 40px 24px;
  text-align: center;
}

.state-block.compact {
  padding: 28px 16px;
  min-height: 180px;
}

.state-icon {
  font-size: 28px;
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
  margin: 0;
  font-size: 12px;
  color: var(--color-ink-muted);
  max-width: 320px;
}

.state-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  justify-content: center;
  margin-top: 4px;
}

.chart-card {
  padding-bottom: 8px;
}

.chart-box {
  height: 220px;
  padding: 0 8px 8px;
}

.chart-skeleton {
  padding: 8px 16px 16px;
}

.growth-badge {
  font-size: 12px;
  font-weight: 700;
  padding: 4px 8px;
  border-radius: 4px;
  background: var(--color-surface-sunken);
}

.ai-card {
  border-radius: var(--radius-lg);
  border: 1px solid #c7d2fe;
  background: linear-gradient(135deg, #eef2ff 0%, #eff6ff 48%, #f5f3ff 100%);
  box-shadow: var(--shadow-card);
  padding-bottom: 8px;
  overflow: hidden;
}

.ai-brand {
  display: flex;
  align-items: center;
  gap: 12px;
}

.ai-mark {
  width: 36px;
  height: 36px;
  border-radius: 8px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: var(--color-primary);
  color: #fff;
  font-size: 12px;
  font-weight: 700;
}

.ai-loading,
.ai-body {
  padding: 0 16px 16px;
}

.ai-loading-text {
  margin: 8px 0 0;
  font-size: 12px;
  color: var(--color-ink-muted);
}

.ai-body {
  opacity: 0;
  transform: translateY(6px);
  transition: opacity 180ms ease, transform 180ms ease;
}

.ai-body.visible {
  opacity: 1;
  transform: translateY(0);
}

.ai-block {
  margin-bottom: 14px;
  padding: 12px 14px;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.72);
  border: 1px solid rgba(199, 210, 254, 0.7);
}

.ai-block-head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.ai-block-head h4 {
  margin: 0;
  font-size: 13px;
  font-weight: 600;
  color: var(--color-ink);
}

.ai-block p,
.ai-block li {
  margin: 0;
  font-size: 13px;
  color: var(--color-ink-secondary);
  line-height: 1.6;
}

.ai-block ul {
  margin: 0;
  padding-left: 18px;
}

.ai-icon {
  font-size: 16px;
}

.ai-icon.summary {
  color: var(--color-primary);
}

.ai-icon.highlight {
  color: #d97706;
}

.ai-icon.recommend {
  color: #059669;
}

.ai-icon.risk {
  color: #dc2626;
}

.ai-footer {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  margin-top: 4px;
  font-size: 12px;
  color: var(--color-ink-muted);
}

.season-chip {
  background: #fffbeb;
  color: #d97706;
}

@media (prefers-reduced-motion: reduce) {
  .ai-body {
    transition: none;
    transform: none;
  }
}

@media (max-width: 1100px) {
  .workspace {
    grid-template-columns: 1fr;
  }

  .list-panel {
    min-height: 420px;
  }
}
</style>
