import type { PlatformId } from '@/types/products'

export type TrendVerdict = 'growing' | 'shrinking' | 'stable'
export type CompetitionLevel = 'high' | 'mid' | 'low'

export interface GrowthCategoryItem {
  id: string
  category_id: string
  category_name: string
  platform_id: PlatformId
  period_month: string
  price_p25: string | number | null
  price_p50: string | number | null
  price_p75: string | number | null
  avg_price: string | number | null
  growth_rate: string | number | null
  seasonality_hint: string | null
  sample_size: number | null
  ai_insight: string | null
  ai_verdict: TrendVerdict | null
  computed_at: string
}

export interface GrowthCategoryData {
  items: GrowthCategoryItem[]
  days: number
}

export interface PriceDistributionBucket {
  label: string
  min_price: string | number
  max_price: string | number
  product_count: number
  average_rating: string | number | null
}

export interface PriceCurvePoint {
  period_month: string
  average_price: string | number
  growth_rate: string | number | null
}

export interface PriceDistributionData {
  category_id: string
  category_name: string
  currency: string
  sample_size: number
  price_p25: string | number
  price_p50: string | number
  price_p75: string | number
  buckets: PriceDistributionBucket[]
  price_curve: PriceCurvePoint[]
  analysis_suggestion: string
}

export interface TrendAIReportData {
  category_id: string
  category_name: string
  generated_at: string
  summary: string
  highlights: string[]
  recommendations: string[]
  risks: string[]
}
