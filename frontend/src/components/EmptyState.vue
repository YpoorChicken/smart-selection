<script setup lang="ts">
import { Box } from '@element-plus/icons-vue'

withDefaults(
  defineProps<{
    title: string
    description?: string
    icon?: object
  }>(),
  {
    description: '',
    icon: () => Box,
  },
)
</script>

<template>
  <div class="empty-state" role="status">
    <el-icon class="empty-icon" :size="32">
      <component :is="icon" />
    </el-icon>
    <p class="empty-title">{{ title }}</p>
    <p v-if="description" class="empty-desc">{{ description }}</p>
    <div v-if="$slots.default" class="empty-actions">
      <slot />
    </div>
  </div>
</template>

<style scoped>
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 48px 24px;
  text-align: center;
}

.empty-icon {
  color: var(--color-ink-disabled);
  margin-bottom: 4px;
}

.empty-title {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  color: var(--color-ink-secondary);
}

.empty-desc {
  margin: 0;
  max-width: 360px;
  font-size: 12px;
  line-height: 1.5;
  color: var(--color-ink-muted);
}

.empty-actions {
  margin-top: 12px;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  justify-content: center;
}
</style>
