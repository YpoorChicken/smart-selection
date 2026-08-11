<script setup lang="ts">
import {
  nextTick,
  onBeforeUnmount,
  onMounted,
  ref,
} from 'vue'
import { useRouter } from 'vue-router'
import {
  ArrowRight,
  Bell,
  Box,
  Collection,
  Goods,
  TrendCharts,
} from '@element-plus/icons-vue'
import * as echarts from 'echarts/core'
import { BarChart, LineChart } from 'echarts/charts'
import {
  GridComponent,
  LegendComponent,
  TooltipComponent,
} from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import {
  getCategoryGrowth,
  getDailyPriceTrend,
  getDashboardOverview,
} from '@/api/dashboard'
import type {
  CategoryGrowthItem,
  DailyPriceTrendPoint,
  DashboardOverviewData,
} from '@/types/dashboard'

echarts.use([
  BarChart,
  LineChart,
  GridComponent,
  LegendComponent,
  TooltipComponent,
  CanvasRenderer,
])

type LoadState = 'loading' | 'success' | 'error'

const router = useRouter()

const pageState = ref<LoadState>('loading')
const pageError = ref('')
const contentVisible = ref(false)

const overview = ref<DashboardOverviewData | null>(null)
const growthItems = ref<CategoryGrowthItem[]>([])
const pricePoints = ref<DailyPriceTrendPoint[]>([])

const barChartRef = ref<HTMLDivElement | null>(null)
const lineChartRef = ref<HTMLDivElement | null>(null)
let barChart: echarts.ECharts | null = null
let lineChart: echarts.ECharts | null = null

function toNumber(value: string | number | null | undefined): number | null {
  if (value === null || value === undefined || value === '') return null
  const n = typeof value === 'number' ? value : Number(value)
  return Number.isFinite(n) ? n : null
}

function formatPct(value: string | number | null | undefined): string {
  const n = toNumber(value)
  if (n === null) return '—'
  const pct = Math.abs(n) <= 1 ? n * 100 : n
  const sign = pct > 0 ? '+' : ''
  return `${sign}${pct.toFixed(1)}%`
}

function formatUpdatedAt(iso: string | undefined): string {
  if (!iso) return '—'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return '—'
  const hh = String(d.getHours()).padStart(2, '0')
  const mm = String(d.getMinutes()).padStart(2, '0')
  return `今天 ${hh}:${mm}`
}

function weekdayLabel(isoDate: string): string {
  const d = new Date(`${isoDate}T00:00:00Z`)
  if (Number.isNaN(d.getTime())) return isoDate.slice(5)
  const labels = ['周日', '周一', '周二', '周三', '周四', '周五', '周六']
  return labels[d.getUTCDay()] ?? isoDate.slice(5)
}

function disposeCharts() {
  barChart?.dispose()
  lineChart?.dispose()
  barChart = null
  lineChart = null
}

function renderBarChart() {
  if (!barChartRef.value) return
  if (!barChart) barChart = echarts.init(barChartRef.value)

  const names = growthItems.value.map((item) => item.category_name)
  const rates = growthItems.value.map((item) => {
    const n = toNumber(item.growth_rate)
    if (n === null) return 0
    return Math.abs(n) <= 1 ? n * 100 : n
  })
  const maxIndex = rates.reduce(
    (best, value, index, arr) => (value > arr[best]! ? index : best),
    0,
  )

  barChart.setOption({
    grid: { left: 48, right: 16, top: 36, bottom: 48 },
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      formatter: (params: unknown) => {
        const item = Array.isArray(params) ? params[0] : null
        if (!item || typeof item !== 'object') return ''
        const point = item as { name?: string; value?: number }
        return `${point.name || ''}<br/>增长率 <b>${(point.value ?? 0).toFixed(1)}%</b>`
      },
    },
    xAxis: {
      type: 'category',
      data: names,
      axisLabel: {
        color: '#6B7280',
        fontSize: 11,
        interval: 0,
        rotate: names.some((n) => n.length > 6) ? 20 : 0,
      },
      axisLine: { lineStyle: { color: '#E5E7EB' } },
      axisTick: { show: false },
    },
    yAxis: {
      type: 'value',
      axisLabel: {
        color: '#9CA3AF',
        fontSize: 11,
        formatter: (v: number) => `${v}%`,
      },
      splitLine: { lineStyle: { color: '#F3F4F6' } },
    },
    series: [
      {
        type: 'bar',
        data: rates.map((value, index) => ({
          value: Number(value.toFixed(1)),
          itemStyle: {
            color: index === maxIndex ? '#059669' : '#4F46E5',
            borderRadius: [4, 4, 0, 0],
          },
          label: {
            show: true,
            position: 'top',
            color: '#6B7280',
            fontSize: 11,
            formatter: ({ value: v }: { value: number }) => `${v}%`,
          },
        })),
        barMaxWidth: 40,
      },
    ],
  })
}

