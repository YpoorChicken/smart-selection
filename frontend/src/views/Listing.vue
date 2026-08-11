<script setup lang="ts">
/**
 * Design Read: B2B SaaS 运营工作台 Listing 双栏对比页——Indigo 点缀、高密度、对齐原型 06-listing。
 */
import { computed, onMounted, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Check,
  MagicStick,
  Refresh,
  TrophyBase,
} from '@element-plus/icons-vue'
import { getProduct, getProducts } from '@/api/products'
import {
  adoptListingVersion,
  completeAbTest,
  createAbTest,
  getAbTestHistory,
  getListingCurrent,
  getListingVersions,
  optimizeListing,
} from '@/api/listing'
import { useAuthStore } from '@/stores/auth'
import type { ProductListItem } from '@/types/products'
import type {
  AbTestRead,
  ListingVersion,
  OptimizeListingData,
} from '@/types/listing'

type LoadState = 'idle' | 'loading' | 'success' | 'empty' | 'error'
type RightState = 'empty' | 'loading' | 'ready'

const auth = useAuthStore()
const canWrite = computed(() => {
  const role = auth.user?.role
  return role === 'operator' || role === 'ops_lead'
})

const products = ref<ProductListItem[]>([])
const productsLoading = ref(false)
const selectedProductId = ref('')

const pageState = ref<LoadState>('idle')
const pageError = ref('')

const current = ref<ListingVersion | null>(null)
const isSynthetic = ref(false)
const productMeta = ref<{
  title: string
  platform: string
  external_id: string
} | null>(null)

const versions = ref<ListingVersion[]>([])
const creators = ref<Record<string, string>>({})

const rightState = ref<RightState>('empty')
const draft = ref<ListingVersion | null>(null)
const optimizeResult = ref<OptimizeListingData | null>(null)
const generating = ref(false)

const tone = ref('专业')
const site = ref('美国')
const coverageGoal = ref('≥90%')

const activeAbTest = ref<AbTestRead | null>(null)
const abCreating = ref(false)
const abCompleting = ref(false)

const platformLabel: Record<string, string> = {
  amazon: 'Amazon',
  shopee: 'Shopee',
  mock: 'Mock',
  fakestore: 'FakeStore',
}

function splitKeywords(raw: string | null | undefined): string[] {
  if (!raw) return []
  return raw
    .split(/[,，;；|/\n]+/)
    .map((s) => s.trim())
    .filter(Boolean)
}

function normalizeBullets(points: string[] | null | undefined): string[] {
  const list = (points || []).map((p) => String(p).trim()).filter(Boolean)
  while (list.length < 5) list.push('')
  return list.slice(0, 5)
}

const originalKeywords = computed(() => splitKeywords(current.value?.keywords))
const draftKeywords = computed(() => {
  if (optimizeResult.value) return optimizeResult.value.optimization.search_keywords
  return splitKeywords(draft.value?.keywords)
})

const keywordDiff = computed(() => {
  const left = new Set(originalKeywords.value.map((k) => k.toLowerCase()))
  const right = new Set(draftKeywords.value.map((k) => k.toLowerCase()))
  const removed = originalKeywords.value.filter((k) => !right.has(k.toLowerCase()))
  const added = draftKeywords.value.filter((k) => !left.has(k.toLowerCase()))
  const kept = originalKeywords.value.filter((k) => right.has(k.toLowerCase()))
  return { removed, added, kept }
})

const coverageText = computed(() => {
  const cov = draft.value?.keyword_coverage ?? optimizeResult.value?.version.keyword_coverage
  if (cov == null) return null
  const n = Number(cov)
  return Number.isFinite(n) ? `${n.toFixed(0)}%` : String(cov)
})

const reasonText = computed(
  () =>
    optimizeResult.value?.optimization.reason ||
    draft.value?.reason ||
    '',
)

