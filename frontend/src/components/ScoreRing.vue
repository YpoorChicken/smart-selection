<script setup>
import { computed } from 'vue'

const props = defineProps({
  /** 蓝海指数 0–100；null / undefined 为缺数 */
  score: { type: Number, default: null },
  /** 默认 88；紧凑 72 */
  size: { type: Number, default: 88 },
  label: { type: String, default: '蓝海指数' },
})

const SCORE_HIGH = '#059669'
const SCORE_MID = '#D97706'
const SCORE_LOW = '#DC2626'
const TRACK = '#E5E7EB'
const MUTED = '#6B7280'

const clamped = computed(() => {
  if (props.score == null || Number.isNaN(props.score)) return null
  return Math.min(100, Math.max(0, Math.round(props.score)))
})

const strokeColor = computed(() => {
  const s = clamped.value
  if (s == null) return TRACK
  if (s >= 80) return SCORE_HIGH
  if (s >= 60) return SCORE_MID
  return SCORE_LOW
})

const tierLabel = computed(() => {
  const s = clamped.value
  if (s == null) return '暂无数据'
  if (s >= 80) return '高潜力'
  if (s >= 60) return '建议复核'
  return '风险较高'
})

const strokeWidth = computed(() => (props.size <= 72 ? 6 : 8))

const radius = computed(() => (props.size - strokeWidth.value) / 2)

const circumference = computed(() => 2 * Math.PI * radius.value)

const dashOffset = computed(() => {
  const s = clamped.value
  if (s == null) return circumference.value
  return circumference.value * (1 - s / 100)
})

const ariaLabel = computed(() => {
  if (clamped.value == null) return `${props.label}暂无数据`
  return `${props.label} ${clamped.value} 分，${tierLabel.value}`
})

const displayValue = computed(() => (clamped.value == null ? '—' : String(clamped.value)))
</script>

<template>
  <div
    class="score-ring"
    role="img"
    :aria-label="ariaLabel"
    :style="{ width: `${size}px`, height: `${size}px` }"
  >
    <svg
      class="score-ring__svg"
      :width="size"
      :height="size"
      :viewBox="`0 0 ${size} ${size}`"
      aria-hidden="true"
    >
      <circle
        class="score-ring__track"
        :cx="size / 2"
        :cy="size / 2"
        :r="radius"
        fill="none"
        :stroke="TRACK"
        :stroke-width="strokeWidth"
      />
      <circle
        class="score-ring__arc"
        :cx="size / 2"
        :cy="size / 2"
        :r="radius"
        fill="none"
        :stroke="strokeColor"
        :stroke-width="strokeWidth"
        stroke-linecap="round"
        :stroke-dasharray="circumference"
        :stroke-dashoffset="dashOffset"
        :transform="`rotate(-90 ${size / 2} ${size / 2})`"
      />
    </svg>
    <div class="score-ring__center">
      <span
        class="score-ring__value"
        :style="{ color: clamped == null ? MUTED : strokeColor }"
      >
        {{ displayValue }}
      </span>
      <span class="score-ring__label">{{ label }}</span>
    </div>
  </div>
</template>

<style scoped>
.score-ring {
  position: relative;
  flex-shrink: 0;
}

.score-ring__svg {
  display: block;
}

.score-ring__arc {
  transition: stroke-dashoffset 240ms ease-out;
}

.score-ring__center {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  pointer-events: none;
}

.score-ring__value {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial,
    'Noto Sans SC', 'PingFang SC', 'Microsoft YaHei', sans-serif;
  font-size: 28px;
  font-weight: 600;
  line-height: 1.2;
  letter-spacing: -0.4px;
}

.score-ring__label {
  margin-top: 2px;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial,
    'Noto Sans SC', 'PingFang SC', 'Microsoft YaHei', sans-serif;
  font-size: 11px;
  font-weight: 500;
  line-height: 1.3;
  letter-spacing: 0.2px;
  color: #6b7280;
}

@media (prefers-reduced-motion: reduce) {
  .score-ring__arc {
    transition: none;
  }
}
</style>