function renderLineChart() {
  if (!lineChartRef.value) return
  if (!lineChart) lineChart = echarts.init(lineChartRef.value)

  const labels = pricePoints.value.map((p) => weekdayLabel(p.date))
  const own = pricePoints.value.map((p) => toNumber(p.own_avg_price))
  const comp = pricePoints.value.map((p) => toNumber(p.competitor_avg_price))
  const hasData = own.some((v) => v !== null) || comp.some((v) => v !== null)

  lineChart.setOption({
    color: ['#4F46E5', '#93C5FD'],
    grid: { left: 48, right: 16, top: 40, bottom: 36 },
    legend: {
      top: 0,
      right: 0,
      icon: 'roundRect',
      itemWidth: 12,
      itemHeight: 4,
      textStyle: { color: '#6B7280', fontSize: 12 },
      data: ['自营均价', '竞品均价'],
    },
    tooltip: {
      trigger: 'axis',
      formatter: (params: unknown) => {
        if (!Array.isArray(params)) return ''
        const lines = params.map((item) => {
          const p = item as { seriesName?: string; value?: number | null; marker?: string }
          const val =
            p.value === null || p.value === undefined
              ? '—'
              : `$${Number(p.value).toFixed(2)}`
          return `${p.marker || ''}${p.seriesName || ''} <b>${val}</b>`
        })
        const axis = (params[0] as { axisValueLabel?: string })?.axisValueLabel || ''
        return `${axis}<br/>${lines.join('<br/>')}`
      },
    },
    xAxis: {
      type: 'category',
      data: labels,
      boundaryGap: false,
      axisLabel: { color: '#6B7280', fontSize: 11 },
      axisLine: { lineStyle: { color: '#E5E7EB' } },
      axisTick: { show: false },
    },
    yAxis: {
      type: 'value',
      scale: hasData,
      axisLabel: {
        color: '#9CA3AF',
        fontSize: 11,
        formatter: (v: number) => `$${v}`,
      },
      splitLine: { lineStyle: { color: '#F3F4F6' } },
    },
    series: [
      {
        name: '自营均价',
        type: 'line',
        data: own,
        smooth: true,
        showSymbol: true,
        symbolSize: 6,
        connectNulls: true,
        lineStyle: { width: 2.5, color: '#4F46E5' },
        areaStyle: { color: 'rgba(79, 70, 229, 0.10)' },
      },
      {
        name: '竞品均价',
        type: 'line',
        data: comp,
        smooth: true,
        showSymbol: true,
        symbolSize: 5,
        connectNulls: true,
        lineStyle: { width: 2, type: 'dashed', color: '#93C5FD' },
      },
    ],
  })
}

async function renderCharts() {
  await nextTick()
  renderBarChart()
  renderLineChart()
}

function handleResize() {
  barChart?.resize()
  lineChart?.resize()
}

async function loadDashboard() {
  pageState.value = 'loading'
  pageError.value = ''
  contentVisible.value = false
  disposeCharts()

  try {
    const [overviewData, growthData, priceData] = await Promise.all([
      getDashboardOverview({ days: 30 }),
      getCategoryGrowth({ days: 30, limit: 6 }),
      getDailyPriceTrend({ days: 7 }),
    ])
    overview.value = overviewData
    growthItems.value = growthData.items
    pricePoints.value = priceData.points
    pageState.value = 'success'
    await nextTick()
    requestAnimationFrame(() => {
      contentVisible.value = true
    })
    await renderCharts()
  } catch (err) {
    pageState.value = 'error'
    pageError.value =
      err instanceof Error ? err.message : '看板数据加载失败，请稍后重试'
  }
}

function goTrends() {
  void router.push('/trends')
}

function goSelections() {
  void router.push('/selections')
}

function goCompetitors() {
  void router.push('/competitors')
}

onMounted(() => {
  void loadDashboard()
  window.addEventListener('resize', handleResize)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', handleResize)
  disposeCharts()
})
</script>

