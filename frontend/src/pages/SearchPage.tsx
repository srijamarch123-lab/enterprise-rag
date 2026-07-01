import { useState } from 'react'
import { Search, FileText, Loader2 } from 'lucide-react'
import api from '../services/api'

interface SearchResult {
  // existing fields
  score: number
  semantic_score?: number
  bm25_score?: number
  combined_score?: number
  confidence_score?: number
  search_type: 'semantic' | 'bm25' | 'hybrid'
  qdrant_point_id?: string

  // source attribution (Phase 5)
  doc_name?: string
  doc_id?: number
  path?: string
  chunk_id: number
  chunk_index: number
  page?: number | null

  // legacy fields (may still exist from older backend)
  document_id?: number
  page_number?: number | null
  text_preview: string
  department: string | null
  access_level: string
  filename?: string
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
    <div style={{ padding: '24px', maxWidth: '900px' }}>
      <h1 style={{ fontSize: '20px', fontWeight: 600, marginBottom: '20px', color: '#1a5c2e' }}>
        Search Documents
      </h1>

      {/* Search Form */}
      <form onSubmit={handleSearch} style={{ marginBottom: '24px' }}>
        <div style={{ display: 'flex', gap: '12px' }}>
          <div style={{ flex: 1, position: 'relative' }}>
            <Search
              size={18}
              style={{ position: 'absolute', left: '14px', top: '50%', transform: 'translateY(-50%)', color: '#7a9a7a' }}
            />
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search your documents..."
              style={{
                width: '100%',
                padding: '12px 16px 12px 44px',
                fontSize: '15px',
                border: '1px solid #c8e6d0',
                borderRadius: '10px',
                outline: 'none',
                background: 'white',
              }}
            />
          </div>
          <button
            type="submit"
            disabled={loading || !query.trim()}
            style={{
              padding: '12px 24px',
              background: loading ? '#c0dd97' : '#4a7a5a',
              color: 'white',
              border: 'none',
              borderRadius: '10px',
              fontSize: '14px',
              fontWeight: 500,
              cursor: loading ? 'not-allowed' : 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
            }}
          >
            {loading && <Loader2 size={16} className="animate-spin" />}
            Search
          </button>
        </div>
      </form>

      {/* Error */}
      {error && (
        <div style={{ padding: '16px', background: '#fee', color: '#c00', borderRadius: '8px', marginBottom: '16px' }}>
          {error}
        </div>
      )}

      {/* Results */}
      {searched && !loading && (
        <div>
          {!hasAnswer ? (
            <div style={{ padding: '24px', textAlign: 'center', background: '#f5f5f5', borderRadius: '10px', color: '#666' }}>
              No confident answer found. Try rephrasing your question.
            </div>
          ) : results.length === 0 ? (
            <div style={{ color: '#7a9a7a', textAlign: 'center', padding: '40px' }}>
              No results found
            </div>
          ) : (
            <>
              <div style={{ fontSize: '13px', color: '#7a9a7a', marginBottom: '16px' }}>
                Found {results.length} results for "{query}"
                {normalizedQuery && normalizedQuery !== query && (
                  <span style={{ marginLeft: '8px' }}>
                    (normalized: "{normalizedQuery}")
                  </span>
                )}
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                {results.map((r, i) => (
                  <div
                    key={r.chunk_id || i}
                    style={{
                      padding: '16px',
                      background: 'white',
                      borderRadius: '10px',
                      border: '1px solid #e8f5ee',
                    }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'start', marginBottom: '8px' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <FileText size={16} style={{ color: '#4a7a5a' }} />
                        <span style={{ fontSize: '14px', fontWeight: 500, color: '#1a5c2e' }}>
                          {r.doc_name || r.filename || `Document ${r.doc_id ?? ''}`}
                        </span>
                        {r.search_type && (
                          <span
                            style={{
                              fontSize: '10px',
                              padding: '2px 6px',
                              borderRadius: '4px',
                              background: r.search_type === 'semantic' ? '#e3d5fc' : '#fce3d5',
                              color: r.search_type === 'semantic' ? '#5a3a9a' : '#9a5a3a',
                              textTransform: 'uppercase',
                            }}
                          >
                            {r.search_type}
                          </span>
                        )}
                      </div>
                      <span
                        style={{
                          fontSize: '12px',
                          padding: '2px 8px',
                          borderRadius: '4px',
                          background: '#e8f5ee',
                          color: '#1a5c2e',
                          whiteSpace: 'nowrap',
                        }}
                        title="Confidence score"
                      >
                        {typeof r.confidence_score === 'number'
                          ? `${(r.confidence_score * 100).toFixed(1)}% confidence`
                          : r.combined_score
                            ? `${(r.combined_score * 100).toFixed(1)}%`
                            : r.search_type === 'semantic'
                              ? `${(r.semantic_score ? r.semantic_score * 100 : 0).toFixed(1)}%`
                              : `BM25: ${r.bm25_score?.toFixed(1) || 0}`}
                      </span>
                    </div>

                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', marginBottom: '4px' }}>
                      {typeof (r.page ?? r.page_number) === 'number' && (
                        <div style={{ fontSize: '12px', color: '#7a9a7a' }}>
                          Page {r.page ?? r.page_number}
                        </div>
                      )}

                      {typeof r.chunk_id === 'number' && (
                        <div style={{ fontSize: '12px', color: '#7a9a7a' }}>
                          Chunk {r.chunk_id}
                        </div>
                      )}

                      {typeof r.doc_id === 'number' && (
                        <div style={{ fontSize: '12px', color: '#7a9a7a' }}>
                          Doc ID {r.doc_id}
                        </div>
                      )}

                      {r.path && (
                        <div
                          style={{
                            fontSize: '12px',
                            color: '#7a9a7a',
                            maxWidth: 260,
                            overflow: 'hidden',
                            textOverflow: 'ellipsis',
                            whiteSpace: 'nowrap',
                          }}
                          title={r.path}
                        >
                          Source: {r.path}
                        </div>
                      )}
                    </div>

                    <div style={{ fontSize: '13px', color: '#4a5a4a', lineHeight: 1.5 }}>
                      {r.text_preview}
                    </div>
                  </div>
                ))}
              </div>
            </>
          )}
        </div>
      )}

      {/* Initial state */}
      {!searched && !loading && (
        <div style={{ color: '#7a9a7a', textAlign: 'center', padding: '60px' }}>
          Enter a query to search your documents
        </div>
      )}
    </div>
  )
}