/** Listing 优化相关类型（对齐 SDD §3.5） */

export type ListingSource = 'original' | 'ai_generated' | 'adopted'
export type ABTestStatus = 'running' | 'completed' | 'cancelled'
export type ABTestMetric = 'manual' | 'ctr' | 'conversion' | 'keyword_coverage'
export type ABTestWinner = 'a' | 'b'

export interface ListingVersion {
  id: string
  product_id: string
  version_no: number
  source: ListingSource
  title: string
  description: string | null
  bullet_points: string[] | null
  keywords: string | null
  keyword_coverage: number | string | null
  reason: string | null
  is_current: boolean
  created_by: string | null
  created_at: string
  parent_version_id: string | null
}

export interface ListingOptimizeAIResult {
  title: string
  bullet_points: string[]
  description: string
  search_keywords: string[]
  reason: string
}

export interface OptimizeListingData {
  product_id: string
  listing_id: string
  parent_version_id: string | null
  version: ListingVersion
  optimization: ListingOptimizeAIResult
  keyword_seed: string[]
  competitor_titles: string[]
  mode: string
  generated_at: string
}

export interface ListingCurrentData {
  product_id: string
  product_title: string
  platform: string
  external_id: string
  version: ListingVersion
  is_synthetic: boolean
}

export interface ListingVersionsData {
  product_id: string
  items: ListingVersion[]
  creators: Record<string, string>
  generated_at: string
}

export interface ListingCompareData {
  product_id: string
  original: ListingVersion
  optimized: ListingVersion | null
  generated_at: string
}

export interface CreateAbTestRequest {
  listing_id: string
  version_a_id?: string | null
  metric?: ABTestMetric
}

export interface AbTestRead {
  id: string
  listing_id: string
  version_a_id: string
  version_b_id: string
  status: ABTestStatus
  metric: ABTestMetric
  started_at: string
  completed_at: string | null
  winner: ABTestWinner | null
  created_by: string | null
  created_at: string
  updated_at: string
  version_a: ListingVersion | null
  version_b: ListingVersion | null
  winner_version_id: string | null
}

export interface CreateAbTestData {
  ab_test: AbTestRead
  optimization: ListingOptimizeAIResult | null
  mode: string
  generated_at: string
}

export interface CompleteAbTestRequest {
  winner: ABTestWinner
  adopt?: boolean
}

export interface CompleteAbTestData {
  ab_test: AbTestRead
  adopted: boolean
  current_version_id: string | null
}

export interface AbTestHistoryPage {
  items: AbTestRead[]
  meta: {
    page: number
    page_size: number
    total: number
    total_pages: number
  }
}
