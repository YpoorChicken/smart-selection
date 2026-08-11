import request from '@/api/request'
import type { ApiResponse } from '@/types/auth'
import type { PlatformId } from '@/types/products'
import type {
  CategoryGrowthData,
  DailyPriceTrendData,
  DashboardOverviewData,
} from '@/types/dashboard'

function getResponseData<T>(response: { data: ApiResponse<T> }): T {
  if (response.data.data === null) {
    throw new Error(response.data.message || '服务未返回数据')
  }
  return response.data.data
}

export async function getDashboardOverview(params?: {
  platform_id?: PlatformId
  days?: number
}): Promise<DashboardOverviewData> {
  const response = await request.get<ApiResponse<DashboardOverviewData>>(
    '/dashboard/overview',
    { params },
  )
  return getResponseData(response)
}

export async function getCategoryGrowth(params?: {
  platform_id?: PlatformId
  days?: number
  limit?: number
}): Promise<CategoryGrowthData> {
  const response = await request.get<ApiResponse<CategoryGrowthData>>(
    '/dashboard/category-growth',
    { params },
  )
  return getResponseData(response)
}

export async function getDailyPriceTrend(params?: {
  days?: number
}): Promise<DailyPriceTrendData> {
  const response = await request.get<ApiResponse<DailyPriceTrendData>>(
    '/dashboard/price-trend',
    { params },
  )
  return getResponseData(response)
}
