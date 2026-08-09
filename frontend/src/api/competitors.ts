import request from '@/api/request'
import type { ApiResponse } from '@/types/auth'
import type { PageData } from '@/types/products'
import type {
  BatchUpdateCompetitorsData,
  CompetitionDashboardData,
  CompetitorBinding,
  CompetitorDetail,
  DiscoverCompetitorsData,
} from '@/types/competitors'

function getResponseData<T>(response: { data: ApiResponse<T> }): T {
  if (response.data.data === null) {
    throw new Error(response.data.message || '服务未返回数据')
  }
  return response.data.data
}

export async function getCompetitorBindings(params: {
  own_product_id?: string
  active_only?: boolean
  page?: number
  page_size?: number
}): Promise<PageData<CompetitorBinding>> {
  const response = await request.get<ApiResponse<PageData<CompetitorBinding>>>(
    '/competitors',
    { params },
  )
  return getResponseData(response)
}

export async function getCompetitorDetail(
  bindingId: string,
  snapshotLimit = 60,
): Promise<CompetitorDetail> {
  const response = await request.get<ApiResponse<CompetitorDetail>>(
    `/competitors/${bindingId}`,
    { params: { snapshot_limit: snapshotLimit } },
  )
  return getResponseData(response)
}

export async function discoverCompetitors(params: {
  product_id: string
  limit?: number
  use_ai?: boolean
}): Promise<DiscoverCompetitorsData> {
  const response = await request.get<ApiResponse<DiscoverCompetitorsData>>(
    '/competitors/discover',
    { params },
  )
  return getResponseData(response)
}

export async function refreshCompetitor(
  bindingId: string,
): Promise<{ binding_id: string; alerts_created: number }> {
  const response = await request.post<
    ApiResponse<{ binding_id: string; alerts_created: number }>
  >(`/competitors/${bindingId}/refresh`)
  return getResponseData(response)
}

export async function batchUpdateCompetitors(): Promise<BatchUpdateCompetitorsData> {
  const response = await request.post<ApiResponse<BatchUpdateCompetitorsData>>(
    '/competitors/batch-update',
  )
  return getResponseData(response)
}

export async function getCompetitionDashboard(
  topLimit = 5,
): Promise<CompetitionDashboardData> {
  const response = await request.get<ApiResponse<CompetitionDashboardData>>(
    '/dashboard/competition',
    { params: { top_limit: topLimit } },
  )
  return getResponseData(response)
}
