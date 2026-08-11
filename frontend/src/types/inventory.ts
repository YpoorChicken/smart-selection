import type { PlatformId } from '@/types/products'
import type { PageData } from '@/types/products'

export type InventoryRisk = 'normal' | 'watch' | 'critical'

export interface InventoryItem {
  id: string
  product_id: string
  product_title: string
  platform: PlatformId
  sku: string | null
  quantity: number
  safety_stock: number
  predicted_daily_sales: string | number | null
  days_of_cover: string | number | null
  risk_level: InventoryRisk
  recorded_at: string
}

export interface InventorySummaryData {
  product_total: number
  critical_count: number
  watch_count: number
  normal_count: number
  unread_inventory_alert_count: number
  generated_at: string
}

export interface InventoryUpdatePayload {
  quantity: number
  safety_stock?: number | null
  sku?: string | null
  predicted_daily_sales?: number | null
}

export interface InventoryUpdateData {
  item: InventoryItem
  alert_created: boolean
  alert_severity: string | null
}

export type InventoryPageData = PageData<InventoryItem>
