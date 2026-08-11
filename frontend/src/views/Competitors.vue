<script setup lang="ts">
import {
  computed,
  nextTick,
  onBeforeUnmount,
  onMounted,
  ref,
  watch,
} from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Plus,
  Refresh,
  WarningFilled,
  Close,
  StarFilled,
} from '@element-plus/icons-vue'
import * as echarts from 'echarts/core'
import { LineChart } from 'echarts/charts'
import {
  GridComponent,
  LegendComponent,
  MarkLineComponent,
  TitleComponent,
  TooltipComponent,
} from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import { getProducts } from '@/api/products'
import {
  batchUpdateCompetitors,
  discoverCompetitors,
  getCompetitorBindings,
  getCompetitorDetail,
} from '@/api/competitors'
import { getAlerts, markAlertRead } from '@/api/alerts'
import { useAuthStore } from '@/stores/auth'
import type { ProductListItem } from '@/types/products'
import type { CompetitorBinding, CompetitorSnapshot } from '@/types/competitors'
import type { AlertItem, AlertSeverityLabel } from '@/types/alerts'
import { severityToLabel } from '@/types/alerts'

echarts.use([
  LineChart,
  GridComponent,
  TooltipComponent,
  LegendComponent,
  TitleComponent,
  MarkLineComponent,
  CanvasRenderer,
])

type LoadState = 'idle' | 'loading' | 'success' | 'empty' | 'error'

const CHART_COLORS = ['#4F46E5', '#0EA5E9', '#059669', '#F59E0B', '#DC2626']

const auth = useAuthStore()

const canWrite = computed(() => {
  const role = auth.user?.role
  return role === 'operator' || role === 'ops_lead'
})

const canMarkRead = computed(() => canWrite.value)

/** —— 商品选择 —— */
const products = ref<ProductListItem[]>([])
const selectedProductId = ref('')
const productsLoading = ref(false)

/** —— 竞品表 —— */
const tableState = ref<LoadState>('idle')
const tableError = ref('')
const bindings = ref<CompetitorBinding[]>([])
const selectedBindingId = ref<string | null>(null)
const compareIds = ref<string[]>([])

/** —— 告警 —— */
const alerts = ref<AlertItem[]>([])
const bannerDismissed = ref(false)
const markingId = ref<string | null>(null)

/** —— 图表 —— */
const chartRef = ref<HTMLDivElement | null>(null)
let chart: echarts.ECharts | null = null
const chartLoading = ref(false)
const snapshotMap = ref<Record<string, CompetitorSnapshot[]>>({})

/** —— 操作 —— */
const refreshing = ref(false)
const discovering = ref(false)

const selectedProduct = computed(() =>
  products.value.find((p) => p.id === selectedProductId.value) || null,
)

const unreadAlerts = computed(() => alerts.value.filter((a) => !a.is_read))

const bannerAlert = computed(() => {
  if (bannerDismissed.value) return null
  const list = [...unreadAlerts.value].sort((a, b) => {
    const rank = (s: string) =>
      s === 'critical' ? 0 : s === 'warning' ? 1 : 2
    const dr = rank(a.severity) - rank(b.severity)
    if (dr !== 0) return dr
    return b.triggered_at.localeCompare(a.triggered_at)
  })
  return list[0] || null
})

const alertByBinding = computed(() => {
  const map = new Map<string, AlertItem>()
  for (const a of unreadAlerts.value) {
    if (!a.competitor_binding_id) continue
    const prev = map.get(a.competitor_binding_id)
    if (!prev || severityRank(a.severity) < severityRank(prev.severity)) {
      map.set(a.competitor_binding_id, a)
    }
  }
  return map
})

function severityRank(s: string): number {
  return s === 'critical' ? 0 : s === 'warning' ? 1 : 2
}

function toNumber(v: string | number | null | undefined): number | null {
  if (v === null || v === undefined || v === '') return null
  const n = Number(v)
  return Number.isFinite(n) ? n : null
}

function formatPrice(v: string | number | null | undefined, currency = 'USD'): string {
  const n = toNumber(v)
  if (n === null) return '—'
  const symbol = currency === 'USD' || !currency ? '$' : `${currency} `
  return `${symbol}${n.toFixed(2)}`
}