const currentVersionLabel = computed(() => {
  if (!current.value) return '—'
  if (isSynthetic.value || current.value.version_no === 0) return '原文'
  return `v${current.value.version_no}`
})

function formatTime(iso: string): string {
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

function sourceLabel(source: string, isCurrent: boolean, isDraft = false): string {
  if (isDraft) return 'AI 草稿'
  if (isCurrent) return '当前版本'
  if (source === 'original') return '原始导入'
  if (source === 'adopted') return '已采纳'
  if (source === 'ai_generated') return 'AI 优化'
  return source
}

async function loadProducts() {
  productsLoading.value = true
  try {
    const data = await getProducts({ page: 1, page_size: 100 })
    products.value = data.items
    if (!selectedProductId.value && data.items.length) {
      selectedProductId.value = data.items[0].id
    }
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : '加载商品失败')
  } finally {
    productsLoading.value = false
  }
}

async function loadListing() {
  const id = selectedProductId.value
  if (!id) {
    pageState.value = 'empty'
    return
  }
  pageState.value = 'loading'
  pageError.value = ''
  rightState.value = 'empty'
  draft.value = null
  optimizeResult.value = null
  activeAbTest.value = null

  try {
    const [cur, vers, detail, abHist] = await Promise.all([
      getListingCurrent(id),
      getListingVersions(id),
      getProduct(id).catch(() => null),
      getAbTestHistory({ listing_id: id, status: 'running', page: 1, page_size: 1 }).catch(
        () => null,
      ),
    ])

    current.value = cur.version
    isSynthetic.value = cur.is_synthetic
    productMeta.value = {
      title: cur.product_title || detail?.title || cur.version.title,
      platform: cur.platform,
      external_id: cur.external_id,
    }
    versions.value = vers.items
    creators.value = vers.creators
    activeAbTest.value = abHist?.items?.[0] ?? null

    // 若有未采纳的最新 AI 稿，自动展示对比
    const latestAi = [...vers.items]
      .reverse()
      .find((v) => !v.is_current && v.source === 'ai_generated')
    if (latestAi) {
      draft.value = latestAi
      rightState.value = 'ready'
    }

    pageState.value = 'success'
  } catch (e) {
    pageState.value = 'error'
    pageError.value = e instanceof Error ? e.message : '加载 Listing 失败'
  }
}

async function handleGenerate() {
  if (!canWrite.value) {
    ElMessage.warning('仅运营或运营主管可生成优化稿')
    return
  }
  if (!selectedProductId.value) return

  generating.value = true
  rightState.value = 'loading'
  try {
    const data = await optimizeListing(selectedProductId.value)
    optimizeResult.value = data
    draft.value = data.version
    rightState.value = 'ready'
    ElMessage.success('AI 优化稿已生成')
    const vers = await getListingVersions(selectedProductId.value)
    versions.value = vers.items
    creators.value = vers.creators
  } catch (e) {
    rightState.value = draft.value ? 'ready' : 'empty'
    ElMessage.error(e instanceof Error ? e.message : '生成失败，原文未改动')
  } finally {
    generating.value = false
  }
}

async function handleDiscard() {
  draft.value = null
  optimizeResult.value = null
  rightState.value = 'empty'
}

async function handleAdopt(versionId?: string) {
  if (!canWrite.value) {
    ElMessage.warning('仅运营或运营主管可采纳版本')
    return
  }
  const vid = versionId || draft.value?.id
  if (!vid || !selectedProductId.value) return
  if (isSynthetic.value && vid === selectedProductId.value) {
    ElMessage.info('当前已是原文基线')
    return
  }

  try {
    await ElMessageBox.confirm(
      '采纳后将替换当前生效 Listing，并回写商品主文案。是否继续？',
      '采纳为新版本',
      {
        type: 'warning',
        confirmButtonText: '确认采纳',
        cancelButtonText: '取消',
      },
    )
  } catch {
    return
  }

  try {
    await adoptListingVersion(selectedProductId.value, vid)
    ElMessage.success('已采纳为当前版本')
    await loadListing()
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : '采纳失败')
  }
}

