import request from '@/api/request'
import type { ApiResponse } from '@/types/auth'
import type {
  CategoryTreeData,
  PageData,
  PlatformId,
  ProductHistoryData,
  ProductListItem,
  ProductQuery,
  SyncLog,
  SyncProductsRequest,
  SyncStatusData,
} from '@/types/products'

function getResponseData<T>(response: { data: ApiResponse<T> }): T {
  if (response.data.data === null) {
    throw new Error(response.data.message || '服务未返回数据')
  }

  return response.data.data
}

export async function getCategoryTree(platformId?: PlatformId): Promise<CategoryTreeData> {
  const response = await request.get<ApiResponse<CategoryTreeData>>('/categories', {
    params: platformId ? { platform_id: platformId } : undefined,
  })
  return getResponseData(response)
}

export async function getProducts(query: ProductQuery): Promise<PageData<ProductListItem>> {
  const response = await request.get<ApiResponse<PageData<ProductListItem>>>('/products', {
    params: query,
  })
  return getResponseData(response)
}

export async function getProduct(productId: string): Promise<ProductListItem & {
  bullet_points?: string[] | null
  keywords?: string | null
}> {
  const response = await request.get<
    ApiResponse<
      ProductListItem & {
        bullet_points?: string[] | null
        keywords?: string | null
      }
    >
  >(`/products/${productId}`)
  return getResponseData(response)
}

export async function getProductHistory(
  productId: string,
  limit = 90,
): Promise<ProductHistoryData> {
  const response = await request.get<ApiResponse<ProductHistoryData>>(
    `/products/${productId}/history`,
    { params: { limit } },
  )
  return getResponseData(response)
}

export async function syncCategories(platformId: PlatformId): Promise<SyncLog> {
  const response = await request.post<ApiResponse<SyncLog>>('/sync/categories', {
    platform_id: platformId,
  })
  return getResponseData(response)
}

export async function syncProducts(payload: SyncProductsRequest): Promise<SyncLog> {
  const response = await request.post<ApiResponse<SyncLog>>('/sync/products', payload)
  return getResponseData(response)
}

export async function getSyncStatus(limit = 10): Promise<SyncStatusData> {
  const response = await request.get<ApiResponse<SyncStatusData>>('/sync/status', {
    params: { limit },
  })
  return getResponseData(response)
}