function formatPct(v: string | number | null | undefined): number | null {
  const n = toNumber(v)
  if (n === null) return null
  return n * 100
}

function formatRelative(iso: string | null | undefined): string {
  if (!iso) return '—'
  const t = new Date(iso).getTime()
  if (Number.isNaN(t)) return '—'
  const diff = Date.now() - t
  const mins = Math.floor(diff / 60000)
  if (mins < 1) return '刚刚'
  if (mins < 60) return `${mins} 分钟前`
  const hours = Math.floor(mins / 60)
  if (hours < 24) return `${hours} 小时前`
  const days = Math.floor(hours / 24)
  return `${days} 天前`
}

function platformLabel(platform: string | undefined): string {
  if (!platform) return '—'
  const map: Record<string, string> = {
    amazon: 'Amazon',
    shopee: 'Shopee',
    dummyjson: 'DummyJSON',
    fakestore: 'FakeStore',
    mock: 'Mock',
  }
  return map[platform] || platform
}

function rowSeverity(row: CompetitorBinding): AlertSeverityLabel | null {
  const alert = alertByBinding.value.get(row.id)
  if (alert) return severityToLabel(alert.severity)
  const pct = formatPct(row.latest_snapshot?.price_change_pct)
  if (pct === null) return null
  if (pct <= -10) return 'high'
  if (pct <= -5) return 'medium'
  return 'low'
}

function severityText(level: AlertSeverityLabel | null): string {
  if (level === 'high') return '高风险'
  if (level === 'medium') return '中风险'
  if (level === 'low') return '低风险'
  return '—'
}

async function loadProducts() {
  productsLoading.value = true
  try {
    const page = await getProducts({ page: 1, page_size: 100 })
    products.value = page.items
    if (!selectedProductId.value && page.items.length > 0) {
      selectedProductId.value = page.items[0].id
    }
  } catch (err) {
    ElMessage.error(err instanceof Error ? err.message : '加载商品失败')
  } finally {
    productsLoading.value = false
  }
}

async function loadBindings() {
  if (!selectedProductId.value) {
    bindings.value = []
    tableState.value = 'empty'
    return
  }
  tableState.value = 'loading'
  tableError.value = ''
  try {
    const page = await getCompetitorBindings({
      own_product_id: selectedProductId.value,
      active_only: true,
      page: 1,
      page_size: 100,
    })
    bindings.value = page.items
    tableState.value = page.items.length ? 'success' : 'empty'
    if (page.items.length) {
      const firstId = page.items[0].id
      if (
        !selectedBindingId.value ||
        !page.items.some((b) => b.id === selectedBindingId.value)
      ) {
        selectedBindingId.value = firstId
      }
      if (
        compareIds.value.length === 0 ||
        !compareIds.value.every((id) => page.items.some((b) => b.id === id))
      ) {
        compareIds.value = page.items.slice(0, 4).map((b) => b.id)
      }
    } else {
      selectedBindingId.value = null
      compareIds.value = []
      snapshotMap.value = {}
      renderChart()
    }
  } catch (err) {
    tableState.value = 'error'
    tableError.value = err instanceof Error ? err.message : '加载竞品失败'
  }
}

async function loadAlerts() {
  try {
    const list = await getAlerts({
      page: 1,
      page_size: 50,
      is_read: false,
      product_id: selectedProductId.value || undefined,
      days: 30,
    })
    alerts.value = list.items.filter((a) => a.type.startsWith('competitor_'))
    bannerDismissed.value = false
  } catch {
    // 列表权限不足时不阻断主表
  }
}

async function loadSnapshotsForCompare() {
  const ids = compareIds.value.slice(0, 5)
  if (!ids.length) {
    snapshotMap.value = {}
    renderChart()
    return
  }
  chartLoading.value = true
  try {
    const entries = await Promise.all(
      ids.map(async (id) => {
        const detail = await getCompetitorDetail(id, 90)
        return [id, detail.snapshots] as const
      }),
    )
    const next: Record<string, CompetitorSnapshot[]> = {}
    for (const [id, snaps] of entries) {
      next[id] = [...snaps].sort((a, b) =>
        a.recorded_at.localeCompare(b.recorded_at),
      )
    }
    snapshotMap.value = next
    await nextTick()
    renderChart()
  } catch (err) {
    ElMessage.error(err instanceof Error ? err.message : '加载价格趋势失败')
  } finally {
    chartLoading.value = false
  }
}

