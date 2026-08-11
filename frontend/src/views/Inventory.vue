<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import {
  Bell,
  Box,
  Refresh,
  Search,
  WarningFilled,
} from '@element-plus/icons-vue'
import PageHeader from '@/components/PageHeader.vue'
import EmptyState from '@/components/EmptyState.vue'
import {
  getInventoryList,
  getInventorySummary,
  updateInventory,
} from '@/api/inventory'
import { useAuthStore } from '@/stores/auth'
import type {
  InventoryItem,
  InventoryRisk,
  InventorySummaryData,
} from '@/types/inventory'
import type { PlatformId } from '@/types/products'

type LoadState = 'loading' | 'success' | 'empty' | 'error'

const PLATFORM_LABEL: Record<PlatformId, string> = {
  amazon: 'Amazon',
  shopee: 'Shopee',
  mock: 'Mock',
  dummyjson: 'DummyJSON',
  fakestore: 'FakeStore',
}

const RISK_LABEL: Record<InventoryRisk, string> = {
  normal: '正常',
  watch: '预警',
  critical: '告警',
}

const router = useRouter()
const auth = useAuthStore()

const canWrite = computed(() => {
  const role = auth.user?.role
  return role === 'operator' || role === 'ops_lead'
})

const pageState = ref<LoadState>('loading')
const pageError = ref('')
const contentVisible = ref(false)

const summary = ref<InventorySummaryData | null>(null)
const items = ref<InventoryItem[]>([])
const total = ref(0)

const filters = reactive({
  keyword: '',
  risk_level: '' as InventoryRisk | '',
})

const pager = reactive({
  page: 1,
  page_size: 20,
})

const updatingId = ref<string | null>(null)
const dialogVisible = ref(false)
const dialogSaving = ref(false)
const editRow = ref<InventoryItem | null>(null)
const editForm = reactive({
  quantity: 0,
  safety_stock: 0,
  predicted_daily_sales: null as number | null,
})

let keywordTimer: ReturnType<typeof setTimeout> | null = null
let requestSeq = 0

function toNumber(value: string | number | null | undefined): number | null {
  if (value === null || value === undefined || value === '') return null
  const n = typeof value === 'number' ? value : Number(value)
  return Number.isFinite(n) ? n : null
}

function formatSales(value: string | number | null | undefined): string {
  const n = toNumber(value)
  if (n === null) return '—'
  return n.toFixed(1)
}

function formatUpdatedAt(iso: string | undefined): string {
  if (!iso) return '—'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return '—'
  const hh = String(d.getHours()).padStart(2, '0')
  const mm = String(d.getMinutes()).padStart(2, '0')
  const today = new Date()
  const sameDay =
    d.getFullYear() === today.getFullYear() &&
    d.getMonth() === today.getMonth() &&
    d.getDate() === today.getDate()
  if (sameDay) return `今天 ${hh}:${mm}`
  return `${d.getMonth() + 1}/${d.getDate()} ${hh}:${mm}`
}

function warehouseLabel(platform: PlatformId): string {
  if (platform === 'amazon') return '美国西部仓'
  if (platform === 'shopee') return '东南亚仓'
  return '默认仓'
}

/** 在途量后端未建模，列表展示占位「—」 */
function inTransitDisplay(): string {
  return '—'
}

function rowClassName({ row }: { row: InventoryItem }): string {
  if (row.risk_level === 'critical') return 'row-critical'
  if (row.risk_level === 'watch') return 'row-watch'
  return 'row-normal'
}

async function loadSummary() {
  summary.value = await getInventorySummary()
}

async function loadList(opts?: { soft?: boolean }) {
  const seq = ++requestSeq
  if (!opts?.soft) {
    pageState.value = 'loading'
    pageError.value = ''
    contentVisible.value = false
  }

  try {
    const [listData] = await Promise.all([
      getInventoryList({
        page: pager.page,
        page_size: pager.page_size,
        risk_level: filters.risk_level,
        keyword: filters.keyword.trim() || undefined,
      }),
      loadSummary().catch(() => undefined),
    ])

    if (seq !== requestSeq) return

    items.value = listData.items
    total.value = listData.meta.total
    pageState.value =
      listData.items.length === 0 && !filters.keyword && !filters.risk_level
        ? 'empty'
        : listData.items.length === 0
          ? 'empty'
          : 'success'

    requestAnimationFrame(() => {
      if (seq === requestSeq) contentVisible.value = true
    })
  } catch (err) {
    if (seq !== requestSeq) return
    pageError.value =
      err instanceof Error ? err.message : '库存列表加载失败，请稍后重试'
    if (!opts?.soft || items.value.length === 0) {
      pageState.value = 'error'
    }
  }
}

