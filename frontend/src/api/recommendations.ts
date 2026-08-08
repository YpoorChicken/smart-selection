import request from '@/api/request'
import type { ApiResponse } from '@/types/auth'
import type { PlatformId } from '@/types/products'
import type {
  BlueOceanCategoryData,
  GenerateRecommendationsData,
  RecommendationItem,
  RecommendationPageData,
  RecommendationStats,
  RecommendationStatus,
  SelectionAIAnalysisData,
} from '@/types/recommendations'

function getResponseData<T>(response: { data: ApiResponse<T> }): T {
  if (response.data.data === null) {
    throw new Error(response.data.message || '服务未返回数据')
  }
  return response.data.data
}

export async function getBlueOceanCategories(params?: {
  platform_id?: PlatformId
  min_demand?: number
  min_competition?: number
  limit?: number
}): Promise<BlueOceanCategoryData> {
  const response = await request.get<ApiResponse<BlueOceanCategoryData>>(
    '/recommendations/blue-ocean',
    { params },
  )
  return getResponseData(response)
}

export async function getRecommendations(params?: {
  page?: number
  page_size?: number
  status?: RecommendationStatus
  platform_id?: PlatformId
  category_id?: string
  min_score?: number
}): Promise<RecommendationPageData> {
  const response = await request.get<ApiResponse<RecommendationPageData>>(
    '/recommendations',
    { params },
  )
  return getResponseData(response)
}

export async function getRecommendationStats(): Promise<RecommendationStats> {
  const response = await request.get<ApiResponse<RecommendationStats>>(
    '/recommendations/stats',
  )
  return getResponseData(response)
}

export async function getRecommendationDetail(
  id: string,
): Promise<RecommendationItem> {
  const response = await request.get<ApiResponse<RecommendationItem>>(
    `/recommendations/${id}`,
  )
  return getResponseData(response)
}

export async function generateRecommendations(payload: {
  platform_id?: PlatformId
  category_id?: string
  limit?: number
}): Promise<GenerateRecommendationsData> {
  const response = await request.post<ApiResponse<GenerateRecommendationsData>>(
    '/recommendations/generate',
    payload,
  )
  return getResponseData(response)
}

export async function generateSelectionAIAnalysis(
  id: string,
): Promise<SelectionAIAnalysisData> {
  const response = await request.post<ApiResponse<SelectionAIAnalysisData>>(
    `/recommendations/${id}/ai-analysis`,
  )
  return getResponseData(response)
}

export async function acceptRecommendation(
  id: string,
  note?: string,
): Promise<RecommendationItem> {
  const response = await request.post<ApiResponse<RecommendationItem>>(
    `/recommendations/${id}/accept`,
    note ? { note } : {},
  )
  return getResponseData(response)
}

export async function rejectRecommendation(
  id: string,
  reason?: string,
): Promise<RecommendationItem> {
  const response = await request.post<ApiResponse<RecommendationItem>>(
    `/recommendations/${id}/reject`,
    reason ? { reason } : {},
  )
  return getResponseData(response)
}