function ensureChart() {
  if (!chartRef.value) return null
  if (!chart) {
    chart = echarts.init(chartRef.value)
  }
  return chart
}

function renderChart() {
  const instance = ensureChart()
  if (!instance) return

  const ids = compareIds.value.filter((id) => snapshotMap.value[id])
  if (!ids.length) {
    instance.clear()
    instance.setOption({
      title: {
        text: '勾选竞品以对比价格趋势',
        left: 'center',
        top: 'middle',
        textStyle: { color: '#9CA3AF', fontSize: 14, fontWeight: 400 },
      },
    })
    return
  }

  const dateSet = new Set<string>()
  for (const id of ids) {
    for (const s of snapshotMap.value[id] || []) {
      dateSet.add(s.recorded_at.slice(0, 10))
    }
  }
  const dates = [...dateSet].sort()

  const ownPrice = toNumber(selectedProduct.value?.price)

  const series = ids.map((id, index) => {
    const binding = bindings.value.find((b) => b.id === id)
    const name = binding?.competitor_product?.title?.slice(0, 24) || `竞品 ${index + 1}`
    const byDay = new Map<string, number>()
    for (const s of snapshotMap.value[id] || []) {
      const day = s.recorded_at.slice(0, 10)
      const price = toNumber(s.price)
      if (price !== null) byDay.set(day, price)
    }
    return {
      name,
      type: 'line' as const,
      smooth: true,
      showSymbol: dates.length <= 14,
      symbolSize: 6,
      lineStyle: { width: 2 },
      data: dates.map((d) => byDay.get(d) ?? null),
      ...(index === 0 && ownPrice !== null
        ? {
            markLine: {
              silent: true,
              symbol: 'none',
              lineStyle: { color: '#9CA3AF', type: 'dashed', width: 1 },
              label: {
                formatter: '自营价',
                color: '#9CA3AF',
                fontSize: 11,
              },
              data: [{ yAxis: ownPrice }],
            },
          }
        : {}),
    }
  })

  instance.setOption(
    {
      color: CHART_COLORS,
      title: { show: false },
      tooltip: {
        trigger: 'axis',
        backgroundColor: '#fff',
        borderColor: '#E5E7EB',
        textStyle: { color: '#111827', fontSize: 12 },
        valueFormatter: (v: unknown) =>
          v == null ? '—' : `$${Number(v).toFixed(2)}`,
      },
      legend: {
        type: 'scroll',
        bottom: 0,
        textStyle: { color: '#6B7280', fontSize: 12 },
      },
      grid: { left: 48, right: 24, top: 24, bottom: 48 },
      xAxis: {
        type: 'category',
        data: dates,
        axisLine: { lineStyle: { color: '#E5E7EB' } },
        axisLabel: { color: '#6B7280', fontSize: 12 },
      },
      yAxis: {
        type: 'value',
        axisLabel: {
          color: '#6B7280',
          fontSize: 12,
          formatter: (v: number) => `$${v}`,
        },
        splitLine: { lineStyle: { color: '#F3F4F6' } },
      },
      series,
    },
    true,
  )
}

function onRowClick(row: CompetitorBinding) {
  selectedBindingId.value = row.id
  if (!compareIds.value.includes(row.id)) {
    compareIds.value = [...compareIds.value.slice(0, 3), row.id]
  }
}

function toggleCompare(bindingId: string, checked: boolean) {
  if (checked) {
    if (compareIds.value.includes(bindingId)) return
    if (compareIds.value.length >= 5) {
      ElMessage.warning('最多对比 5 个竞品')
      return
    }
    compareIds.value = [...compareIds.value, bindingId]
  } else {
    compareIds.value = compareIds.value.filter((id) => id !== bindingId)
  }
}

function rowClassName({ row }: { row: CompetitorBinding }): string {
  const classes: string[] = []
  if (row.id === selectedBindingId.value) classes.push('is-selected')
  if (rowSeverity(row) === 'high') classes.push('row-high')
  return classes.join(' ')
}

