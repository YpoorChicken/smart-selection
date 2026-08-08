<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  Box,
  DataAnalysis,
  Document,
  Grid,
  Goods,
  Monitor,
  Warning,
  SwitchButton,
} from '@element-plus/icons-vue'
import { useAuthStore } from '@/stores/auth'

interface NavItem {
  path: string
  label: string
  icon: typeof Grid
}

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

/** 菜单固定 7 项，顺序不可变 */
const navItems: NavItem[] = [
  { path: '/', label: '运营看板', icon: Grid },
  { path: '/products', label: '商品管理', icon: Goods },
  { path: '/trends', label: '市场趋势', icon: DataAnalysis },
  { path: '/selections', label: '选品推荐', icon: Box },
  { path: '/competitors', label: '竞品监控', icon: Monitor },
  { path: '/listing', label: 'Listing 优化', icon: Document },
  { path: '/inventory', label: '库存预警', icon: Warning },
]

const breadcrumbs = computed(() => {
  const crumbs = (route.meta.breadcrumb as string[] | undefined) || []
  if (crumbs.length > 0) return crumbs
  const title = (route.meta.title as string | undefined) || '工作台'
  return [title]
})

function isActive(path: string): boolean {
  if (path === '/') return route.path === '/'
  return route.path === path || route.path.startsWith(`${path}/`)
}

async function handleLogout() {
  auth.logout()
  await router.replace('/login')
}
</script>

<template>
  <el-container class="app-shell">
    <el-aside class="app-sidebar" width="240px">
      <div class="brand">
        <div class="brand-mark" aria-hidden="true">H</div>
        <div class="brand-text">
          <div class="brand-title">华普智选</div>
          <div class="brand-sub">跨境智能运营</div>
        </div>
      </div>

      <nav class="nav-list" aria-label="主导航">
        <router-link
          v-for="item in navItems"
          :key="item.path"
          :to="item.path"
          class="nav-item"
          :class="{ active: isActive(item.path) }"
        >
          <el-icon class="nav-icon"><component :is="item.icon" /></el-icon>
          <span class="nav-label">{{ item.label }}</span>
        </router-link>
      </nav>

      <div class="sidebar-footer">
        <el-button
          class="logout-btn"
          text
          :icon="SwitchButton"
          @click="handleLogout"
        >
          退出登录
        </el-button>
      </div>
    </el-aside>

    <el-container class="app-main-wrap">
      <el-header class="app-header" height="56px">
        <el-breadcrumb separator="/">
          <el-breadcrumb-item :to="{ path: '/' }">首页</el-breadcrumb-item>
          <el-breadcrumb-item
            v-for="(crumb, index) in breadcrumbs"
            :key="`${crumb}-${index}`"
          >
            {{ crumb }}
          </el-breadcrumb-item>
        </el-breadcrumb>

        <div class="header-user">
          <el-avatar :size="32" class="user-avatar">
            {{ auth.avatarText }}
          </el-avatar>
          <span class="user-name">{{ auth.displayName }}</span>
          <el-button link type="primary" @click="handleLogout">退出</el-button>
        </div>
      </el-header>

      <el-main class="app-main">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<style scoped>
.app-shell {
  min-height: 100vh;
  background: var(--color-canvas);
}

.app-sidebar {
  display: flex;
  flex-direction: column;
  background: var(--color-sidebar);
  color: var(--color-sidebar-text);
  border-right: 1px solid rgba(255, 255, 255, 0.06);
}

.brand {
  display: flex;
  align-items: center;
  gap: 12px;
  height: 64px;
  padding: 0 16px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
}

.brand-mark {
  width: 32px;
  height: 32px;
  border-radius: 6px;
  background: var(--color-primary);
  color: #fff;
  font-size: 14px;
  font-weight: 700;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.brand-title {
  font-size: 16px;
  font-weight: 600;
  color: #fff;
  line-height: 1.3;
}

.brand-sub {
  margin-top: 2px;
  font-size: 11px;
  color: var(--color-ink-disabled);
  line-height: 1.3;
}

.nav-list {
  flex: 1;
  padding: 12px 8px;
  display: flex;
  flex-direction: column;
  gap: 4px;
  overflow-y: auto;
}

.nav-item {
  position: relative;
  display: flex;
  align-items: center;
  gap: 10px;
  height: 40px;
  padding: 0 12px 0 16px;
  border-radius: 6px;
  color: var(--color-sidebar-text);
  transition: background-color 160ms ease, color 160ms ease;
}

.nav-item:hover {
  background: var(--color-sidebar-hover);
  color: #fff;
}

.nav-item.active {
  background: rgba(79, 70, 229, 0.15);
  color: var(--color-sidebar-text-active);
}

.nav-item.active::before {
  content: '';
  position: absolute;
  left: 0;
  top: 8px;
  bottom: 8px;
  width: 3px;
  border-radius: 0 2px 2px 0;
  background: var(--color-primary);
}

.nav-icon {
  font-size: 18px;
}

.nav-label {
  font-size: 14px;
  font-weight: 500;
}

.sidebar-footer {
  padding: 12px 8px 16px;
  border-top: 1px solid rgba(255, 255, 255, 0.06);
}

.logout-btn {
  width: 100%;
  justify-content: flex-start;
  color: var(--color-sidebar-text) !important;
  height: 40px;
  padding-left: 16px;
}

.logout-btn:hover {
  color: #fff !important;
  background: var(--color-sidebar-hover);
}

.app-main-wrap {
  min-width: 0;
}

.app-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 0 24px;
  background: var(--color-surface);
  border-bottom: 1px solid var(--color-hairline);
}

.header-user {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-left: auto;
  flex-shrink: 0;
}

.user-avatar {
  background: var(--color-primary-subtle);
  color: var(--color-primary);
  font-size: 13px;
  font-weight: 600;
}

.user-name {
  font-size: 14px;
  color: var(--color-ink-secondary);
  max-width: 140px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.app-main {
  padding: 24px;
  background: var(--color-canvas);
}
</style>
