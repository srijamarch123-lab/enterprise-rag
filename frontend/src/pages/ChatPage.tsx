import { useState, useRef, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { Send, Plus, MessageSquare, ArrowLeft, LogOut, FileText, Loader2 } from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import api from '../services/api'
import { logout } from '../services/api'
import { theme } from '../theme'
import './ChatPage.css'

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
  answer?: string
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
      const res = await api.post('/chat', { query, limit: 5 })
      const assistantMsg: ChatMessage = {
        id: crypto.randomUUID(),
        role: 'assistant',
        answer: res.data.answer || '',
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
    <div className="chat-page-root">
      <aside className="chat-page-sidebar">
        {isAdmin && (
          <button
            onClick={() => navigate('/documents')}
            className="chat-page-sidebar-link"
            aria-label="Back to dashboard"
          >
            <ArrowLeft size={15} strokeWidth={2} />
            Back to dashboard
          </button>
        )}

        <div className="chat-page-sidebar-top">
          <button
            onClick={handleNewChat}
            className="chat-page-button chat-page-button-primary"
          >
            <Plus size={16} strokeWidth={2.25} />
            New chat
          </button>
        </div>

        <div className="chat-page-sidebar-list">
          <div className="chat-page-sidebar-heading">Chats</div>
          {conversations.map((c) => (
            <button
              key={c.id}
              onClick={() => setActiveId(c.id)}
              className={`chat-page-chat-item ${c.id === activeId ? 'active' : ''}`}
              aria-current={c.id === activeId ? 'page' : undefined}
            >
              <MessageSquare size={14} />
              <span className="chat-page-chat-title">{c.title}</span>
            </button>
          ))}
        </div>

        <div className="chat-page-sidebar-footer">
          <button
            onClick={handleLogout}
            className="chat-page-sidebar-link"
            aria-label="Log out"
          >
            <LogOut size={15} strokeWidth={2} />
            Log out
          </button>
        </div>
      </aside>

      <main className="chat-page-main">
        <div className="chat-page-content-wrap">
          <div className="chat-page-content">
            {active.messages.length === 0 && (
              <div className="chat-page-empty-state">
                <div className="chat-page-empty-title">Ask about your documents</div>
                <div className="chat-page-empty-subtitle">Results are scoped to what your role can access.</div>
              </div>
            )}

            {active.messages.map((m) => (
              <div key={m.id}>
                {m.role === 'user' ? (
                  <div className="chat-page-message-row user-message-row">
                    <div className="chat-page-message-bubble user-message-bubble">{m.query}</div>
                  </div>
                ) : m.error ? (
                  <div className="chat-page-message-error">{m.error}</div>
                ) : (
                  <div className="chat-page-message-column">
                    {m.answer ? (
                      <div className="chat-page-message-answer">
                        <ReactMarkdown remarkPlugins={[remarkGfm]}>{m.answer}</ReactMarkdown>
                      </div>
                    ) : null}

                    <div className="chat-page-results-list">
                      <div className="chat-page-results-summary">
                        {m.results?.length} source{m.results?.length !== 1 ? 's' : ''} found
                      </div>
                      {m.results?.map((r, i) => {
                      const pct = confidencePercent(r)
                      const cColor = confidenceColor(pct)
                      return (
                        <div key={r.chunk_id || i} className="chat-page-result-card">
                          <div className="chat-page-result-header">
                            <div className="chat-page-result-meta">
                              <FileText size={14} />
                              <span className="chat-page-result-title">
                                {r.doc_name || r.filename || `Document ${r.doc_id ?? ''}`}
                              </span>
                              <span className="chat-page-result-badge">{r.search_type}</span>
                            </div>
                            <div className="chat-page-result-score">
                              <span className={`chat-page-result-percent ${pct >= 70 ? 'success' : pct >= 40 ? 'warning' : 'danger'}`}>{pct.toFixed(0)}%</span>
                              <progress
                                value={Math.min(pct, 100)}
                                max={100}
                                className={`chat-page-result-progress ${pct >= 70 ? 'success' : pct >= 40 ? 'warning' : 'danger'}`}
                              />
                            </div>
                          </div>
                          <div className="chat-page-result-preview">{r.text_preview}</div>
                        </div>
                      )
                    })}
                  </div>
                </div>
                )}
              </div>
            ))}

            {loading && (
              <div className="chat-page-loading">
                <Loader2 size={14} className="animate-spin" />
                Searching...
              </div>
            )}
            <div ref={bottomRef} />
          </div>
        </div>

        <form onSubmit={handleSend} className="chat-page-form">
          <div className="chat-page-form-row">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Ask a question about your documents..."
              className="chat-page-input"
            />
            <button
              type="submit"
              disabled={loading || !input.trim()}
              className="chat-page-send-button"
              aria-label="Send message"
            >
              <Send size={16} />
            </button>
          </div>
        </form>
      </main>
    </div>
  )
}
