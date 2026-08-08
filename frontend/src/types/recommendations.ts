import type { PlatformId } from '@/types/products'

export type RecommendationStatus = 'pending' | 'accepted' | 'rejected'

export interface BlueOceanScores {
  demand: number | string
  competition: number | string
  margin: number | string
  trend: number | string
}

export interface BlueOceanCategoryItem {
  category_id: string
  category_name: string
  platform_id: PlatformId
  title: string
  product_id: string | null
  blue_ocean_index: number | string
  scores: BlueOceanScores
  sample_size: number
  avg_price: number | string | null
  growth_rate: number | string | null
  reason: string
  recommendation_id: string | null
}

export interface BlueOceanCategoryData {
  items: BlueOceanCategoryItem[]
  min_demand: number | string
  min_competition: number | string
  total: number
}

export interface RecommendationItem {
  id: string
  category_id: string
  product_id: string | null
  title: string
  score_total: number | string
  score_demand: number | string
  score_competition: number | string
  score_margin: number | string
  score_trend: number | string
  ai_blue_ocean_text: string | null
  reason: string | null
  status: RecommendationStatus
  decided_by: string | null
  decided_at: string | null
  reject_reason: string | null
  note: string | null
  created_at: string
  updated_at: string
  category_name: string | null
  platform_id: PlatformId | null
}

export interface RecommendationStats {
  pending: number
  accepted: number
  rejected: number
  total: number
}

export interface PageMeta {
  page: number
  page_size: number
  total: number
  total_pages: number
}

export interface RecommendationPageData {
  items: RecommendationItem[]
  meta: PageMeta
}

export interface CompetitorStrategy {
  rank: number
  name: string
  differentiation: string
}

export interface SelectionAIAnalysis {
  market_opportunity: string
  competitive_landscape: CompetitorStrategy[]
  entry_advice: string
  risks: string[]
}

export interface SelectionAIAnalysisData {
  recommendation_id: string
  category_id: string
  category_name: string
  generated_at: string
  analysis: SelectionAIAnalysis
  reason: string
  ai_blue_ocean_text: string
}

export interface GenerateRecommendationsData {
  items: RecommendationItem[]
  generated_count: number
}
