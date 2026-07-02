import { useState } from 'react'
import { Search, FileText, Loader2 } from 'lucide-react'
import api from '../services/api'
import { theme } from '../theme'

const { color, font, radius } = theme

interface SearchResult {
  score: number
  semantic_score?: number
  bm25_score?: number
  combined_score?: number
  confidence_score?: number
  search_type: 'semantic' | 'bm25' | 'hybrid'
  qdrant_point_id?: string

  doc_name?: string
  doc_id?: number
  path?: string
  file_path?: string
  chunk_id: number
  chunk_index: number
  page?: number | null

  document_id?: number
  page_number?: number | null
  text_preview: string
  department: string | null
  access_level: string
  filename?: string
}

function confidencePercent(r: SearchResult): number {
  if (typeof r.confidence_score === 'number') return r.confidence_score * 100
  if (typeof r.combined_score === 'number') return r.combined_score * 100
  if (r.search_type === 'semantic' && typeof r.semantic_score === 'number') return r.semantic_score * 100
  return 0
}

function confidenceColor(pct: number): string {
  if (pct >= 70) return color.success
  if (pct >= 40) return color.warning
  return color.danger
}

export default function SearchPage() {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<SearchResult[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [searched, setSearched] = useState(false)
  const [normalizedQuery, setNormalizedQuery] = useState('')
  const [hasAnswer, setHasAnswer] = useState(true)

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!query.trim()) return

    setLoading(true)
    setError('')
    setSearched(true)

    try {
      const res = await api.post('/search', { query, limit: 5 })
      setResults(res.data.results || [])
      setNormalizedQuery(res.data.normalized_query || '')
      setHasAnswer(res.data.has_answer ?? true)
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Search failed')
      setResults([])
      setHasAnswer(false)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{ padding: '32px 40px', maxWidth: '860px', fontFamily: font }}>
      <div style={{ marginBottom: '28px' }}>
        <h1 style={{ fontSize: '20px', fontWeight: 600, color: color.textPrimary, letterSpacing: '-0.01em', margin: 0 }}>
          Search documents
        </h1>
        <p style={{ fontSize: '13.5px', color: color.textSecondary, marginTop: '4px' }}>
          Ask a question in plain language. Results are scoped to what your role can access.
        </p>
      </div>

      <form onSubmit={handleSearch} style={{ marginBottom: '28px' }}>
        <div style={{ display: 'flex', gap: '10px' }}>
          <div style={{ flex: 1, position: 'relative' }}>
            <Search
              size={17}
              style={{ position: 'absolute', left: '14px', top: '50%', transform: 'translateY(-50%)', color: color.textTertiary }}
            />
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search your documents..."
              style={{
                width: '100%',
                padding: '12px 16px 12px 42px',
                fontSize: '14.5px',
                fontFamily: font,
                border: `1px solid ${color.border}`,
                borderRadius: radius.md,
                outline: 'none',
                background: color.surface,
                color: color.textPrimary,
              }}
              onFocus={(e) => (e.currentTarget.style.borderColor = color.chatAccent)}
              onBlur={(e) => (e.currentTarget.style.borderColor = color.border)}
            />
          </div>
          <button
            type="submit"
            disabled={loading || !query.trim()}
            style={{
              padding: '12px 22px',
              background: loading || !query.trim() ? color.borderStrong : color.chatAccent,
              color: '#fff',
              border: 'none',
              borderRadius: radius.md,
              fontSize: '14px',
              fontFamily: font,
              fontWeight: 500,
              cursor: loading || !query.trim() ? 'not-allowed' : 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              transition: 'background 0.12s',
            }}
          >
            {loading && <Loader2 size={15} className="animate-spin" />}
            Search
          </button>
        </div>
      </form>

      {error && (
        <div style={{ padding: '14px 16px', background: color.dangerSoft, color: color.danger, borderRadius: radius.md, marginBottom: '16px', fontSize: '13.5px' }}>
          {error}
        </div>
      )}

      {searched && !loading && (
        <div>
          {!hasAnswer ? (
            <div style={{ padding: '32px 24px', textAlign: 'center', background: color.surface, border: `1px solid ${color.border}`, borderRadius: radius.lg, color: color.textSecondary }}>
              <div style={{ fontSize: '14px', fontWeight: 500, color: color.textPrimary, marginBottom: '4px' }}>
                No confident answer found
              </div>
              <div style={{ fontSize: '13px' }}>Try rephrasing your question, or check that the right documents have been uploaded.</div>
            </div>
          ) : results.length === 0 ? (
            <div style={{ color: color.textTertiary, textAlign: 'center', padding: '48px', fontSize: '13.5px' }}>
              No results found
            </div>
          ) : (
            <>
              <div style={{ fontSize: '12.5px', color: color.textTertiary, marginBottom: '14px' }}>
                {results.length} result{results.length !== 1 ? 's' : ''} for "{query}"
                {normalizedQuery && normalizedQuery !== query && (
                  <span style={{ marginLeft: '6px' }}>· normalized: "{normalizedQuery}"</span>
                )}
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                {results.map((r, i) => {
                  const pct = confidencePercent(r)
                  const cColor = confidenceColor(pct)
                  return (
                    <div
                      key={r.chunk_id || i}
                      style={{
                        padding: '16px 18px',
                        background: color.surface,
                        borderRadius: radius.md,
                        border: `1px solid ${color.border}`,
                      }}
                    >
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '12px', marginBottom: '10px' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', minWidth: 0 }}>
                          <FileText size={15} style={{ color: color.textTertiary, flexShrink: 0 }} />
                          <span style={{ fontSize: '13.5px', fontWeight: 500, color: color.textPrimary, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                            {r.doc_name || r.filename || `Document ${r.doc_id ?? ''}`}
                          </span>
                          {r.search_type && (
                            <span
                              style={{
                                fontSize: '10px',
                                fontWeight: 600,
                                padding: '2px 7px',
                                borderRadius: '20px',
                                background: color.chatAccentSoft,
                                color: color.chatAccent,
                                textTransform: 'uppercase',
                                letterSpacing: '0.02em',
                                flexShrink: 0,
                              }}
                            >
                              {r.search_type}
                            </span>
                          )}
                        </div>

                        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: '4px', flexShrink: 0 }}>
                          <span style={{ fontSize: '12px', fontWeight: 600, color: cColor }}>
                            {pct.toFixed(0)}% confidence
                          </span>
                          <div style={{ width: '72px', height: '4px', borderRadius: '2px', background: color.border, overflow: 'hidden' }}>
                            <div style={{ width: `${Math.min(pct, 100)}%`, height: '100%', background: cColor, borderRadius: '2px' }} />
                          </div>
                        </div>
                      </div>

                      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '10px', marginBottom: '8px' }}>
                        {typeof (r.page ?? r.page_number) === 'number' && (
                          <span style={{ fontSize: '11.5px', color: color.textTertiary }}>Page {r.page ?? r.page_number}</span>
                        )}
                        {typeof r.chunk_id === 'number' && (
                          <span style={{ fontSize: '11.5px', color: color.textTertiary }}>Chunk {r.chunk_id}</span>
                        )}
                        {typeof r.doc_id === 'number' && (
                          <span style={{ fontSize: '11.5px', color: color.textTertiary }}>Doc {r.doc_id}</span>
                        )}
                        {(r.path || r.file_path) && (
                          <span
                            style={{ fontSize: '11.5px', color: color.textTertiary, maxWidth: 240, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}
                            title={r.path || r.file_path}
                          >
                            {r.path || r.file_path}
                          </span>
                        )}
                      </div>

                      <div style={{ fontSize: '13px', color: color.textSecondary, lineHeight: 1.55 }}>
                        {r.text_preview}
                      </div>
                    </div>
                  )
                })}
              </div>
            </>
          )}
        </div>
      )}

      {!searched && !loading && (
        <div style={{ color: color.textTertiary, textAlign: 'center', padding: '64px', fontSize: '13.5px' }}>
          Enter a query to search your documents
        </div>
      )}
    </div>
  )
}
