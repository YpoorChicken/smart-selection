import type { NumericValue, PlatformId } from '@/types/products'

export interface CompetitorProductBrief {
  id: string
  title: string
  platform: PlatformId | string
  external_id: string
  price: NumericValue | null
  currency: string
  rating: NumericValue | null
  review_count: number
  image_url: string | null
  product_url: string | null
  last_synced_at: string | null
}

export interface CompetitorSnapshot {
  id: number
  binding_id: string
  price: NumericValue
  rating: NumericValue | null
  price_change_pct: NumericValue | null
  recorded_at: string
}

export interface CompetitorBinding {
  id: string
  own_product_id: string
  competitor_product_id: string
  created_by: string
  is_active: boolean
  created_at: string
  removed_at: string | null
  own_product: CompetitorProductBrief | null
  competitor_product: CompetitorProductBrief | null
  latest_snapshot: CompetitorSnapshot | null
  discover_reason?: string | null
}

export interface CompetitorDetail {
  binding: CompetitorBinding
  snapshots: CompetitorSnapshot[]
  recent_alert_count: number
}

export interface DiscoverCompetitorsData {
  own_product_id: string
  summary: string
  candidates_considered: number
  created: CompetitorBinding[]
  skipped_existing: number
  mode: string
}

export interface BatchUpdateCompetitorsData {
  total: number
  updated: number
  failed: number
  alerts_created: number
  price_drop_alerts: number
  rating_drop_alerts: number
  errors: string[]
}

export interface CompetitionTopChangeItem {
  binding_id: string
  own_product_id: string
  own_product_title: string
  competitor_product_id: string
  competitor_product_title: string
  price: NumericValue
  price_change_pct: NumericValue
  direction: 'up' | 'down'
  recorded_at: string
}

export interface CompetitionDashboardData {
  monitored_total: number
  today_alert_count: number
  today_price_change_count: number
  top_changes: CompetitionTopChangeItem[]
  summary: string
  generated_at: string
}