async function handleRollback(version: ListingVersion) {
  if (version.is_current) {
    ElMessage.info('该版本已是当前生效稿')
    return
  }
  await handleAdopt(version.id)
}

async function handleCreateAbTest() {
  if (!canWrite.value) {
    ElMessage.warning('仅运营或运营主管可发起 A/B 测试')
    return
  }
  if (!selectedProductId.value) return
  abCreating.value = true
  try {
    const data = await createAbTest({
      listing_id: selectedProductId.value,
      version_a_id: isSynthetic.value ? undefined : current.value?.id,
      metric: 'manual',
    })
    activeAbTest.value = data.ab_test
    draft.value = data.ab_test.version_b
    if (data.optimization) {
      optimizeResult.value = {
        product_id: selectedProductId.value,
        listing_id: selectedProductId.value,
        parent_version_id: data.ab_test.version_a_id,
        version: data.ab_test.version_b!,
        optimization: data.optimization,
        keyword_seed: [],
        competitor_titles: [],
        mode: data.mode,
        generated_at: data.generated_at,
      }
    }
    rightState.value = 'ready'
    ElMessage.success('A/B 测试已创建，B 版为 AI 生成稿')
    const vers = await getListingVersions(selectedProductId.value)
    versions.value = vers.items
    creators.value = vers.creators
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : '创建 A/B 失败')
  } finally {
    abCreating.value = false
  }
}

async function handlePickWinner(winner: 'a' | 'b') {
  if (!activeAbTest.value) return
  abCompleting.value = true
  try {
    await completeAbTest(activeAbTest.value.id, { winner, adopt: true })
    ElMessage.success(`已选择 ${winner.toUpperCase()} 为胜出并采纳`)
    await loadListing()
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : '完成 A/B 失败')
  } finally {
    abCompleting.value = false
  }
}

function previewVersion(version: ListingVersion) {
  if (version.is_current) {
    draft.value = null
    optimizeResult.value = null
    rightState.value = 'empty'
    return
  }
  draft.value = version
  optimizeResult.value = null
  rightState.value = 'ready'
}

watch(selectedProductId, () => {
  void loadListing()
})

onMounted(async () => {
  await loadProducts()
  if (selectedProductId.value) await loadListing()
  else pageState.value = 'empty'
})
</script>

