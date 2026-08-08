import request from './request'
import type {
  ApiResponse,
  LoginPayload,
  RegisterPayload,
  TokenPayload,
  UserInfo,
} from '@/types/auth'

export async function loginApi(payload: LoginPayload): Promise<TokenPayload> {
  const { data } = await request.post<ApiResponse<TokenPayload>>(
    '/auth/login',
    payload,
  )
  if (!data.data) {
    throw new Error(data.message || '登录失败')
  }
  return data.data
}

export async function registerApi(
  payload: RegisterPayload,
): Promise<TokenPayload | UserInfo> {
  const { data } = await request.post<ApiResponse<TokenPayload | UserInfo>>(
    '/auth/register',
    payload,
  )
  if (!data.data) {
    throw new Error(data.message || '注册失败')
  }
  return data.data
}

export async function fetchMeApi(): Promise<UserInfo> {
  const { data } = await request.get<ApiResponse<UserInfo>>('/auth/me')
  if (!data.data) {
    throw new Error(data.message || '获取用户信息失败')
  }
  return data.data
}