function onKeywordInput() {
  if (keywordTimer) clearTimeout(keywordTimer)
  keywordTimer = setTimeout(() => {
    pager.page = 1
    void loadList({ soft: true })
  }, 300)
}

function onRiskChange() {
  pager.page = 1
  void loadList({ soft: true })
}

function openUpdate(row: InventoryItem) {
  if (!canWrite.value) {
    ElMessage.warning('仅运营或运营主管可更新库存')
    return
  }
  editRow.value = row
  editForm.quantity = row.quantity
  editForm.safety_stock = row.safety_stock
  editForm.predicted_daily_sales = toNumber(row.predicted_daily_sales)
  dialogVisible.value = true
}

async function submitUpdate() {
  if (!editRow.value) return
  dialogSaving.value = true
  updatingId.value = editRow.value.product_id
  try {
    const result = await updateInventory(editRow.value.product_id, {
      quantity: editForm.quantity,
      safety_stock: editForm.safety_stock,
      predicted_daily_sales: editForm.predicted_daily_sales,
    })
    ElMessage.success(
      result.alert_created ? '库存已更新，并触发库存告警' : '库存已更新',
    )
    dialogVisible.value = false
    await loadList({ soft: true })
  } catch (err) {
    ElMessage.error(err instanceof Error ? err.message : '更新库存失败')
  } finally {
    dialogSaving.value = false
    updatingId.value = null
  }
}

function goProduct(row: InventoryItem) {
  void router.push({ path: '/products', query: { keyword: row.product_title } })
}

function clearFilters() {
  filters.keyword = ''
  filters.risk_level = ''
  pager.page = 1
  void loadList()
}

watch(
  () => [pager.page, pager.page_size],
  () => {
    void loadList({ soft: true })
  },
)

onMounted(() => {
  void loadList()
})
</script>