<template>
  <div class="dashboard">
    <div v-if="pageState === 'loading'" class="dashboard-skeleton" aria-busy="true">
      <div class="skel-header">
        <el-skeleton animated :rows="1" style="width: 200px" />
        <el-skeleton animated :rows="1" style="width: 160px" />
      </div>
      <div class="kpi-grid">
        <div v-for="i in 4" :key="`kpi-skel-${i}`" class="kpi-card skel-card">
          <el-skeleton animated :rows="3" />
        </div>
      </div>
      <div class="chart-grid">
        <div class="panel skel-card"><el-skeleton animated :rows="6" /></div>
        <div class="panel skel-card"><el-skeleton animated :rows="6" /></div>
      </div>
      <div class="bottom-grid">
        <div class="panel skel-card"><el-skeleton animated :rows="3" /></div>
        <div class="panel skel-card"><el-skeleton animated :rows="3" /></div>
        <div class="panel skel-card"><el-skeleton animated :rows="3" /></div>
      </div>
    </div>

    <div v-else-if="pageState === 'error'" class="error-block">
      <el-alert
        type="error"
        :closable="false"
        show-icon
        :title="pageError || '看板加载失败'"
      />
      <el-button type="primary" class="retry-btn" @click="loadDashboard">
        重试
      </el-button>
    </div>

    <div
      v-else
      class="dashboard-body"
      :class="{ 'is-visible': contentVisible }"
    >
      <header class="page-header">
        <div>
          <h1 class="page-title">数据概览</h1>
          <p class="page-meta">
            近 7 天 · 更新时间：{{ formatUpdatedAt(overview?.generated_at) }}
          </p>
        </div>
      </header>

      <section class="kpi-grid" aria-label="核心指标">
        <article class="kpi-card">
          <div class="kpi-top">
            <span class="kpi-label">商品总数</span>
            <el-icon class="kpi-icon"><Goods /></el-icon>
          </div>
          <div class="kpi-value">{{ overview?.product_total ?? 0 }}</div>
          <div class="kpi-sub">全平台在售商品</div>
        </article>

        <article class="kpi-card">
          <div class="kpi-top">
            <span class="kpi-label">监控品类</span>
            <el-icon class="kpi-icon"><Collection /></el-icon>
          </div>
          <div class="kpi-value">{{ overview?.watched_category_count ?? 0 }}</div>
          <div class="kpi-sub">已标记关注的品类</div>
        </article>

        <article class="kpi-card accent">
          <div class="kpi-top">
            <span class="kpi-label">待审推荐</span>
            <el-icon class="kpi-icon accent-icon"><Box /></el-icon>
          </div>
          <div class="kpi-value accent-value">
            {{ overview?.pending_recommendation_count ?? 0 }}
          </div>
          <div class="kpi-sub">待运营审核的选品</div>
        </article>

        <article class="kpi-card" :class="{ alert: (overview?.today_alert_count ?? 0) > 0 }">
          <div class="kpi-top">
            <span class="kpi-label">今日告警</span>
            <el-icon class="kpi-icon" :class="{ 'alert-icon': (overview?.today_alert_count ?? 0) > 0 }">
              <Bell />
            </el-icon>
          </div>
          <div
            class="kpi-value"
            :class="{ 'alert-value': (overview?.today_alert_count ?? 0) > 0 }"
          >
            {{ overview?.today_alert_count ?? 0 }}
          </div>
          <div class="kpi-sub">含竞品 / 库存等类型</div>
        </article>
      </section>

      <section class="chart-grid" aria-label="趋势图表">
        <article class="panel chart-panel">
          <div class="panel-head">
            <h2 class="panel-title">Top 品类增长率</h2>
            <button type="button" class="link-btn" @click="goTrends">
              查看全部 →
            </button>
          </div>
          <div v-if="growthItems.length === 0" class="chart-empty">
            <el-icon :size="28"><TrendCharts /></el-icon>
            <p>暂无品类增长率数据</p>
            <span>请先在市场趋势页触发趋势计算</span>
          </div>
          <div v-else ref="barChartRef" class="chart-canvas" />
        </article>

        <article class="panel chart-panel">
          <div class="panel-head">
            <h2 class="panel-title">近 7 天价格变动趋势</h2>
            <button type="button" class="link-btn" @click="goCompetitors">
              查看全部 →
            </button>
          </div>
          <div
            v-if="
              pricePoints.every(
                (p) => p.own_avg_price == null && p.competitor_avg_price == null,
              )
            "
            class="chart-empty"
          >
            <el-icon :size="28"><TrendCharts /></el-icon>
            <p>暂无价格变动数据</p>
            <span>同步商品历史或刷新竞品后可出图</span>
          </div>
          <div v-else ref="lineChartRef" class="chart-canvas" />
        </article>
      </section>

      <section class="bottom-grid" aria-label="洞察摘要">
        <button
          type="button"
          class="insight-card growth"
          @click="goTrends"
        >
          <div class="insight-label">最快增长品类</div>
          <template v-if="overview?.fastest_growing_category">
            <div class="insight-name">
              {{ overview.fastest_growing_category.category_name }}
            </div>
            <div class="insight-metric">
              {{ formatPct(overview.fastest_growing_category.growth_rate) }}
              <span class="insight-cap">环比增长</span>
            </div>
          </template>
          <template v-else>
            <div class="insight-name muted">暂无增长品类</div>
            <div class="insight-metric muted">—</div>
          </template>
          <el-icon class="insight-arrow"><ArrowRight /></el-icon>
        </button>

        <button
          type="button"
          class="insight-card ocean"
          @click="goSelections"
        >
          <div class="insight-label">蓝海品类</div>
          <template v-if="overview?.blue_ocean_category">
            <div class="insight-name">
              {{ overview.blue_ocean_category.category_name }}
            </div>
            <div class="insight-metric">
              {{ Math.round(toNumber(overview.blue_ocean_category.blue_ocean_index) ?? 0) }}
              <span class="insight-cap">蓝海指数</span>
            </div>
          </template>
          <template v-else>
            <div class="insight-name muted">暂无蓝海推荐</div>
            <div class="insight-metric muted">—</div>
          </template>
          <el-icon class="insight-arrow"><ArrowRight /></el-icon>
        </button>

        <article class="ai-card">
          <div class="ai-head">
            <span class="ai-badge" aria-hidden="true">✨</span>
            <h2 class="panel-title">AI 一句话摘要</h2>
          </div>
          <p class="ai-text">
            {{ overview?.summary || '暂无摘要，完成选品与竞品同步后将自动生成。' }}
          </p>
          <div class="ai-foot">
            <span>生成于 {{ formatUpdatedAt(overview?.generated_at) }}</span>
            <button type="button" class="link-btn" @click="loadDashboard">
              刷新
            </button>
          </div>
        </article>
      </section>
    </div>
  </div>