<template>
  <div class="listing-page">
    <!-- 工具条 -->
    <section class="card toolbar">
      <div class="toolbar-left">
        <el-select
          v-model="selectedProductId"
          filterable
          placeholder="选择商品"
          :loading="productsLoading"
          class="product-select"
        >
          <el-option
            v-for="p in products"
            :key="p.id"
            :label="p.title"
            :value="p.id"
          />
        </el-select>
        <template v-if="productMeta">
          <span class="tag platform">{{ platformLabel[productMeta.platform] || productMeta.platform }}</span>
          <span class="meta-text">ASIN: {{ productMeta.external_id }}</span>
          <span class="meta-text">当前版本 {{ currentVersionLabel }}</span>
        </template>
      </div>
      <div class="toolbar-right">
        <el-button
          v-if="canWrite"
          :loading="abCreating"
          @click="handleCreateAbTest"
        >
          <el-icon><TrophyBase /></el-icon>
          发起 A/B 测试
        </el-button>
      </div>
    </section>

    <!-- A/B 进行中条 -->
    <section v-if="activeAbTest" class="card ab-banner">
      <div class="ab-info">
        <strong>A/B 测试进行中</strong>
        <span>A = 基线 · B = AI 对照稿 · 指标 {{ activeAbTest.metric }}</span>
      </div>
      <div class="ab-actions">
        <el-button
          :loading="abCompleting"
          @click="handlePickWinner('a')"
        >
          胜出 A（基线）
        </el-button>
        <el-button
          type="primary"
          :loading="abCompleting"
          @click="handlePickWinner('b')"
        >
          胜出 B（AI）并采纳
        </el-button>
      </div>
    </section>

    <!-- 生成参数条 -->
    <section class="card gen-bar">
      <div class="gen-controls">
        <label>
          语气
          <el-select v-model="tone" size="small" style="width: 100px">
            <el-option label="专业" value="专业" />
            <el-option label="促销" value="促销" />
            <el-option label="亲和" value="亲和" />
          </el-select>
        </label>
        <label>
          站点
          <el-select v-model="site" size="small" style="width: 100px">
            <el-option label="美国" value="美国" />
            <el-option label="英国" value="英国" />
            <el-option label="日本" value="日本" />
          </el-select>
        </label>
        <label>
          关键词覆盖目标
          <el-select v-model="coverageGoal" size="small" style="width: 110px">
            <el-option label="≥90%" value="≥90%" />
            <el-option label="≥80%" value="≥80%" />
            <el-option label="≥70%" value="≥70%" />
          </el-select>
        </label>
      </div>
      <div class="gen-action">
        <span class="hint">预计 20–40 秒</span>
        <el-button
          type="primary"
          :loading="generating"
          :disabled="!canWrite || !selectedProductId || pageState === 'loading'"
          @click="handleGenerate"
        >
          <el-icon v-if="!generating"><MagicStick /></el-icon>
          生成 AI 优化稿
        </el-button>
      </div>
    </section>

    <!-- 三态 -->
    <el-alert
      v-if="pageState === 'error'"
      type="error"
      :title="pageError || '加载失败'"
      show-icon
      :closable="false"
      class="state-alert"
    >
      <el-button size="small" @click="loadListing">重试</el-button>
    </el-alert>

    <div v-else-if="pageState === 'empty'" class="card empty-box">
      <p>暂无商品，请先在商品管理同步数据</p>
    </div>

    <div v-else-if="pageState === 'loading'" class="card compare-card">
      <el-skeleton :rows="10" animated />
    </div>

    <!-- 双栏对比 -->
    <section v-else class="card compare-card">
      <div class="compare-head">
        <div class="col-head left-head">
          <span class="badge badge-original">原版</span>
        </div>
        <div class="col-head right-head">
          <span class="badge badge-ai">AI 优化版</span>
          <template v-if="rightState === 'ready'">
            <span class="ok-text">
              <el-icon><Check /></el-icon>
              优化完成
              <template v-if="coverageText"> · 关键词覆盖率 {{ coverageText }}</template>
            </span>
            <el-button
              link
              type="primary"
              :loading="generating"
              :disabled="!canWrite"
              @click="handleGenerate"
            >
              <el-icon><Refresh /></el-icon>
              重新生成
            </el-button>
          </template>
        </div>
      </div>

      <!-- 标题 -->
      <div class="compare-row">
        <div class="field-label">商品标题</div>
        <div class="row-cols">
          <div class="col col-left">
            <p class="title-text">{{ current?.title || '—' }}</p>
          </div>
          <div class="col col-right">
            <template v-if="rightState === 'ready'">
              <p class="title-text">{{ draft?.title || optimizeResult?.optimization.title }}</p>
            </template>
            <template v-else-if="rightState === 'loading'">
              <el-skeleton :rows="2" animated />
            </template>
            <p v-else class="placeholder">尚未生成优化稿</p>
          </div>
        </div>
      </div>

      <!-- 卖点 -->
      <div class="compare-row">
        <div class="field-label">五点卖点</div>
        <div class="row-cols">
          <div class="col col-left">
            <ol class="bullets">
              <li
                v-for="(b, i) in normalizeBullets(current?.bullet_points)"
                :key="`l-${i}`"
              >
                <span class="idx">{{ i + 1 }}</span>
                <span>{{ b || '—' }}</span>
              </li>
            </ol>
          </div>
          <div class="col col-right">
            <template v-if="rightState === 'ready'">
              <ol class="bullets bullets-ai">
                <li
                  v-for="(b, i) in normalizeBullets(
                    draft?.bullet_points || optimizeResult?.optimization.bullet_points,
                  )"
                  :key="`r-${i}`"
                >
                  <span class="idx">{{ i + 1 }}</span>
                  <span>{{ b || '—' }}</span>
                </li>
              </ol>
            </template>
            <template v-else-if="rightState === 'loading'">
              <el-skeleton :rows="5" animated />
            </template>
            <p v-else class="placeholder">尚未生成优化稿</p>
          </div>
        </div>
      </div>

      <!-- 描述 -->
      <div class="compare-row">
        <div class="field-label">商品描述</div>
        <div class="row-cols">
          <div class="col col-left">
            <p class="desc">{{ current?.description || '—' }}</p>
            <div class="char-count">
              {{ (current?.description || '').length }} / 2000
            </div>
          </div>
          <div class="col col-right">
            <template v-if="rightState === 'ready'">
              <p class="desc">
                {{ draft?.description || optimizeResult?.optimization.description }}
              </p>
              <div class="char-count">
                {{
                  (
                    draft?.description ||
                    optimizeResult?.optimization.description ||
                    ''
                  ).length
                }}
                / 2000
              </div>
            </template>
            <template v-else-if="rightState === 'loading'">
              <el-skeleton :rows="4" animated />
            </template>
            <p v-else class="placeholder">尚未生成优化稿</p>
          </div>
        </div>
      </div>

      <!-- 关键词 -->
      <div class="compare-row">
        <div class="field-label">关键词</div>
        <div class="row-cols">
          <div class="col col-left">
            <div class="kw-wrap">
              <template v-if="rightState === 'ready'">
                <span
                  v-for="k in keywordDiff.kept"
                  :key="`k-${k}`"
                  class="kw kw-kept"
                >{{ k }}</span>
                <span
                  v-for="k in keywordDiff.removed"
                  :key="`rm-${k}`"
                  class="kw kw-removed"
                >
                  <s>{{ k }}</s>
                  <em>删除</em>
                </span>
              </template>
              <template v-else>
                <span
                  v-for="k in originalKeywords"
                  :key="`o-${k}`"
                  class="kw kw-kept"
                >{{ k }}</span>
                <span v-if="!originalKeywords.length" class="placeholder">暂无关键词</span>
              </template>
            </div>
          </div>
          <div class="col col-right">
            <template v-if="rightState === 'ready'">
              <div class="kw-wrap">
                <span
                  v-for="k in keywordDiff.kept"
                  :key="`rk-${k}`"
                  class="kw kw-kept"
                >{{ k }}</span>
                <span
                  v-for="k in keywordDiff.added"
                  :key="`ad-${k}`"
                  class="kw kw-added"
                >
                  {{ k }}
                  <em>新增</em>
                </span>
              </div>
            </template>
            <template v-else-if="rightState === 'loading'">
              <el-skeleton :rows="2" animated />
            </template>
            <p v-else class="placeholder">尚未生成优化稿</p>
          </div>
        </div>
      </div>

      <!-- 优化理由 -->
      <div v-if="rightState === 'ready' && reasonText" class="reason-card">
        <h4>优化理由</h4>
        <p>{{ reasonText }}</p>
      </div>

      <!-- 底栏操作 -->
      <div v-if="rightState === 'ready'" class="compare-footer">
        <el-button @click="handleDiscard">放弃本次结果</el-button>
        <el-button
          type="primary"
          :disabled="!canWrite || !draft?.id"
          @click="handleAdopt()"
        >
          采纳为新版本
        </el-button>
      </div>
    </section>

    <!-- 版本时间线 -->
    <section class="card timeline-card">
      <div class="timeline-head">
        <h3>版本历史</h3>
        <span class="muted">点击历史版本可预览；「回滚」恢复为当前生效</span>
      </div>
      <el-timeline v-if="versions.length" class="version-timeline">
        <el-timeline-item
          v-for="v in versions"
          :key="v.id"
          :type="v.is_current ? 'primary' : undefined"
          :hollow="!v.is_current && v.source === 'ai_generated'"
          :timestamp="formatTime(v.created_at)"
          placement="top"
        >
          <div
            class="tl-node"
            :class="{ current: v.is_current, draft: draft?.id === v.id }"
            @click="previewVersion(v)"
          >
            <div class="tl-title">
              <strong>v{{ v.version_no }}</strong>
              <span>{{ sourceLabel(v.source, v.is_current) }}</span>
              <el-tag v-if="v.is_current" size="small" type="primary" effect="plain">
                当前
              </el-tag>
              <el-tag
                v-else-if="draft?.id === v.id"
                size="small"
                type="info"
                effect="plain"
              >
                预览中
              </el-tag>
            </div>
            <div class="tl-meta">
              {{ creators[v.created_by || ''] || '系统' }}
              <el-button
                v-if="!v.is_current && canWrite"
                link
                type="primary"
                size="small"
                @click.stop="handleRollback(v)"
              >
                回滚为此版本
              </el-button>
            </div>
          </div>
        </el-timeline-item>
        <el-timeline-item
          v-if="draft && !versions.some((v) => v.id === draft?.id)"
          type="primary"
          hollow
          timestamp="刚刚"
          placement="top"
        >
          <div class="tl-node draft">
            <div class="tl-title">
              <strong>v{{ (versions.at(-1)?.version_no || 0) + 1 }}</strong>
              <span>AI 草稿</span>
            </div>
          </div>
        </el-timeline-item>
      </el-timeline>
      <p v-else class="muted empty-tl">暂无版本记录，生成优化稿后将出现时间线</p>
    </section>
  </div>
