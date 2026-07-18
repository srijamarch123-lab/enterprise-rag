export interface SearchResult {
  score: number
  semantic_score?: number
  bm25_score?: number
  combined_score?: number
  confidence_score?: number
  search_type: 'semantic' | 'bm25' | 'hybrid'
  qdrant_point_id?: string
  doc_name?: string
  doc_id?: number
  filename?: string
  text_preview?: string
  parent_text?: string
  text?: string
  department?: string | null
  access_level?: string
  drive_url?: string
  path?: string
  file_path?: string
  chunk_id?: number
  chunk_index?: number
  page?: number | null
  document_id?: number
  page_number?: number | null
}

export interface User {
  id: number
  email: string
  full_name: string | null
  role: string
  department: string | null
  is_active: boolean
  created_at: string | null
  last_login: string | null
  last_login_ip?: string | null
  login_count?: number
  password_last_changed?: string | null
  recent_activity?: { action: string; timestamp: string }[]
}

export interface Document {
  id: number
  filename: string
  original_filename: string
  file_path: string
  file_type: string
  file_size: number
  department: string | null
  status: string
  page_count: number | null
  chunk_count: number | null
  uploaded_at: string
  processed_at?: string | null
  extraction_error?: string | null
}

export interface ChatMessage {
  id: string | number
  role: 'user' | 'assistant'
  content?: string
  query?: string
  answer?: string
  results?: SearchResult[]
  hasAnswer?: boolean
  normalizedQuery?: string
  error?: string | null
  metadata?: Record<string, any>
  suggestions?: string[]
  feedbackSubmitted?: 'up' | 'down'
}

export interface Conversation {
  id: string
  title: string
  messages: ChatMessage[]
}