</template>

<style scoped>
.dashboard {
  min-height: 100%;
}

.dashboard-skeleton,
.dashboard-body {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.dashboard-body {
  opacity: 0;
  transform: translateY(4px);
  transition: opacity 180ms ease, transform 180ms ease;
}

.dashboard-body.is-visible {
  opacity: 1;
  transform: translateY(0);
}

.skel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.skel-card {
  padding: 20px;
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
}

.page-header {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
}

.page-title {
  margin: 0;
  font-size: 22px;
  font-weight: 600;
  color: #111827;
  letter-spacing: -0.2px;
  line-height: 1.3;
}

.page-meta {
  margin: 6px 0 0;
  font-size: 12px;
  color: #6b7280;
}

.kpi-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 24px;
}

.kpi-card {
  position: relative;
  padding: 20px 20px 18px 24px;
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  box-shadow: 0 1px 2px rgba(17, 24, 39, 0.04);
  transition: transform 120ms ease, box-shadow 120ms ease;
  overflow: hidden;
}

.kpi-card::before {
  content: '';
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  width: 4px;
  background: #4f46e5;
}

.kpi-card.accent::before {
  background: #4f46e5;
}

.kpi-card.alert::before {
  background: #dc2626;
}

.kpi-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 8px 20px rgba(17, 24, 39, 0.08);
}

.kpi-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}

.kpi-label {
  font-size: 13px;
  font-weight: 500;
  color: #6b7280;
}

.kpi-icon {
  color: #9ca3af;
  font-size: 18px;
}

.kpi-icon.accent-icon {
  color: #4f46e5;
}

.kpi-icon.alert-icon {
  color: #dc2626;
}

.kpi-value {
  font-size: 32px;
  font-weight: 700;
  line-height: 1.15;
  letter-spacing: -0.5px;
  color: #111827;
}

.kpi-value.accent-value {
  color: #4f46e5;
}

.kpi-value.alert-value {
  color: #dc2626;
}

.kpi-sub {
  margin-top: 8px;
  font-size: 12px;
  color: #9ca3af;
}