async function handleRefresh() {
  if (!canWrite.value) {
    ElMessage.warning('仅运营或运营主管可刷新竞品数据')
    return
  }
  try {
    await ElMessageBox.confirm(
      '将拉取全部活跃竞品最新价格并写入快照，可能触发降价告警。是否继续？',
      '刷新竞品数据',
      {
        confirmButtonText: '确认刷新',
        cancelButtonText: '取消',
        type: 'warning',
      },
    )
  } catch {
    return
  }

  refreshing.value = true
  try {
    const result = await batchUpdateCompetitors()
    ElMessage.success(
      `已更新 ${result.updated}/${result.total} 条，新增告警 ${result.alerts_created}`,
    )
    await Promise.all([loadBindings(), loadAlerts()])
    await loadSnapshotsForCompare()
  } catch (err) {
    // axios 拦截器已提示
  } finally {
    refreshing.value = false
  }
}

async function handleDiscover() {
  if (!selectedProductId.value) {
    ElMessage.warning('请先选择自营商品')
    return
  }
  if (!canWrite.value) {
    ElMessage.warning('仅运营或运营主管可添加竞品')
    return
  }
  discovering.value = true
  try {
    const result = await discoverCompetitors({
      product_id: selectedProductId.value,
      limit: 5,
      use_ai: true,
    })
    ElMessage.success(
      result.created.length
        ? `已自动绑定 ${result.created.length} 个竞品`
        : result.summary || '未新增竞品',
    )
    await Promise.all([loadBindings(), loadAlerts()])
    await loadSnapshotsForCompare()
  } catch {
    // handled
  } finally {
    discovering.value = false
  }
}

async function handleMarkRead(alert: AlertItem) {
  if (!canMarkRead.value) {
    ElMessage.warning('仅运营或运营主管可标记已读')
    return
  }
  markingId.value = alert.id
  try {
    await markAlertRead(alert.id)
    ElMessage.success('已标记为已读')
    await loadAlerts()
  } catch {
    // handled
  } finally {
    markingId.value = null
  }
}

function dismissBanner() {
  bannerDismissed.value = true
}

function scrollToAlerts() {
  document.getElementById('competitor-alerts')?.scrollIntoView({
    behavior: 'smooth',
    block: 'start',
  })
}

function onResize() {
  chart?.resize()
}

watch(selectedProductId, async () => {
  compareIds.value = []
  selectedBindingId.value = null
  await Promise.all([loadBindings(), loadAlerts()])
  await loadSnapshotsForCompare()
})

watch(compareIds, () => {
  void loadSnapshotsForCompare()
})

onMounted(async () => {
  await loadProducts()
  if (selectedProductId.value) {
    await Promise.all([loadBindings(), loadAlerts()])
    await loadSnapshotsForCompare()
  }
  window.addEventListener('resize', onResize)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', onResize)
  chart?.dispose()
  chart = null
})
</script>

