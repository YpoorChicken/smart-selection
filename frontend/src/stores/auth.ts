import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { fetchMeApi, loginApi, registerApi } from '@/api/auth'
import {
  clearStoredToken,
  getStoredToken,
  setStoredToken,
} from '@/api/request'
import type { LoginPayload, RegisterPayload, UserInfo } from '@/types/auth'

const USER_KEY = 'hpzx_user'

function readStoredUser(): UserInfo | null {
  const raw = localStorage.getItem(USER_KEY)
  if (!raw) return null
  try {
    return JSON.parse(raw) as UserInfo
  } catch {
    return null
  }
}

export const useAuthStore = defineStore('auth', () => {
  const token = ref<string | null>(getStoredToken())
  const user = ref<UserInfo | null>(readStoredUser())
  const sessionSynced = ref(false)
  let syncAttempted = false
  let syncing: Promise<void> | null = null

  const isAuthenticated = computed(() => Boolean(token.value))
  const displayName = computed(
    () => user.value?.display_name || user.value?.email || '未登录',
  )
  const avatarText = computed(() => {
    const name = displayName.value
    return name ? name.slice(0, 1) : '?'
  })

  function persistUser(next: UserInfo | null) {
    user.value = next
    if (next) {
      localStorage.setItem(USER_KEY, JSON.stringify(next))
    } else {
      localStorage.removeItem(USER_KEY)
    }
  }

  async function login(payload: LoginPayload) {
    const result = await loginApi(payload)
    token.value = result.access_token
    setStoredToken(result.access_token)
    persistUser(result.user)
    sessionSynced.value = true
    return result
  }

  async function register(payload: RegisterPayload) {
    const result = await registerApi(payload)
    if ('access_token' in result && result.access_token) {
      token.value = result.access_token
      setStoredToken(result.access_token)
      persistUser(result.user)
      sessionSynced.value = true
      return result
    }
    persistUser(result as UserInfo)
    return result
  }

  async function hydrate() {
    if (!token.value) {
      persistUser(null)
      sessionSynced.value = false
      return
    }
    try {
      const me = await fetchMeApi()
      persistUser(me)
      sessionSynced.value = true
    } catch (err) {
      const status = (err as { response?: { status?: number } })?.response?.status
      // 仅鉴权失败时清会话；网络/5xx 保留本地用户，避免误登出
      if (status === 401) {
        logout()
      }
    }
  }

  async function ensureSession() {
    if (!token.value || sessionSynced.value || syncAttempted) return
    if (!syncing) {
      syncAttempted = true
      syncing = hydrate().finally(() => {
        syncing = null
      })
    }
    await syncing
  }

  function logout() {
    token.value = null
    clearStoredToken()
    persistUser(null)
    sessionSynced.value = false
    syncAttempted = false
  }

  return {
    token,
    user,
    sessionSynced,
    isAuthenticated,
    displayName,
    avatarText,
    login,
    register,
    hydrate,
    ensureSession,
    logout,
  }
})
