import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'
import { getStoredToken } from '@/api/request'

const AppShell = () => import('@/layouts/AppShell.vue')

const routes: RouteRecordRaw[] = [
  {
    path: '/login',
    name: 'login',
    component: () => import('@/views/LoginView.vue'),
    meta: { public: true, title: '登录' },
  },
  {
    path: '/',
    component: AppShell,
    children: [
      {
        path: '',
        name: 'dashboard',
        component: () => import('@/views/DashboardView.vue'),
        meta: { title: '运营看板', breadcrumb: ['运营看板'] },
      },
      {
        path: 'products',
        name: 'products',
        component: () => import('@/views/ProductsView.vue'),
        meta: { title: '商品管理', breadcrumb: ['商品管理'] },
      },
      {
        path: 'trends',
        name: 'trends',
        component: () => import('@/views/TrendsView.vue'),
        meta: { title: '市场趋势', breadcrumb: ['选品分析', '市场趋势'] },
      },
      {
        path: 'selections',
        name: 'selections',
        component: () => import('@/views/SelectionsView.vue'),
        meta: { title: '选品推荐', breadcrumb: ['选品推荐'] },
      },
      {
        path: 'competitors',
        name: 'competitors',
        component: () => import('@/views/CompetitorsView.vue'),
        meta: { title: '竞品监控', breadcrumb: ['竞品监控'] },
      },
      {
        path: 'listing',
        name: 'listing',
        component: () => import('@/views/ListingView.vue'),
        meta: { title: 'Listing 优化', breadcrumb: ['Listing 优化'] },
      },
      {
        path: 'inventory',
        name: 'inventory',
        component: () => import('@/views/InventoryView.vue'),
        meta: { title: '库存预警', breadcrumb: ['库存预警'] },
      },
      {
        path: '404',
        name: 'not-found',
        component: () => import('@/views/NotFoundView.vue'),
        meta: { title: '页面不存在', breadcrumb: ['404'] },
      },
    ],
  },
  {
    path: '/:pathMatch(.*)*',
    name: 'catch-all',
    redirect: '/404',
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach((to) => {
  const isPublic = Boolean(to.meta.public)
  const token = getStoredToken()

  if (!isPublic && !token) {
    return {
      path: '/login',
      query: { redirect: to.fullPath },
    }
  }

  if (to.path === '/login' && token) {
    return { path: '/' }
  }

  const title = (to.meta.title as string | undefined) || '华普智选'
  document.title = `${title} · 华普智选`
  return true
})

export default router