<template>
  <div class="inventory-page">
    <PageHeader description="按安全库存阈值识别告警与预警，支持行内更新库存。">
      <template #actions>
        <el-button :icon="Refresh" @click="loadList()">刷新</el-button>
      </template>
    </PageHeader>

    <div v-if="pageState === 'loading'" class="skeleton-block" aria-busy="true">
      <div class="stats-card skel">
        <el-skeleton animated :rows="2" />
      </div>
      <div class="panel skel">
        <el-skeleton animated :rows="8" />
      </div>
    </div>

    <div v-else-if="pageState === 'error'" class="panel error-panel">
      <EmptyState
        title="库存数据加载失败"
        :description="pageError || '请检查网络后重试'"
        :icon="WarningFilled"
      >
        <el-button type="primary" @click="loadList()">重试</el-button>
      </EmptyState>
    </div>

    <div
      v-else
      class="inventory-body"
      :class="{ 'is-visible': contentVisible }"
    >
      <section class="stats-card" aria-label="库存统计">
        <div class="stat-item">
          <el-icon class="stat-icon"><Box /></el-icon>
          <div>
            <div class="stat-label">库存商品总数</div>
            <div class="stat-value">{{ summary?.product_total ?? total }}</div>
          </div>
        </div>
        <div class="stat-divider" aria-hidden="true" />
        <div class="stat-item">
          <el-icon class="stat-icon danger"><Bell /></el-icon>
          <div>
            <div class="stat-label">库存告警</div>
            <div class="stat-value danger">{{ summary?.critical_count ?? 0 }}</div>
            <div class="stat-sub">库存低于安全库存</div>
          </div>
        </div>
        <div class="stat-divider" aria-hidden="true" />
        <div class="stat-item">
          <el-icon class="stat-icon warning"><WarningFilled /></el-icon>
          <div>
            <div class="stat-label">库存预警</div>
            <div class="stat-value warning">{{ summary?.watch_count ?? 0 }}</div>
            <div class="stat-sub">库存低于 2× 安全库存</div>
          </div>
        </div>
      </section>

      <section class="toolbar panel">
        <el-input
          v-model="filters.keyword"
          clearable
          class="search-input"
          placeholder="搜索商品名 / SKU"
          :prefix-icon="Search"
          @input="onKeywordInput"
          @clear="onRiskChange"
        />
        <el-select
          v-model="filters.risk_level"
          class="risk-select"
          placeholder="全部状态"
          @change="onRiskChange"
        >
          <el-option label="全部状态" value="" />
          <el-option label="告警" value="critical" />
          <el-option label="预警" value="watch" />
          <el-option label="正常" value="normal" />
        </el-select>
        <div class="toolbar-meta">
          <span>告警 &lt; 安全库存 · 预警 &lt; 2×安全库存</span>
          <span>最近更新 {{ formatUpdatedAt(summary?.generated_at) }}</span>
        </div>
      </section>

      <section class="panel table-panel">
        <div class="panel-head">
          <h2 class="panel-title">库存风险明细</h2>
          <span class="panel-meta">共 {{ total }} 条</span>
        </div>

        <div
          v-if="pageState === 'empty' || items.length === 0"
          class="table-empty"
        >
          <EmptyState
            title="暂无库存数据"
            :description="
              filters.keyword || filters.risk_level
                ? '当前筛选无结果，可清空条件后重试'
                : '系统将在首次打开时自动生成模拟库存快照'
            "
            :icon="Box"
          >
            <el-button
              v-if="filters.keyword || filters.risk_level"
              @click="clearFilters"
            >
              清空筛选
            </el-button>
            <el-button type="primary" @click="loadList()">刷新</el-button>
          </EmptyState>
        </div>

        <div v-else class="table-scroll">
          <el-table
            :data="items"
            row-key="id"
            class="inventory-table"
            :row-class-name="rowClassName"
            empty-text="暂无数据"
          >
            <el-table-column label="商品" min-width="220">
              <template #default="{ row }: { row: InventoryItem }">
                <div class="product-cell">
                  <div class="product-name" :title="row.product_title">
                    {{ row.product_title }}
                  </div>
                  <div class="product-meta">
                    <span class="platform-tag">{{ PLATFORM_LABEL[row.platform] }}</span>
                    <span v-if="row.sku" class="sku">{{ row.sku }}</span>
                  </div>
                </div>
              </template>
            </el-table-column>

            <el-table-column label="仓库" width="120">
              <template #default="{ row }: { row: InventoryItem }">
                {{ warehouseLabel(row.platform) }}
              </template>
            </el-table-column>

            <el-table-column label="当前库存" width="100" align="right">
              <template #default="{ row }: { row: InventoryItem }">
                {{ row.quantity }}
              </template>
            </el-table-column>

            <el-table-column label="安全库存" width="100" align="right">
              <template #default="{ row }: { row: InventoryItem }">
                {{ row.safety_stock }}
              </template>
            </el-table-column>

            <el-table-column label="在途" width="80" align="right">
              <template #default>
                {{ inTransitDisplay() }}
              </template>
            </el-table-column>

            <el-table-column label="预计日销" width="100" align="right">
              <template #default="{ row }: { row: InventoryItem }">
                {{ formatSales(row.predicted_daily_sales) }}
              </template>
            </el-table-column>

            <el-table-column label="状态" width="96" align="center">
              <template #default="{ row }: { row: InventoryItem }">
                <span class="risk-tag" :class="row.risk_level">
                  {{ RISK_LABEL[row.risk_level] }}
                </span>
              </template>
            </el-table-column>

            <el-table-column label="操作" width="160" fixed="right">
              <template #default="{ row }: { row: InventoryItem }">
                <el-button link type="primary" @click="goProduct(row)">
                  查看商品
                </el-button>
                <el-button
                  link
                  type="primary"
                  :loading="updatingId === row.product_id"
                  :disabled="!canWrite"
                  @click="openUpdate(row)"
                >
                  更新库存
                </el-button>
              </template>
            </el-table-column>
          </el-table>
        </div>

        <div v-if="total > 0" class="pager">
          <span class="pager-total">共 {{ total }} 条</span>
          <el-pagination
            v-model:current-page="pager.page"
            v-model:page-size="pager.page_size"
            background
            layout="sizes, prev, pager, next"
            :total="total"
            :page-sizes="[10, 20, 50]"
          />
        </div>
      </section>
    </div>

    <el-dialog
      v-model="dialogVisible"
      title="更新库存"
      width="420px"
      destroy-on-close
      @closed="editRow = null"
    >
      <p v-if="editRow" class="dialog-product">{{ editRow.product_title }}</p>
      <el-form label-position="top">
        <el-form-item label="当前库存" required>
          <el-input-number
            v-model="editForm.quantity"
            :min="0"
            :step="1"
            controls-position="right"
            class="full-width"
          />
        </el-form-item>
        <el-form-item label="安全库存">
          <el-input-number
            v-model="editForm.safety_stock"
            :min="0"
            :step="1"
            controls-position="right"
            class="full-width"
          />
        </el-form-item>
        <el-form-item label="预计日销">
          <el-input-number
            v-model="editForm.predicted_daily_sales"
            :min="0"
            :step="0.1"
            :precision="2"
            controls-position="right"
            class="full-width"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="dialogSaving" @click="submitUpdate">
          保存
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.inventory-page {
  min-height: 100%;
}

.inventory-body {
  display: flex;
  flex-direction: column;
  gap: 24px;
  opacity: 0;
  transform: translateY(4px);
  transition: opacity 180ms ease, transform 180ms ease;
}

.inventory-body.is-visible {
  opacity: 1;
  transform: translateY(0);
}

