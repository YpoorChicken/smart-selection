<script setup lang="ts">
import { useRouter } from 'vue-router'
import { WarningFilled } from '@element-plus/icons-vue'
import EmptyState from '@/components/EmptyState.vue'

const router = useRouter()

function goHome() {
  void router.push('/')
}
</script>

<template>
  <div class="not-found">
    <EmptyState
      title="页面不存在"
      description="你访问的地址无效或已被移除，请返回运营看板继续工作。"
      :icon="WarningFilled"
    >
      <el-button type="primary" @click="goHome">返回首页</el-button>
    </EmptyState>
  </div>
</template>

<style scoped>
.not-found {
  min-height: calc(100vh - var(--header-height) - 48px);
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--color-surface);
  border: 1px solid var(--color-hairline);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-card);
}
</style>
