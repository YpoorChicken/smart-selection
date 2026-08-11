import request from '@/api/request'
import type { ApiResponse } from '@/types/auth'
import type {
  InventoryPageData,
  InventoryRisk,
  InventorySummaryData,
  InventoryUpdateData,
  InventoryUpdatePayload,
} from '@/types/inventory'

function getResponseData<T>(response: { data: ApiResponse<T> }): T {
  if (response.data.data === null) {
    throw new Error(response.data.message || '服务未返回数据')
  }
  return response.data.data
}

export async function getInventoryList(params?: {
  page?: number
  page_size?: number
  risk_level?: InventoryRisk | ''
  keyword?: string
}): Promise<InventoryPageData> {
  const response = await request.get<ApiResponse<InventoryPageData>>(
    '/inventory',
    {
      params: {
        page: params?.page,
        page_size: params?.page_size,
        risk_level: params?.risk_level || undefined,
        keyword: params?.keyword || undefined,
      },
    },
  )
  return getResponseData(response)
}

export async function getInventorySummary(): Promise<InventorySummaryData> {
  const response = await request.get<ApiResponse<InventorySummaryData>>(
    '/inventory/summary',
  )
  return getResponseData(response)
}

export async function updateInventory(
  productId: string,
  payload: InventoryUpdatePayload,
): Promise<InventoryUpdateData> {
  const response = await request.put<ApiResponse<InventoryUpdateData>>(
    `/inventory/${productId}`,
    payload,
  )
  return getResponseData(response)
}

export async function checkInventory(): Promise<Record<string, unknown>> {
  const response = await request.post<ApiResponse<Record<string, unknown>>>(
    '/inventory/check',
  )
  return getResponseData(response)
}