.skeleton-block {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.skel,
.panel {
  background: var(--color-surface);
  border: 1px solid var(--color-hairline);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-card);
}

.skel {
  padding: 20px;
}

.stats-card {
  display: grid;
  grid-template-columns: 1fr auto 1fr auto 1fr;
  align-items: center;
  gap: 8px;
  padding: 20px 24px;
  background: var(--color-surface);
  border: 1px solid var(--color-hairline);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-card);
  transition: transform 120ms ease, box-shadow 120ms ease;
}

.stats-card:hover {
  transform: translateY(-2px);
  box-shadow: var(--shadow-raised);
}

.stat-item {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 4px 8px;
}

.stat-icon {
  margin-top: 4px;
  font-size: 20px;
  color: var(--color-ink-muted);
}

.stat-icon.danger {
  color: var(--color-danger);
}

.stat-icon.warning {
  color: var(--color-warning);
}

.stat-label {
  font-size: 12px;
  color: var(--color-ink-muted);
}

.stat-value {
  margin-top: 4px;
  font-size: 28px;
  font-weight: 600;
  letter-spacing: -0.4px;
  line-height: 1.2;
  color: var(--color-ink);
}

.stat-value.danger {
  color: var(--color-danger);
}

.stat-value.warning {
  color: var(--color-warning);
}

.stat-sub {
  margin-top: 4px;
  font-size: 12px;
  color: var(--color-ink-disabled);
}

.stat-divider {
  width: 1px;
  height: 48px;
  background: var(--color-hairline);
}

.toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 12px;
  padding: 16px 20px;
}

.search-input {
  width: 240px;
}

.risk-select {
  width: 140px;
}

.toolbar-meta {
  margin-left: auto;
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  font-size: 12px;
  color: var(--color-ink-muted);
}

.table-panel {
  padding: 16px 20px 12px;
  transition: transform 120ms ease, box-shadow 120ms ease;
}

.table-panel:hover {
  transform: translateY(-2px);
  box-shadow: var(--shadow-raised);
}

.panel-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}

.panel-title {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  color: var(--color-ink);
}

.panel-meta {
  font-size: 12px;
  color: var(--color-ink-muted);
}

.product-cell {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
}

.product-name {
  font-size: 14px;
  font-weight: 500;
  color: var(--color-ink);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.product-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.platform-tag {
  flex-shrink: 0;
  font-size: 11px;
  font-weight: 500;
  color: var(--color-primary);
  background: var(--color-primary-subtle);
  border-radius: 4px;
  padding: 1px 6px;
}

.sku {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 12px;
  color: var(--color-ink-muted);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.risk-tag {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 44px;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 12px;
  font-weight: 600;
  line-height: 1.4;
}

.risk-tag.normal {
  color: var(--color-success);
  background: #ecfdf5;
}

.risk-tag.watch {
  color: var(--color-warning);
  background: #fffbeb;
}

.risk-tag.critical {
  color: var(--color-danger);
  background: #fef2f2;
}

.inventory-table :deep(.el-table__header th) {
  background: var(--color-surface-sunken);
  color: var(--color-ink-muted);
  font-size: 12px;
  font-weight: 600;
}

.inventory-table :deep(.el-table__row) {
  height: 56px;
}

.inventory-table :deep(.el-table__row.row-critical > td) {
  background: #fef2f2 !important;
}

.inventory-table :deep(.el-table__row.row-critical > td:first-child) {
  box-shadow: inset 3px 0 0 #dc2626;
}

.inventory-table :deep(.el-table__row.row-watch > td) {
  background: #fffbeb !important;
}

.inventory-table :deep(.el-table__row.row-watch > td:first-child) {
  box-shadow: inset 3px 0 0 #d97706;
}

.inventory-table :deep(.el-table__row.row-critical:hover > td),
.inventory-table :deep(.el-table__row.row-watch:hover > td) {
  filter: brightness(0.99);
}

.pager {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 12px 0 4px;
}

.pager-total {
  font-size: 12px;
  color: var(--color-ink-muted);
}

.dialog-product {
  margin: 0 0 16px;
  font-size: 14px;
  font-weight: 500;
  color: var(--color-ink-secondary);
}

.full-width {
  width: 100%;
}

.error-panel {
  padding: 8px;
}

@media (max-width: 900px) {
  .stats-card {
    grid-template-columns: 1fr;
  }

  .stat-divider {
    width: 100%;
    height: 1px;
  }

  .toolbar-meta {
    margin-left: 0;
    width: 100%;
  }

  .search-input,
  .risk-select {
    width: 100%;
  }
}

@media (prefers-reduced-motion: reduce) {
  .inventory-body,
  .stats-card,
  .table-panel {
    transition: none;
  }

  .stats-card:hover,
  .table-panel:hover {
    transform: none;
  }
}
</style>
