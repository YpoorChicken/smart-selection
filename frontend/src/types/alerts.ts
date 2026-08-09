import type { NumericValue } from '@/types/products'

/** 后端枚举；展示映射 high/medium/low */
export type AlertSeverity = 'info' | 'warning' | 'critical'
export type AlertSeverityLabel = 'high' | 'medium' | 'low'

export type AlertType =
  | 'competitor_price_drop'
  | 'competitor_rating_drop'
  | 'competitor_discovered'
  | 'inventory_low'
  | 'collection_failed'

export interface AlertItem {
  id: string
  type: AlertType
  severity: AlertSeverity
  product_id: string | null
  competitor_binding_id: string | null
  threshold_value: NumericValue | null
  trigger_value: NumericValue | null
  title: string
  message: string | null
  is_read: boolean
  read_by: string | null
  read_at: string | null
  triggered_at: string
  created_at: string
  product_title: string | null
}

export interface UnreadCountData {
  unread_count: number
}

export interface AlertStatsData {
  total: number
  unread: number
  read: number
  by_type: Record<string, number>
  by_severity: Record<string, number>
  unread_by_severity: Record<string, number>
}

export function severityToLabel(severity: AlertSeverity): AlertSeverityLabel {
  if (severity === 'critical') return 'high'
  if (severity === 'warning') return 'medium'
  return 'low'
}
