import request from '@/api/request'
import type { ApiResponse } from '@/types/auth'
import type { PageData } from '@/types/products'
import type {
  AlertItem,
  AlertSeverity,
  AlertStatsData,
  AlertType,
  UnreadCountData,
} from '@/types/alerts'

function getResponseData<T>(response: { data: ApiResponse<T> }): T {
  if (response.data.data === null) {
    throw new Error(response.data.message || '服务未返回数据')
  }
  return response.data.data
}

export async function getAlerts(params: {
  page?: number
  page_size?: number
  is_read?: boolean
  type?: AlertType
  severity?: AlertSeverity
  product_id?: string
  days?: number
}): Promise<PageData<AlertItem>> {
  const response = await request.get<ApiResponse<PageData<AlertItem>>>('/alerts', {
    params,
  })
  return getResponseData(response)
}

export async function markAlertRead(alertId: string): Promise<AlertItem> {
  const response = await request.post<ApiResponse<AlertItem>>(
    `/alerts/${alertId}/read`,
  )
  return getResponseData(response)
}

export async function getUnreadAlertCount(): Promise<UnreadCountData> {
  const response = await request.get<ApiResponse<UnreadCountData>>(
    '/alerts/unread-count',
  )
  return getResponseData(response)
}

export async function getAlertStats(days = 7): Promise<AlertStatsData> {
  const response = await request.get<ApiResponse<AlertStatsData>>('/alerts/stats', {
    params: { days },
  })
  return getResponseData(response)
}