.chart-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 24px;
}

.panel {
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  box-shadow: 0 1px 2px rgba(17, 24, 39, 0.04);
  transition: transform 120ms ease, box-shadow 120ms ease;
}

.panel:hover {
  transform: translateY(-2px);
  box-shadow: 0 8px 20px rgba(17, 24, 39, 0.08);
}

.chart-panel {
  padding: 20px 20px 16px;
  min-height: 340px;
  display: flex;
  flex-direction: column;
}

.panel-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}

.panel-title {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  color: #111827;
}

.link-btn {
  border: 0;
  background: transparent;
  padding: 0;
  font-size: 13px;
  color: #4f46e5;
  cursor: pointer;
  transition: color 120ms ease;
}

.link-btn:hover {
  color: #4338ca;
}

.chart-canvas {
  flex: 1;
  width: 100%;
  min-height: 280px;
}

.chart-empty {
  flex: 1;
  min-height: 280px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  color: #9ca3af;
}

.chart-empty p {
  margin: 0;
  font-size: 14px;
  font-weight: 600;
  color: #6b7280;
}

.chart-empty span {
  font-size: 12px;
}

.bottom-grid {
  display: grid;
  grid-template-columns: 1fr 1fr 1.2fr;
  gap: 24px;
}

.insight-card {
  position: relative;
  text-align: left;
  border: 0;
  border-radius: 8px;
  padding: 24px;
  min-height: 140px;
  cursor: pointer;
  color: #111827;
  transition: transform 120ms ease, box-shadow 120ms ease;
  box-shadow: 0 1px 2px rgba(17, 24, 39, 0.04);
}

.insight-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 10px 24px rgba(17, 24, 39, 0.1);
}

.insight-card.growth {
  background: linear-gradient(135deg, #ecfdf5 0%, #d1fae5 55%, #a7f3d0 100%);
}

.insight-card.ocean {
  background: linear-gradient(135deg, #eef2ff 0%, #e0e7ff 50%, #c7d2fe 100%);
}

.insight-label {
  font-size: 12px;
  font-weight: 600;
  color: #6b7280;
  letter-spacing: 0.2px;
}

.insight-name {
  margin-top: 12px;
  font-size: 18px;
  font-weight: 600;
  color: #111827;
  line-height: 1.3;
  padding-right: 28px;
}

.insight-name.muted,
.insight-metric.muted {
  color: #9ca3af;
}

.insight-metric {
  margin-top: 16px;
  font-size: 28px;
  font-weight: 700;
  letter-spacing: -0.4px;
  color: #059669;
  display: flex;
  align-items: baseline;
  gap: 8px;
}

.insight-card.ocean .insight-metric {
  color: #4f46e5;
}

.insight-cap {
  font-size: 12px;
  font-weight: 500;
  color: #6b7280;
}

.insight-arrow {
  position: absolute;
  right: 20px;
  top: 50%;
  transform: translateY(-50%);
  font-size: 18px;
  color: #6b7280;
}

.ai-card {
  padding: 20px 24px;
  border-radius: 8px;
  background: linear-gradient(135deg, #eef2ff 0%, #f5f3ff 55%, #e0e7ff 100%);
  border: 1px solid #e0e7ff;
  box-shadow: 0 1px 2px rgba(79, 70, 229, 0.06);
  transition: transform 120ms ease, box-shadow 120ms ease;
  display: flex;
  flex-direction: column;
  min-height: 140px;
}

.ai-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 10px 24px rgba(79, 70, 229, 0.12);
}

.ai-head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
}

.ai-badge {
  font-size: 16px;
  line-height: 1;
}

.ai-text {
  margin: 0;
  flex: 1;
  font-size: 14px;
  line-height: 1.65;
  color: #374151;
}

.ai-foot {
  margin-top: 16px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 12px;
  color: #9ca3af;
}

.error-block {
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  padding: 24px;
}

.retry-btn {
  margin-top: 16px;
}

@media (max-width: 1200px) {
  .kpi-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .chart-grid,
  .bottom-grid {
    grid-template-columns: 1fr;
  }
}

@media (prefers-reduced-motion: reduce) {
  .dashboard-body,
  .kpi-card,
  .panel,
  .insight-card,
  .ai-card {
    transition: none;
  }

  .kpi-card:hover,
  .panel:hover,
  .insight-card:hover,
  .ai-card:hover {
    transform: none;
  }
}
</style>
