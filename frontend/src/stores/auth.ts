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
    return result
  }

  async function register(payload: RegisterPayload) {
    const result = await registerApi(payload)
    if ('access_token' in result && result.access_token) {
      token.value = result.access_token
      setStoredToken(result.access_token)
      persistUser(result.user)
      return result
    }
    persistUser(result as UserInfo)
    return result
  }

  async function hydrate() {
    if (!token.value) {
      persistUser(null)
      return
    }
    try {
      const me = await fetchMeApi()
      persistUser(me)
    } catch {
      logout()
    }
  }

  function logout() {
    token.value = null
    clearStoredToken()
    persistUser(null)
  }

  return {
    token,
    user,
    isAuthenticated,
    displayName,
    avatarText,
    login,
    register,
    hydrate,
    logout,
  }
})
