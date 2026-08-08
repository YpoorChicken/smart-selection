import request from '@/api/request'
import type { ApiResponse } from '@/types/auth'
import type { PlatformId } from '@/types/products'
import type {
  GrowthCategoryData,
  PriceDistributionData,
  TrendAIReportData,
} from '@/types/trends'

export async function getGrowthCategories(params: {
  platform_id: PlatformId
  days?: number
  limit?: number
}): Promise<GrowthCategoryData> {
  const response = await request.get<ApiResponse<GrowthCategoryData>>(
    '/trends/categories',
    { params },
  )
  return response.data.data as GrowthCategoryData
}

export async function getPriceDistribution(
  categoryId: string,
): Promise<PriceDistributionData> {
  const response = await request.get<ApiResponse<PriceDistributionData>>(
    `/trends/categories/${categoryId}/charts/price-distribution`,
  )
  return response.data.data as PriceDistributionData
}

export async function generateTrendAIReport(
  categoryId: string,
): Promise<TrendAIReportData> {
  // LLM 生成可能超过默认 30s，单独放宽超时。
  const response = await request.post<ApiResponse<TrendAIReportData>>(
    `/trends/categories/${categoryId}/ai-report`,
    null,
    { timeout: 90000 },
  )
  return response.data.data as TrendAIReportData
}

export async function calculateCategoryTrend(payload: {
  category_id: string
  period?: 'daily' | 'monthly'
}): Promise<void> {
  await request.post('/trends/calculate', {
    category_id: payload.category_id,
    period: payload.period ?? 'daily',
  })
}
