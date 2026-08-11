import type { PlatformId } from '@/types/products'

export type TrendVerdict = 'growing' | 'shrinking' | 'stable'

export interface FastestGrowingCategory {
  category_id: string
  category_name: string
  platform_id: PlatformId
  growth_rate: string | number
  average_price: string | number | null
  sample_size: number | null
  ai_verdict: TrendVerdict | null
  period_month: string
}

export interface OverviewBlueOceanCategory {
  category_id: string
  category_name: string
  platform_id: PlatformId
  blue_ocean_index: string | number
  score_demand: string | number
  score_competition: string | number
  score_margin: string | number
  score_trend: string | number
  reason: string | null
  recommendation_id: string | null
  avg_price: string | number | null
  growth_rate: string | number | null
}

export interface DashboardOverviewData {
  product_total: number
  watched_category_count: number
  pending_recommendation_count: number
  today_alert_count: number
  fastest_growing_category: FastestGrowingCategory | null
  blue_ocean_category: OverviewBlueOceanCategory | null
  summary: string
  generated_at: string
}

export interface CategoryGrowthItem {
  category_id: string
  category_name: string
  platform_id: PlatformId
  growth_rate: string | number | null
  average_price: string | number | null
  sample_size: number | null
  period_month: string
}

export interface CategoryGrowthData {
  items: CategoryGrowthItem[]
  days: number
  limit: number
  generated_at: string
}

export interface DailyPriceTrendPoint {
  date: string
  own_avg_price: string | number | null
  competitor_avg_price: string | number | null
}

export interface DailyPriceTrendData {
  days: number
  points: DailyPriceTrendPoint[]
  generated_at: string
}
