<script setup lang="ts">
import { computed, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const router = useRouter()
const route = useRoute()

const activeTab = ref<'login' | 'register'>('login')
const loading = ref(false)
const loginFormRef = ref<FormInstance>()
const registerFormRef = ref<FormInstance>()

const loginForm = reactive({
  email: '',
  password: '',
})

const registerForm = reactive({
  display_name: '',
  email: '',
  password: '',
  confirmPassword: '',
})

const loginRules: FormRules = {
  email: [
    { required: true, message: '请输入邮箱', trigger: 'blur' },
    { type: 'email', message: '邮箱格式不正确', trigger: 'blur' },
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 6, message: '密码至少 6 位', trigger: 'blur' },
  ],
}

const registerRules: FormRules = {
  display_name: [
    { required: true, message: '请输入显示名称', trigger: 'blur' },
    { min: 2, max: 40, message: '名称长度 2–40 字', trigger: 'blur' },
  ],
  email: [
    { required: true, message: '请输入邮箱', trigger: 'blur' },
    { type: 'email', message: '邮箱格式不正确', trigger: 'blur' },
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 6, message: '密码至少 6 位', trigger: 'blur' },
  ],
  confirmPassword: [
    { required: true, message: '请再次输入密码', trigger: 'blur' },
    {
      validator: (_rule, value, callback) => {
        if (value !== registerForm.password) {
          callback(new Error('两次输入的密码不一致'))
        } else {
          callback()
        }
      },
      trigger: 'blur',
    },
  ],
}

const redirectPath = computed(() => {
  const raw = route.query.redirect
  if (typeof raw === 'string' && raw.startsWith('/')) return raw
  return '/'
})

async function handleLogin() {
  const valid = await loginFormRef.value?.validate().catch(() => false)
  if (!valid) return

  loading.value = true
  try {
    await auth.login({
      email: loginForm.email.trim(),
      password: loginForm.password,
    })
    ElMessage.success('登录成功')
    await router.replace(redirectPath.value)
  } catch {
    // 错误已由拦截器提示
  } finally {
    loading.value = false
  }
}

async function handleRegister() {
  const valid = await registerFormRef.value?.validate().catch(() => false)
  if (!valid) return

  loading.value = true
  try {
    const result = await auth.register({
      email: registerForm.email.trim(),
      password: registerForm.password,
      display_name: registerForm.display_name.trim(),
    })
    if ('access_token' in result && result.access_token) {
      ElMessage.success('注册成功')
      await router.replace(redirectPath.value)
      return
    }
    ElMessage.success('注册成功，请登录')
    activeTab.value = 'login'
    loginForm.email = registerForm.email.trim()
    loginForm.password = ''
  } catch {
    // 错误已由拦截器提示
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="auth-page">
    <el-card class="auth-card" shadow="never">
      <div class="brand-block">
        <div class="brand-mark">H</div>
        <h1 class="brand-name">华普智选</h1>
        <p class="brand-desc">智能选品与跨境运营中台</p>
      </div>

      <el-tabs v-model="activeTab" class="auth-tabs" stretch>
        <el-tab-pane label="登录" name="login">
          <el-form
            ref="loginFormRef"
            :model="loginForm"
            :rules="loginRules"
            label-position="top"
            @keyup.enter="handleLogin"
          >
            <el-form-item label="邮箱" prop="email">
              <el-input
                v-model="loginForm.email"
                placeholder="请输入邮箱"
                clearable
                autocomplete="username"
              />
            </el-form-item>
            <el-form-item label="密码" prop="password">
              <el-input
                v-model="loginForm.password"
                type="password"
                placeholder="请输入密码"
                show-password
                autocomplete="current-password"
              />
            </el-form-item>
            <div class="form-extra">
              <el-link type="info" :underline="false">忘记密码？</el-link>
            </div>
            <el-button
              type="primary"
              class="submit-btn"
              :loading="loading"
              @click="handleLogin"
            >
              登录
            </el-button>
            <p class="switch-hint">
              还没有账号？
              <el-link type="primary" :underline="false" @click="activeTab = 'register'">
                切换到注册
              </el-link>
            </p>
          </el-form>
        </el-tab-pane>

        <el-tab-pane label="注册" name="register">
          <el-form
            ref="registerFormRef"
            :model="registerForm"
            :rules="registerRules"
            label-position="top"
            @keyup.enter="handleRegister"
          >
            <el-form-item label="显示名称" prop="display_name">
              <el-input
                v-model="registerForm.display_name"
                placeholder="如：张敏"
                clearable
              />
            </el-form-item>
            <el-form-item label="邮箱" prop="email">
              <el-input
                v-model="registerForm.email"
                placeholder="请输入邮箱"
                clearable
                autocomplete="username"
              />
            </el-form-item>
            <el-form-item label="密码" prop="password">
              <el-input
                v-model="registerForm.password"
                type="password"
                placeholder="至少 6 位"
                show-password
                autocomplete="new-password"
              />
            </el-form-item>
            <el-form-item label="确认密码" prop="confirmPassword">
              <el-input
                v-model="registerForm.confirmPassword"
                type="password"
                placeholder="再次输入密码"
                show-password
                autocomplete="new-password"
              />
            </el-form-item>
            <el-button
              type="primary"
              class="submit-btn"
              :loading="loading"
              @click="handleRegister"
            >
              注册
            </el-button>
            <p class="switch-hint">
              已有账号？
              <el-link type="primary" :underline="false" @click="activeTab = 'login'">
                切换到登录
              </el-link>
            </p>
          </el-form>
        </el-tab-pane>
      </el-tabs>
    </el-card>
  </div>
</template>

<style scoped>
.auth-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 64px 16px;
  background: #f3f4f6;
}

.auth-card {
  width: 420px;
  max-width: 100%;
  border: 1px solid var(--color-hairline);
  border-radius: var(--radius-xl);
  box-shadow: var(--shadow-raised);
  padding: 8px 8px 16px;
}

.brand-block {
  text-align: center;
  margin-bottom: 8px;
  padding-top: 8px;
}

.brand-mark {
  width: 40px;
  height: 40px;
  margin: 0 auto 12px;
  border-radius: 8px;
  background: var(--color-primary);
  color: #fff;
  font-size: 18px;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
}

.brand-name {
  margin: 0;
  font-size: 22px;
  font-weight: 600;
  color: var(--color-ink);
  letter-spacing: -0.2px;
}

.brand-desc {
  margin: 8px 0 0;
  font-size: 12px;
  color: var(--color-ink-muted);
}

.auth-tabs :deep(.el-tabs__item) {
  font-size: 14px;
  font-weight: 500;
  color: var(--color-ink-muted);
}

.auth-tabs :deep(.el-tabs__item.is-active) {
  color: var(--color-primary);
}

.auth-tabs :deep(.el-tabs__active-bar) {
  background-color: var(--color-primary);
  height: 2px;
}

.auth-tabs :deep(.el-tabs__nav-wrap::after) {
  height: 1px;
  background-color: var(--color-hairline);
}

.auth-tabs :deep(.el-form-item__label) {
  color: var(--color-ink-secondary);
  font-weight: 500;
}

.form-extra {
  display: flex;
  justify-content: flex-end;
  margin: -4px 0 16px;
}

.submit-btn {
  width: 100%;
  height: 36px;
  border-radius: 6px;
  font-weight: 600;
}

.switch-hint {
  margin: 16px 0 0;
  text-align: center;
  font-size: 12px;
  color: var(--color-ink-muted);
}
</style>
