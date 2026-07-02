import { useState, useRef, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { Send, Plus, MessageSquare, ArrowLeft, LogOut, FileText, Loader2 } from 'lucide-react'
import api from '../services/api'
import { logout } from '../services/api'
import { theme } from '../theme'

const { color, font, radius } = theme

const STORAGE_KEY = 'enterprise_rag_chat_conversations'

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

interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  query?: string
  results?: SearchResult[]
  hasAnswer?: boolean
  normalizedQuery?: string
  error?: string
}

interface Conversation {
  id: string
  title: string
  messages: ChatMessage[]
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

function newConversation(): Conversation {
  return { id: crypto.randomUUID(), title: 'New chat', messages: [] }
}

function loadConversations(): Conversation[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return [newConversation()]
    const parsed = JSON.parse(raw)
    if (Array.isArray(parsed) && parsed.length > 0) return parsed
    return [newConversation()]
  } catch {
    return [newConversation()]
  }
}

function saveConversations(conversations: Conversation[]) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(conversations))
  } catch {
    // storage full or unavailable - fail silently, chat still works in-session
  }
}

interface ChatPageProps {
  role?: string
}

export default function ChatPage({ role }: ChatPageProps) {
  const navigate = useNavigate()
  const isAdmin = role === 'admin'

  const [conversations, setConversations] = useState<Conversation[]>(() => loadConversations())
  const [activeId, setActiveId] = useState(conversations[0].id)
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const bottomRef = useRef<HTMLDivElement>(null)

  const active = conversations.find((c) => c.id === activeId) ?? conversations[0]

  useEffect(() => {
    saveConversations(conversations)
  }, [conversations])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [active.messages.length, loading])

  const handleLogout = async () => {
    try { await logout() } finally { window.location.href = '/login' }
  }

  const handleNewChat = () => {
    const conv = newConversation()
    setConversations((prev) => [conv, ...prev])
    setActiveId(conv.id)
  }

  const updateActive = (updater: (c: Conversation) => Conversation) => {
    setConversations((prev) => prev.map((c) => (c.id === activeId ? updater(c) : c)))
  }

  const handleSend = async (e: React.FormEvent) => {
    e.preventDefault()
    const query = input.trim()
    if (!query || loading) return

    const userMsg: ChatMessage = { id: crypto.randomUUID(), role: 'user', query }
    updateActive((c) => ({
      ...c,
      title: c.messages.length === 0 ? query.slice(0, 40) : c.title,
      messages: [...c.messages, userMsg],
    }))
    setInput('')
    setLoading(true)

    try {
      const res = await api.post('/search', { query, limit: 5 })
      const assistantMsg: ChatMessage = {
        id: crypto.randomUUID(),
        role: 'assistant',
        results: res.data.results || [],
        hasAnswer: res.data.has_answer ?? true,
        normalizedQuery: res.data.normalized_query || '',
      }
      updateActive((c) => ({ ...c, messages: [...c.messages, assistantMsg] }))
    } catch (err: any) {
      const assistantMsg: ChatMessage = {
        id: crypto.randomUUID(),
        role: 'assistant',
        error: err.response?.data?.detail || 'Search failed',
      }
      updateActive((c) => ({ ...c, messages: [...c.messages, assistantMsg] }))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{ display: 'flex', height: '100vh', overflow: 'hidden', fontFamily: font, background: color.bg }}>
      <aside
        style={{
          width: '260px',
          background: color.surface,
          borderRight: `1px solid ${color.border}`,
          display: 'flex',
          flexDirection: 'column',
          flexShrink: 0,
        }}
      >
        {isAdmin && (
          <button
            onClick={() => navigate('/documents')}
            style={{
              display: 'flex', alignItems: 'center', gap: '8px', width: '100%',
              padding: '14px 16px', borderBottom: `1px solid ${color.border}`,
              background: 'transparent', border: 'none', cursor: 'pointer',
              fontSize: '13px', fontWeight: 500, color: color.textSecondary, textAlign: 'left',
            }}
            onMouseEnter={(e) => (e.currentTarget.style.color = color.adminAccent)}
            onMouseLeave={(e) => (e.currentTarget.style.color = color.textSecondary)}
          >
            <ArrowLeft size={15} strokeWidth={2} />
            Back to dashboard
          </button>
        )}

        <div style={{ padding: '16px', borderBottom: `1px solid ${color.border}` }}>
          <button
            onClick={handleNewChat}
            style={{
              display: 'flex', alignItems: 'center', gap: '8px', width: '100%',
              padding: '10px 12px', borderRadius: radius.sm,
              background: color.chatAccentSoft, color: color.chatAccentHover,
              border: 'none', cursor: 'pointer', fontSize: '13.5px', fontWeight: 600,
            }}
          >
            <Plus size={16} strokeWidth={2.25} />
            New chat
          </button>
        </div>

        <div style={{ flex: 1, overflowY: 'auto', padding: '10px 10px' }}>
          <div style={{ fontSize: '10.5px', fontWeight: 600, color: color.textTertiary, textTransform: 'uppercase', letterSpacing: '0.05em', padding: '6px 8px' }}>
            Chats
          </div>
          {conversations.map((c) => (
            <button
              key={c.id}
              onClick={() => setActiveId(c.id)}
              style={{
                display: 'flex', alignItems: 'center', gap: '8px', width: '100%',
                padding: '9px 10px', borderRadius: radius.sm, marginBottom: '2px',
                background: c.id === activeId ? color.chatAccentSoft : 'transparent',
                color: c.id === activeId ? color.chatAccentHover : color.textSecondary,
                border: 'none', cursor: 'pointer', fontSize: '13px', fontWeight: 500,
                textAlign: 'left', overflow: 'hidden',
              }}
            >
              <MessageSquare size={14} style={{ flexShrink: 0 }} />
              <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {c.title}
              </span>
            </button>
          ))}
        </div>

        <div style={{ borderTop: `1px solid ${color.border}`, padding: '10px' }}>
          <button
            onClick={handleLogout}
            style={{
              display: 'flex', alignItems: 'center', gap: '8px', width: '100%',
              padding: '10px 12px', borderRadius: radius.sm,
              background: 'transparent', border: 'none', cursor: 'pointer',
              fontSize: '13.5px', fontWeight: 500, color: color.textSecondary, textAlign: 'left',
            }}
            onMouseEnter={(e) => (e.currentTarget.style.color = color.danger)}
            onMouseLeave={(e) => (e.currentTarget.style.color = color.textSecondary)}
          >
            <LogOut size={15} strokeWidth={2} />
            Log out
          </button>
        </div>
      </aside>

      <main style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
        <div style={{ flex: 1, overflowY: 'auto', padding: '24px 0' }}>
          <div style={{ maxWidth: '760px', margin: '0 auto', padding: '0 24px', display: 'flex', flexDirection: 'column', gap: '20px' }}>
            {active.messages.length === 0 && (
              <div style={{ textAlign: 'center', padding: '80px 20px', color: color.textTertiary }}>
                <div style={{ fontSize: '16px', fontWeight: 600, color: color.textPrimary, marginBottom: '6px' }}>
                  Ask about your documents
                </div>
                <div style={{ fontSize: '13.5px' }}>
                  Results are scoped to what your role can access.
                </div>
              </div>
            )}

            {active.messages.map((m) => (
              <div key={m.id}>
                {m.role === 'user' ? (
                  <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
                    <div
                      style={{
                        maxWidth: '75%', padding: '10px 16px', borderRadius: '16px 16px 4px 16px',
                        background: color.chatAccent, color: '#fff', fontSize: '14px', lineHeight: 1.5,
                      }}
                    >
                      {m.query}
                    </div>
                  </div>
                ) : m.error ? (
                  <div style={{ padding: '14px 16px', background: color.dangerSoft, color: color.danger, borderRadius: radius.md, fontSize: '13.5px' }}>
                    {m.error}
                  </div>
                ) : !m.hasAnswer ? (
                  <div style={{ padding: '20px', background: color.surface, border: `1px solid ${color.border}`, borderRadius: radius.lg }}>
                    <div style={{ fontSize: '14px', fontWeight: 500, color: color.textPrimary, marginBottom: '4px' }}>
                      No confident answer found
                    </div>
                    <div style={{ fontSize: '13px', color: color.textSecondary }}>
                      Try rephrasing your question, or check that the right documents have been uploaded.
                    </div>
                  </div>
                ) : (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                    <div style={{ fontSize: '12px', color: color.textTertiary, marginBottom: '2px' }}>
                      {m.results?.length} source{m.results?.length !== 1 ? 's' : ''} found
                    </div>
                    {m.results?.map((r, i) => {
                      const pct = confidencePercent(r)
                      const cColor = confidenceColor(pct)
                      return (
                        <div
                          key={r.chunk_id || i}
                          style={{ padding: '14px 16px', background: color.surface, borderRadius: radius.md, border: `1px solid ${color.border}` }}
                        >
                          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '12px', marginBottom: '8px' }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', minWidth: 0 }}>
                              <FileText size={14} style={{ color: color.textTertiary, flexShrink: 0 }} />
                              <span style={{ fontSize: '13px', fontWeight: 500, color: color.textPrimary, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                                {r.doc_name || r.filename || `Document ${r.doc_id ?? ''}`}
                              </span>
                              <span
                                style={{
                                  fontSize: '10px', fontWeight: 600, padding: '2px 7px', borderRadius: '20px',
                                  background: color.chatAccentSoft, color: color.chatAccentHover,
                                  textTransform: 'uppercase', letterSpacing: '0.02em', flexShrink: 0,
                                }}
                              >
                                {r.search_type}
                              </span>
                            </div>
                            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: '4px', flexShrink: 0 }}>
                              <span style={{ fontSize: '11.5px', fontWeight: 600, color: cColor }}>{pct.toFixed(0)}%</span>
                              <div style={{ width: '56px', height: '4px', borderRadius: '2px', background: color.border, overflow: 'hidden' }}>
                                <div style={{ width: `${Math.min(pct, 100)}%`, height: '100%', background: cColor }} />
                              </div>
                            </div>
                          </div>
                          <div style={{ fontSize: '12.5px', color: color.textSecondary, lineHeight: 1.5 }}>
                            {r.text_preview}
                          </div>
                        </div>
                      )
                    })}
                  </div>
                )}
              </div>
            ))}

            {loading && (
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: color.textTertiary, fontSize: '13px' }}>
                <Loader2 size={14} className="animate-spin" />
                Searching...
              </div>
            )}
            <div ref={bottomRef} />
          </div>
        </div>

        <form onSubmit={handleSend} style={{ padding: '16px 24px 24px', borderTop: `1px solid ${color.border}` }}>
          <div style={{ maxWidth: '760px', margin: '0 auto', display: 'flex', gap: '10px' }}>
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Ask a question about your documents..."
              style={{
                flex: 1, padding: '12px 16px', fontSize: '14.5px', fontFamily: font,
                border: `1px solid ${color.border}`, borderRadius: radius.md, outline: 'none',
                background: color.surface, color: color.textPrimary,
              }}
              onFocus={(e) => (e.currentTarget.style.borderColor = color.chatAccent)}
              onBlur={(e) => (e.currentTarget.style.borderColor = color.border)}
            />
            <button
              type="submit"
              disabled={loading || !input.trim()}
              style={{
                padding: '12px 18px',
                background: loading || !input.trim() ? color.borderStrong : color.chatAccent,
                color: '#fff', border: 'none', borderRadius: radius.md,
                cursor: loading || !input.trim() ? 'not-allowed' : 'pointer',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
              }}
            >
              <Send size={16} />
            </button>
          </div>
        </form>
      </main>
    </div>
  )
}
