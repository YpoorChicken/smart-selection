import request from '@/api/request'
import type { ApiResponse } from '@/types/auth'
import type {
  AbTestHistoryPage,
  CompleteAbTestData,
  CompleteAbTestRequest,
  CreateAbTestData,
  CreateAbTestRequest,
  ListingCompareData,
  ListingCurrentData,
  ListingVersion,
  ListingVersionsData,
  OptimizeListingData,
} from '@/types/listing'

function getResponseData<T>(response: { data: ApiResponse<T> }): T {
  if (response.data.data === null) {
    throw new Error(response.data.message || '服务未返回数据')
  }
  return response.data.data
}

export async function optimizeListing(listingId: string): Promise<OptimizeListingData> {
  const response = await request.post<ApiResponse<OptimizeListingData>>(
    `/listing/optimize/${listingId}`,
    null,
    { timeout: 90000 },
  )
  return getResponseData(response)
}

export async function getListingCurrent(productId: string): Promise<ListingCurrentData> {
  const response = await request.get<ApiResponse<ListingCurrentData>>(
    `/listing/${productId}/current`,
  )
  return getResponseData(response)
}

export async function getListingVersions(productId: string): Promise<ListingVersionsData> {
  const response = await request.get<ApiResponse<ListingVersionsData>>(
    `/listing/${productId}/versions`,
  )
  return getResponseData(response)
}

export async function compareListing(
  productId: string,
  versionId?: string,
): Promise<ListingCompareData> {
  const response = await request.get<ApiResponse<ListingCompareData>>(
    `/listing/${productId}/compare`,
    { params: versionId ? { version_id: versionId } : undefined },
  )
  return getResponseData(response)
}

export async function adoptListingVersion(
  productId: string,
  versionId: string,
): Promise<ListingVersion> {
  const response = await request.post<ApiResponse<ListingVersion>>(
    `/listing/${productId}/versions/${versionId}/adopt`,
  )
  return getResponseData(response)
}

export async function createAbTest(
  payload: CreateAbTestRequest,
): Promise<CreateAbTestData> {
  const response = await request.post<ApiResponse<CreateAbTestData>>(
    '/listing/ab-test/create',
    payload,
    { timeout: 90000 },
  )
  return getResponseData(response)
}

export async function completeAbTest(
  abTestId: string,
  payload: CompleteAbTestRequest,
): Promise<CompleteAbTestData> {
  const response = await request.put<ApiResponse<CompleteAbTestData>>(
    `/listing/ab-test/${abTestId}/complete`,
    payload,
  )
  return getResponseData(response)
}

export async function getAbTestHistory(params: {
  listing_id?: string
  status?: string
  page?: number
  page_size?: number
}): Promise<AbTestHistoryPage> {
  const response = await request.get<ApiResponse<AbTestHistoryPage>>(
    '/listing/ab-test/history',
    { params },
  )
  return getResponseData(response)
}
