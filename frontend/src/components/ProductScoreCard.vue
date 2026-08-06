<script setup>
import { computed } from 'vue'
import ScoreRing from './ScoreRing.vue'

const props = defineProps({
  /** 商品名 */
  name: { type: String, required: true },
  /** 展示价格，如 "$29.99" 或 "¥199" */
  price: { type: [String, Number], required: true },
  /**
   * 商品评分（如亚马逊星级 0–5）
   * 与蓝海指数分离：评分偏用户口碑，蓝海指数偏选品机会
   */
  rating: { type: Number, default: null },
  /** 评分满分，默认 5 */
  ratingMax: { type: Number, default: 5 },
  /** 蓝海指数 0–100 */
  blueOceanScore: { type: Number, default: null },
  /** 可选品类文案 */
  category: { type: String, default: '' },
  /** 是否可点击（列表决策卡） */
  interactive: { type: Boolean, default: true },
})

const emit = defineEmits(['click'])

const SCORE_HIGH = '#059669'
const SCORE_MID = '#D97706'
const SCORE_LOW = '#DC2626'
const MUTED = '#6B7280'

const formattedPrice = computed(() => {
  if (typeof props.price === 'number') {
    return `$${props.price.toFixed(2)}`
  }
  return String(props.price)
})

const ratingDisplay = computed(() => {
  if (props.rating == null || Number.isNaN(props.rating)) return '—'
  return props.rating.toFixed(1)
})

const ratingColor = computed(() => {
  if (props.rating == null || Number.isNaN(props.rating)) return MUTED
  const ratio = props.rating / props.ratingMax
  if (ratio >= 0.8) return SCORE_HIGH
  if (ratio >= 0.6) return SCORE_MID
  return SCORE_LOW
})

const blueOceanTier = computed(() => {
  const s = props.blueOceanScore
  if (s == null || Number.isNaN(s)) return { text: '暂无数据', color: MUTED }
  if (s >= 80) return { text: '高潜力', color: SCORE_HIGH }
  if (s >= 60) return { text: '建议复核', color: SCORE_MID }
  return { text: '风险较高', color: SCORE_LOW }
})

function onActivate() {
  if (!props.interactive) return
  emit('click')
}

function onKeydown(e) {
  if (!props.interactive) return
  if (e.key === 'Enter' || e.key === ' ') {
    e.preventDefault()
    emit('click')
  }
}
</script>

<template>
  <article
    class="product-score-card"
    :class="{ 'is-interactive': interactive }"
    :tabindex="interactive ? 0 : undefined"
    :role="interactive ? 'button' : undefined"
    @click="onActivate"
    @keydown="onKeydown"
  >
    <header class="product-score-card__header">
      <h3 class="product-score-card__name" :title="name">{{ name }}</h3>
      <span v-if="category" class="product-score-card__category">{{ category }}</span>
    </header>

    <div class="product-score-card__body">
      <ScoreRing :score="blueOceanScore" :size="88" />

      <dl class="product-score-card__metrics">
        <div class="metric">
          <dt class="metric__label">价格</dt>
          <dd class="metric__value metric__value--price">{{ formattedPrice }}</dd>
        </div>
        <div class="metric">
          <dt class="metric__label">评分</dt>
          <dd class="metric__value" :style="{ color: ratingColor }">
            <span class="metric__rating-num">{{ ratingDisplay }}</span>
            <span v-if="rating != null" class="metric__rating-max">/ {{ ratingMax }}</span>
          </dd>
        </div>
        <div class="metric">
          <dt class="metric__label">蓝海分层</dt>
          <dd class="metric__value metric__value--tier" :style="{ color: blueOceanTier.color }">
            {{ blueOceanTier.text }}
          </dd>
        </div>
      </dl>
    </div>
  </article>
</template>

<style scoped>
.product-score-card {
  --ink: #111827;
  --ink-muted: #6b7280;
  --surface: #ffffff;
  --hairline: #e5e7eb;
  --canvas-hover: #f9fafb;

  box-sizing: border-box;
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 16px;
  background: var(--surface);
  border: 1px solid var(--hairline);
  border-radius: 8px;
  box-shadow: 0 1px 2px rgba(17, 24, 39, 0.06);
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial,
    'Noto Sans SC', 'PingFang SC', 'Microsoft YaHei', sans-serif;
  transition:
    box-shadow 120ms ease-out,
    border-color 120ms ease-out,
    background-color 120ms ease-out;
}

.product-score-card.is-interactive {
  cursor: pointer;
}

.product-score-card.is-interactive:hover {
  border-color: #d1d5db;
  box-shadow: 0 4px 12px rgba(17, 24, 39, 0.08);
}

.product-score-card.is-interactive:focus-visible {
  outline: 2px solid #4f46e5;
  outline-offset: 2px;
}

.product-score-card__header {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
}

.product-score-card__name {
  margin: 0;
  font-size: 14px;
  font-weight: 600;
  line-height: 1.5;
  color: var(--ink);
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.product-score-card__category {
  font-size: 12px;
  font-weight: 400;
  line-height: 1.4;
  color: var(--ink-muted);
}

.product-score-card__body {
  display: flex;
  align-items: center;
  gap: 16px;
  min-width: 0;
}

.product-score-card__metrics {
  margin: 0;
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.metric {
  display: grid;
  grid-template-columns: 56px 1fr;
  align-items: baseline;
  gap: 8px;
}

.metric__label {
  margin: 0;
  font-size: 12px;
  font-weight: 400;
  line-height: 1.4;
  color: var(--ink-muted);
}

.metric__value {
  margin: 0;
  font-size: 14px;
  font-weight: 600;
  line-height: 1.5;
  color: var(--ink);
  font-variant-numeric: tabular-nums;
}

.metric__value--price {
  font-size: 16px;
  letter-spacing: -0.2px;
}

.metric__rating-max {
  margin-left: 2px;
  font-size: 12px;
  font-weight: 400;
  color: var(--ink-muted);
}

.metric__value--tier {
  font-size: 13px;
}

@media (prefers-reduced-motion: reduce) {
  .product-score-card {
    transition: none;
  }
}
</style>