<template>
  <div class="competitors-page">
    <!-- 工具条 -->
    <section class="toolbar card">
      <div class="toolbar-left">
        <span class="field-label">自营商品</span>
        <el-select
          v-model="selectedProductId"
          class="product-select"
          filterable
          placeholder="选择要监控的商品"
          :loading="productsLoading"
        >
          <el-option
            v-for="p in products"
            :key="p.id"
            :label="p.title"
            :value="p.id"
          >
            <div class="option-row">
              <span class="option-title">{{ p.title }}</span>
              <el-tag size="small" effect="plain">{{ platformLabel(p.platform) }}</el-tag>
            </div>
          </el-option>
        </el-select>
        <el-tag
          v-if="selectedProduct"
          size="small"
          type="info"
          effect="plain"
          class="platform-tag"
        >
          {{ platformLabel(selectedProduct.platform) }}
        </el-tag>
      </div>
      <div class="toolbar-right">
        <el-button
          :icon="Refresh"
          :loading="refreshing"
          @click="handleRefresh"
        >
          刷新竞品数据
        </el-button>
        <el-button
          type="primary"
          :icon="Plus"
          :loading="discovering"
          @click="handleDiscover"
        >
          添加竞品
        </el-button>
      </div>
    </section>

    <!-- 未读告警横条 -->
    <section
      v-if="bannerAlert"
      class="alert-banner"
      :class="`sev-${severityToLabel(bannerAlert.severity)}`"
      :role="bannerAlert.severity === 'critical' ? 'alert' : 'status'"
    >
      <el-icon class="banner-icon"><WarningFilled /></el-icon>
      <div class="banner-body">
        <div class="banner-title">{{ bannerAlert.title }}</div>
        <div class="banner-sub">
          {{ bannerAlert.message || '—' }}
          <span v-if="bannerAlert.product_title">
            · 关联商品：{{ bannerAlert.product_title }}
          </span>
          · {{ formatRelative(bannerAlert.triggered_at) }}
        </div>
      </div>
      <div class="banner-actions">
        <el-button link type="primary" @click="scrollToAlerts">查看告警</el-button>
        <el-button
          link
          type="primary"
          :loading="markingId === bannerAlert.id"
          @click="handleMarkRead(bannerAlert)"
        >
          标记已读
        </el-button>
        <button type="button" class="banner-close" aria-label="关闭横条" @click="dismissBanner">
          <el-icon><Close /></el-icon>
        </button>
      </div>
    </section>

    <!-- 竞品表格 -->
    <section class="card table-card">
      <div class="card-head">
        <h2 class="card-title">
          已监控竞品
          <span class="count">({{ bindings.length }})</span>
        </h2>
        <el-badge
          :value="unreadAlerts.length"
          :hidden="unreadAlerts.length <= 0"
          :max="99"
          type="danger"
          class="unread-badge"
        >
          <span class="badge-label">未读告警</span>
        </el-badge>
      </div>

      <div v-if="tableState === 'loading'" class="state-box">加载中…</div>
      <div v-else-if="tableState === 'error'" class="state-box error">
        {{ tableError }}
        <el-button link type="primary" @click="loadBindings">重试</el-button>
      </div>
      <div v-else-if="tableState === 'empty'" class="state-box">
        暂无绑定竞品。点击「添加竞品」自动发现同类监控对象。
      </div>
      <div v-else class="table-scroll">
      <el-table
        :data="bindings"
        row-key="id"
        class="competitor-table"
        :row-class-name="rowClassName"
        @row-click="onRowClick"
      >
        <el-table-column width="48" align="center">
          <template #header>
            <span class="col-hint">对比</span>
          </template>
          <template #default="{ row }">
            <el-checkbox
              :model-value="compareIds.includes(row.id)"
              @click.stop
              @change="(checked: boolean | string | number) => toggleCompare(row.id, Boolean(checked))"
            />
          </template>
        </el-table-column>
        <el-table-column label="竞品标题" min-width="220">
          <template #default="{ row }">
            <div class="comp-cell">
              <img
                v-if="row.competitor_product?.image_url"
                :src="row.competitor_product.image_url"
                alt=""
                class="thumb"
              />
              <div class="comp-meta">
                <div class="comp-title">
                  {{ row.competitor_product?.title || '—' }}
                </div>
              </div>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="卖家" width="110">
          <template #default="{ row }">
            {{ platformLabel(row.competitor_product?.platform) }}
          </template>
        </el-table-column>
        <el-table-column label="价格" width="100" align="right">
          <template #default="{ row }">
            <span class="price">
              {{
                formatPrice(
                  row.latest_snapshot?.price ?? row.competitor_product?.price,
                  row.competitor_product?.currency,
                )
              }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="价格变化" width="120" align="right">
          <template #default="{ row }">
            <span
              class="change"
              :class="{
                down: (formatPct(row.latest_snapshot?.price_change_pct) ?? 0) < 0,
                up: (formatPct(row.latest_snapshot?.price_change_pct) ?? 0) > 0,
                flat: formatPct(row.latest_snapshot?.price_change_pct) === 0
                  || formatPct(row.latest_snapshot?.price_change_pct) === null,
              }"
            >
              <template v-if="formatPct(row.latest_snapshot?.price_change_pct) === null">
                — —
              </template>
              <template v-else-if="(formatPct(row.latest_snapshot?.price_change_pct) ?? 0) < 0">
                ▼ {{ formatPct(row.latest_snapshot?.price_change_pct)?.toFixed(1) }}%
              </template>
              <template v-else-if="(formatPct(row.latest_snapshot?.price_change_pct) ?? 0) > 0">
                ▲ +{{ formatPct(row.latest_snapshot?.price_change_pct)?.toFixed(1) }}%
              </template>
              <template v-else>— 0.0%</template>
            </span>
          </template>
        </el-table-column>
        <el-table-column label="评分" width="100">
          <template #default="{ row }">
            <span class="rating">
              <el-icon><StarFilled /></el-icon>
              {{ toNumber(row.competitor_product?.rating)?.toFixed(1) ?? '—' }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="评论数" width="100" align="right">
          <template #default="{ row }">
            {{ (row.competitor_product?.review_count ?? 0).toLocaleString() }}
          </template>
        </el-table-column>
        <el-table-column label="最后检查时间" width="120">
          <template #default="{ row }">
            {{
              formatRelative(
                row.latest_snapshot?.recorded_at
                  || row.competitor_product?.last_synced_at,
              )
            }}
          </template>
        </el-table-column>
        <el-table-column label="告警级别" width="100">
          <template #default="{ row }">
            <span
              v-if="rowSeverity(row)"
              class="sev-tag"
              :class="`sev-${rowSeverity(row)}`"
            >
              {{ severityText(rowSeverity(row)) }}
            </span>
            <span v-else class="muted">—</span>
          </template>
        </el-table-column>
      </el-table>
      </div>
    </section>

    <!-- 价格趋势 -->
    <section class="card chart-card">
      <div class="card-head">
        <h2 class="card-title">竞品价格趋势 · 近 30 天</h2>
        <span class="chart-hint">勾选表格左侧对比列，最多 5 条</span>
      </div>
      <div v-loading="chartLoading" class="chart-wrap">
        <div ref="chartRef" class="chart" />
      </div>
      <p class="chart-note">注：价格来自数据源同步，更新可能存在延迟</p>
    </section>

    <!-- 告警列表 -->
    <section id="competitor-alerts" class="card alerts-card">
      <div class="card-head">
        <h2 class="card-title">
          告警列表
          <el-badge
            :value="unreadAlerts.length"
            :hidden="unreadAlerts.length <= 0"
            type="danger"
            class="title-badge"
          />
        </h2>
      </div>
      <div v-if="!alerts.length" class="state-box">暂无未读竞品告警</div>
      <ul v-else class="alert-list">
        <li
          v-for="item in alerts"
          :key="item.id"
          class="alert-item"
          :class="`sev-${severityToLabel(item.severity)}`"
        >
          <div class="alert-main">
            <span class="sev-tag" :class="`sev-${severityToLabel(item.severity)}`">
              {{ severityText(severityToLabel(item.severity)) }}
            </span>
            <div>
              <div class="alert-title">{{ item.title }}</div>
              <div class="alert-msg">
                {{ item.message || '—' }} · {{ formatRelative(item.triggered_at) }}
              </div>
            </div>
          </div>
          <el-button
            size="small"
            :loading="markingId === item.id"
            :disabled="item.is_read"
            @click="handleMarkRead(item)"
          >
            标记已读
          </el-button>
        </li>
      </ul>
    </section>
  </div>
</template>

<style scoped>
.competitors-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.card {
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  padding: 16px 20px;
}

.toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
}

