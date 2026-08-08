export type PlatformId = 'amazon' | 'shopee' | 'mock' | 'fakestore'

export type NumericValue = number | string

export interface CategoryNode {
  id: string
  platform: PlatformId
  external_id: string
  name: string
  parent_id: string | null
  path: string | null
  is_watched: boolean
  product_count: number
  children: CategoryNode[]
}

export interface CategoryTreeData {
  items: CategoryNode[]
}

export interface CategoryBrief {
  id: string
  name: string
  external_id: string
}

export interface ProductListItem {
  id: string
  platform: PlatformId
  external_id: string
  category_id: string
  category: CategoryBrief
  title: string
  description: string | null
  price: NumericValue | null
  currency: string
  rating: NumericValue | null
  review_count: number
  bsr: number | null
  image_url: string | null
  product_url: string | null
  last_synced_at: string | null
  created_at: string
  updated_at: string
}

export interface PageMeta {
  page: number
  page_size: number
  total: number
  total_pages: number
}

export interface PageData<T> {
  items: T[]
  meta: PageMeta
}

export interface ProductHistoryPoint {
  id: number
  price: NumericValue | null
  rating: NumericValue | null
  review_count: number | null
  bsr: number | null
  recorded_at: string
}

export interface ProductHistoryData {
  product_id: string
  items: ProductHistoryPoint[]
}

export type SyncStatus = 'pending' | 'running' | 'success' | 'failed'

export interface SyncLog {
  id: string
  platform_id: PlatformId
  sync_type: 'categories' | 'products' | 'product_detail' | 'daily_history'
  status: SyncStatus
  items_count: number
  error_message: string | null
  started_at: string
  completed_at: string | null
}

export interface SyncStatusData {
  items: SyncLog[]
  running_count: number
}

export interface ProductQuery {
  page: number
  page_size: number
  platform_id?: PlatformId
  category_id?: string
  price_min?: number
  price_max?: number
  q?: string
  sort_by?: 'price' | 'rating' | 'sales_rank'
  sort_order?: 'asc' | 'desc'
}

export interface SyncProductsRequest {
  platform_id: PlatformId
  category_id?: string
  product_id?: string
}
