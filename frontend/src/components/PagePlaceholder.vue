<script setup lang="ts">
import PageHeader from '@/components/PageHeader.vue'
import EmptyState from '@/components/EmptyState.vue'

defineProps<{
  title: string
  description?: string
}>()
</script>

<template>
  <div class="placeholder-page">
    <PageHeader :title="title" :description="description" />
    <div class="page-card">
      <EmptyState
        :title="`${title}即将开放`"
        :description="description || '页面骨架已就绪，后续按原型完善业务内容。'"
      />
      <slot />
    </div>
  </div>
</template>
