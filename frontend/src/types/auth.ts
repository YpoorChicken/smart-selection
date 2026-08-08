export interface ApiResponse<T = unknown> {
  code: number
  data: T | null
  message: string
}

export interface UserInfo {
  id: string
  email: string
  display_name: string
  role: string
  is_active: boolean
}

export interface TokenPayload {
  access_token: string
  token_type: string
  expires_in: number
  user: UserInfo
}

export interface LoginPayload {
  email: string
  password: string
}

export interface RegisterPayload {
  email: string
  password: string
  display_name: string
}
