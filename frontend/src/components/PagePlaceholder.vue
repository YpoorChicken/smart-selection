<script setup lang="ts">
defineProps<{
  title: string
  description?: string
}>()
</script>

<template>
  <div class="page-card">
    <h1 class="page-title">{{ title }}</h1>
    <p class="page-muted">
      {{ description || '页面骨架已就绪，后续按原型完善业务内容。' }}
    </p>
    <slot />
  </div>
</template>