</template>

<style scoped>
.listing-page {
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
  flex-wrap: wrap;
  min-width: 0;
}

.product-select {
  width: min(420px, 100%);
}

.tag.platform {
  display: inline-flex;
  align-items: center;
  height: 22px;
  padding: 0 8px;
  border-radius: 4px;
  background: #fff7ed;
  color: #c2410c;
  font-size: 12px;
  font-weight: 600;
}

.meta-text {
  color: #6b7280;
  font-size: 13px;
}

.ab-banner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  background: #eef2ff;
  border-color: #c7d2fe;
  flex-wrap: wrap;
}

.ab-info {
  display: flex;
  flex-direction: column;
  gap: 4px;
  font-size: 13px;
  color: #374151;
}

.ab-actions {
  display: flex;
  gap: 8px;
}

.gen-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
}

.gen-controls {
  display: flex;
  gap: 16px;
  flex-wrap: wrap;
  align-items: center;
}

.gen-controls label {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: #374151;
}

.gen-action {
  display: flex;
  align-items: center;
  gap: 12px;
}

.hint {
  font-size: 12px;
  color: #9ca3af;
}

.compare-card {
  padding: 0;
  overflow: hidden;
}

.compare-head {
  display: grid;
  grid-template-columns: 1fr 1fr;
  border-bottom: 1px solid #e5e7eb;
}