.toolbar-left {
  display: flex;
  align-items: center;
  gap: 12px;
  flex: 1;
  min-width: 280px;
}

.toolbar-right {
  display: flex;
  gap: 8px;
}

.field-label {
  font-size: 13px;
  color: #6b7280;
  white-space: nowrap;
}

.product-select {
  width: min(420px, 100%);
}

.option-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.option-title {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.platform-tag {
  flex-shrink: 0;
}

/* 告警横条 */
.alert-banner {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  min-height: 48px;
  padding: 12px 16px;
  border-radius: 6px;
  border: 1px solid #fecaca;
  border-left: 4px solid #dc2626;
  background: #fef2f2;
  animation: banner-in 180ms ease-out;
}

.alert-banner.sev-medium {
  border-color: #fde68a;
  border-left-color: #d97706;
  background: #fffbeb;
}

.alert-banner.sev-low {
  border-color: #e5e7eb;
  border-left-color: #6b7280;
  background: #f9fafb;
}

.banner-icon {
  color: #dc2626;
  font-size: 18px;
  margin-top: 2px;
}

.alert-banner.sev-medium .banner-icon {
  color: #d97706;
}

.banner-body {
  flex: 1;
  min-width: 0;
}

.banner-title {
  font-size: 14px;
  font-weight: 600;
  color: #111827;
}

.banner-sub {
  margin-top: 4px;
  font-size: 12px;
  color: #6b7280;
}

.banner-actions {
  display: flex;
  align-items: center;
  gap: 4px;
  flex-shrink: 0;
}

.banner-close {
  display: inline-flex;
  border: none;
  background: transparent;
  color: #6b7280;
  cursor: pointer;
  padding: 4px;
  border-radius: 4px;
}

.banner-close:hover {
  background: rgba(0, 0, 0, 0.04);
  color: #111827;
}

@keyframes banner-in {
  from {
    opacity: 0;
    transform: translateY(-4px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
  gap: 12px;
}

.card-title {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  color: #111827;
  display: flex;
  align-items: center;
  gap: 8px;
}

.count {
  color: #6b7280;
  font-weight: 500;
}

.badge-label {
  font-size: 13px;
  color: #6b7280;
}

.state-box {
  padding: 40px 16px;
  text-align: center;
  color: #6b7280;
  font-size: 14px;
}

.state-box.error {
  color: #dc2626;
}

.comp-cell {
  display: flex;
  align-items: center;
  gap: 10px;
}

.thumb {
  width: 40px;
  height: 40px;
  border-radius: 6px;
  object-fit: cover;
  background: #f3f4f6;
  flex-shrink: 0;
}

.comp-title {
  font-size: 14px;
  color: #111827;
  line-height: 1.35;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.price {
  font-weight: 700;
  color: #111827;
}

.change {
  font-weight: 700;
  font-variant-numeric: tabular-nums;
}

.change.down {
  color: #dc2626;
}

.change.up {
  color: #059669;
}

.change.flat {
  color: #6b7280;
  font-weight: 500;
}

.rating {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  color: #d97706;
}

.sev-tag {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 12px;
  font-weight: 600;
  line-height: 18px;
}

.sev-tag.sev-high {
  color: #dc2626;
  background: #fef2f2;
}

.sev-tag.sev-medium {
  color: #d97706;
  background: #fffbeb;
}

.sev-tag.sev-low {
  color: #6b7280;
  background: #f9fafb;
}

.muted {
  color: #9ca3af;
}

.col-hint {
  font-size: 12px;
  color: #9ca3af;
}

:deep(.competitor-table .el-table__row) {
  cursor: pointer;
}

:deep(.competitor-table .el-table__row:hover > td) {
  background: #f8fafc !important;
}

:deep(.competitor-table .el-table__row.is-selected > td) {
  background: #eef2ff !important;
}

:deep(.competitor-table .el-table__row.is-selected > td:first-child) {
  box-shadow: inset 3px 0 0 #4f46e5;
}

:deep(.competitor-table .el-table__row.row-high > td) {
  background: #fef2f2 !important;
}

:deep(.competitor-table .el-table__row.row-high > td:first-child) {
  box-shadow: inset 3px 0 0 #dc2626;
}

:deep(.competitor-table .el-table__row.row-high.is-selected > td:first-child) {
  box-shadow: inset 3px 0 0 #dc2626;
}

.chart-wrap {
  min-height: 280px;
}

.chart {
  width: 100%;
  height: 280px;
}

.chart-hint {
  font-size: 12px;
  color: #9ca3af;
}

.chart-note {
  margin: 8px 0 0;
  font-size: 12px;
  color: #9ca3af;
}

.alert-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.alert-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 12px 14px;
  border-radius: 6px;
  border: 1px solid #e5e7eb;
  border-left-width: 3px;
  background: #fff;
}

.alert-item.sev-high {
  border-left-color: #dc2626;
  background: #fef2f2;
}

.alert-item.sev-medium {
  border-left-color: #d97706;
  background: #fffbeb;
}

.alert-item.sev-low {
  border-left-color: #6b7280;
  background: #f9fafb;
}

.alert-main {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  min-width: 0;
}

.alert-title {
  font-size: 14px;
  font-weight: 600;
  color: #111827;
}

.alert-msg {
  margin-top: 4px;
  font-size: 12px;
  color: #6b7280;
}

@media (max-width: 768px) {
  .alert-banner {
    flex-wrap: wrap;
  }

  .banner-actions {
    width: 100%;
    justify-content: flex-end;
  }
}
</style>
