import axios, {
  type AxiosInstance,
  type AxiosResponse,
  type InternalAxiosRequestConfig,
} from 'axios'
import { ElMessage } from 'element-plus'
import type { ApiResponse } from '@/types/auth'
import router from '@/router'

const TOKEN_KEY = 'hpzx_access_token'

export function getStoredToken(): string | null {
  return localStorage.getItem(TOKEN_KEY)
}

export function setStoredToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token)
}

export function clearStoredToken(): void {
  localStorage.removeItem(TOKEN_KEY)
}

const request: AxiosInstance = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api/v1',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
})

request.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    const token = getStoredToken()
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => Promise.reject(error),
)

request.interceptors.response.use(
  (response: AxiosResponse<ApiResponse>) => {
    const payload = response.data

    // 非统一包装（如 blob）直接放行
    if (
      payload == null ||
      typeof payload !== 'object' ||
      !('code' in payload)
    ) {
      return response
    }

    if (payload.code === 200) {
      return response
    }

    const message = payload.message || '请求失败'
    ElMessage.error(message)
    return Promise.reject(new Error(message))
  },
  (error) => {
    const status = error.response?.status as number | undefined
    const detail =
      error.response?.data?.message ||
      error.response?.data?.detail ||
      error.message ||
      '网络异常'

    if (status === 401) {
      clearStoredToken()
      const current = router.currentRoute.value
      if (current.path !== '/login') {
        ElMessage.error('登录已过期，请重新登录')
        void router.replace({
          path: '/login',
          query: { redirect: current.fullPath },
        })
      } else {
        ElMessage.error(typeof detail === 'string' ? detail : '账号或密码错误')
      }
      return Promise.reject(error)
    }

    if (status === 429) {
      ElMessage.error(
        typeof detail === 'string' ? detail : '尝试过于频繁，请稍后再试',
      )
      return Promise.reject(error)
    }

    const text =
      typeof detail === 'string'
        ? detail
        : Array.isArray(detail)
          ? detail.map((d) => d.msg || String(d)).join('；')
          : '请求失败'
    ElMessage.error(text)
    return Promise.reject(error)
  },
)

export default request