.col-head {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px 20px;
  min-height: 52px;
}

.right-head {
  border-left: 1px solid #e5e7eb;
  justify-content: flex-start;
}

.badge {
  display: inline-flex;
  align-items: center;
  height: 24px;
  padding: 0 10px;
  border-radius: 4px;
  font-size: 12px;
  font-weight: 600;
}

.badge-original {
  background: #f3f4f6;
  color: #4b5563;
}

.badge-ai {
  background: linear-gradient(90deg, #4f46e5, #4338ca);
  color: #fff;
}

.ok-text {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  color: #059669;
  font-size: 13px;
  margin-left: auto;
}

.compare-row {
  border-bottom: 1px solid #e5e7eb;
}

.compare-row:last-of-type {
  border-bottom: none;
}

.field-label {
  padding: 10px 20px 0;
  font-size: 12px;
  font-weight: 600;
  color: #6b7280;
}

.row-cols {
  display: grid;
  grid-template-columns: 1fr 1fr;
}

.col {
  padding: 12px 20px 16px;
  min-height: 72px;
}

.col-left {
  background: #f9fafb;
}

.col-right {
  border-left: 1px solid #e5e7eb;
  background: #fff;
}

.title-text {
  margin: 0;
  font-size: 15px;
  font-weight: 600;
  color: #111827;
  line-height: 1.5;
}

.bullets {
  margin: 0;
  padding: 0;
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.bullets li {
  display: flex;
  gap: 8px;
  font-size: 13px;
  color: #374151;
  line-height: 1.5;
}

.bullets .idx {
  flex: 0 0 20px;
  height: 20px;
  border-radius: 4px;
  background: #e5e7eb;
  color: #4b5563;
  font-size: 12px;
  font-weight: 600;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.bullets-ai li {
  padding: 8px 10px;
  border-radius: 6px;
  background: #eef2ff;
}

.bullets-ai .idx {
  background: #4f46e5;
  color: #fff;
}

.desc {
  margin: 0;
  font-size: 13px;
  color: #374151;
  line-height: 1.65;
  white-space: pre-wrap;
}

.char-count {
  margin-top: 8px;
  text-align: right;
  font-size: 12px;
  color: #9ca3af;
}

.kw-wrap {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.kw {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  height: 24px;
  padding: 0 8px;
  border-radius: 4px;
  font-size: 12px;
}

.kw-kept {
  background: #f3f4f6;
  color: #4b5563;
}

.kw-added {
  background: #ecfdf5;
  color: #059669;
  border: 1px solid #a7f3d0;
}

.kw-added em,
.kw-removed em {
  font-style: normal;
  font-size: 11px;
  opacity: 0.85;
}

.kw-removed {
  background: #fef2f2;
  color: #dc2626;
  border: 1px solid #fecaca;
}

.kw-removed s {
  text-decoration: line-through;
}

.placeholder {
  margin: 0;
  color: #9ca3af;
  font-size: 13px;
}

.reason-card {
  margin: 0 20px 16px;
  padding: 14px 16px;
  border-radius: 8px;
  background: #f9fafb;
  border: 1px solid #e5e7eb;
}

.reason-card h4 {
  margin: 0 0 8px;
  font-size: 14px;
  font-weight: 600;
  color: #111827;
}

.reason-card p {
  margin: 0;
  font-size: 13px;
  color: #374151;
  line-height: 1.6;
}

.compare-footer {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  padding: 12px 20px 16px;
  border-top: 1px solid #e5e7eb;
}

.timeline-card h3 {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  color: #111827;
}

.timeline-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
  flex-wrap: wrap;
}

.muted {
  color: #6b7280;
  font-size: 12px;
}

.tl-node {
  cursor: pointer;
  padding: 4px 0;
}

.tl-node.current .tl-title strong {
  color: #4f46e5;
}

.tl-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: #374151;
}

.tl-meta {
  margin-top: 4px;
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 12px;
  color: #6b7280;
}

.empty-box,
.empty-tl {
  text-align: center;
  padding: 24px;
  color: #6b7280;
}

.state-alert {
  margin-bottom: 0;
}

@media (max-width: 768px) {
  .compare-head,
  .row-cols {
    grid-template-columns: 1fr;
  }

  .col-right,
  .right-head {
    border-left: none;
    border-top: 1px solid #e5e7eb;
  }
}
</style>
