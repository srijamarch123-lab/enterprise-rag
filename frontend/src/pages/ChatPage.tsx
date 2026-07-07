import { useState, useRef, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { Send, Plus, MessageSquare, ArrowLeft, LogOut, FileText, Loader2, Mic, ThumbsUp, ThumbsDown } from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import api, { logout, submitFeedback } from '../services/api'
import { theme } from '../theme'
import './ChatPage.css'


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

interface ChatMessage {
  id: string | number
  role: 'user' | 'assistant'
  content?: string
  query?: string
  answer?: string
  results?: SearchResult[]
  hasAnswer?: boolean
  normalizedQuery?: string
  error?: string
  metadata?: Record<string, any>
  suggestions?: string[]
  feedbackSubmitted?: 'up' | 'down'
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

interface ChatPageProps {
  role?: string
}

export default function ChatPage({ role }: ChatPageProps) {
  const navigate = useNavigate()
  const isAdmin = role === 'admin'

  const [conversations, setConversations] = useState<Conversation[]>([newConversation()])
  const [activeId, setActiveId] = useState<string | null>(null)
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [listening, setListening] = useState(false)
  const bottomRef = useRef<HTMLDivElement>(null)
  const recognitionRef = useRef<any>(null)

  // Feedback collection states
  const [feedbackMsgId, setFeedbackMsgId] = useState<number | string | null>(null)
  const [feedbackHelpful, setFeedbackHelpful] = useState<boolean | null>(null)
  const [feedbackComment, setFeedbackComment] = useState('')
  const [feedbackLoading, setFeedbackLoading] = useState(false)

  const active = conversations.find((c) => c.id === activeId) ?? conversations[0]

  useEffect(() => {
    const loadSessions = async () => {
      try {
        const { data } = await api.get('/chat/sessions')
        if (Array.isArray(data) && data.length > 0) {
          const loaded = data.map((s: any) => ({ id: String(s.id), title: s.title || 'New chat', messages: [] }))
          setConversations(loaded)
          setActiveId(loaded[0].id)
        }
      } catch {
        setConversations([newConversation()])
        setActiveId(null)
      }
    }
    loadSessions()
  }, [])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [active.messages.length, loading])

  const handleLogout = async () => {
    try { await logout() } finally { window.location.href = '/login' }
  }

  const handleNewChat = async () => {
    try {
      const { data } = await api.post('/chat/sessions', { title: 'New chat' })
      const conv = { id: String(data.id), title: data.title || 'New chat', messages: [] }
      setConversations((prev) => [conv, ...prev])
      setActiveId(conv.id)
    } catch {
      const conv = newConversation()
      setConversations((prev) => [conv, ...prev])
      setActiveId(conv.id)
    }
  }

  const loadSessionMessages = async (sessionId: string) => {
    try {
      const { data } = await api.get(`/chat/sessions/${sessionId}`)
      const mappedMessages = (data.messages || []).map((m: any) => {
        const metadataResults = Array.isArray(m?.metadata?.results) ? m.metadata.results : []
        const metadataSuggestions = Array.isArray(m?.metadata?.suggestions) ? m.metadata.suggestions : []
        return {
          id: m.id,
          role: m.role,
          content: m.content,
          answer: m.role === 'assistant' ? m.content : undefined,
          query: m.role === 'user' ? m.content : undefined,
          results: metadataResults,
          hasAnswer: typeof m?.metadata?.has_answer === 'boolean' ? m.metadata.has_answer : undefined,
          suggestions: metadataSuggestions,
          feedbackSubmitted: m?.metadata?.feedbackSubmitted,
        }
      })
      setConversations((prev) => prev.map((c) => (c.id === sessionId ? { ...c, messages: mappedMessages } : c)))
    } catch {
      // ignore load failures and keep local state
    }
  }

  const handleSend = async (e?: React.FormEvent, overrideQuery?: string) => {
    if (e) e.preventDefault()
    const query = (overrideQuery || input).trim()
    if (!query || loading) return

    let currentActiveId = activeId
    if (!currentActiveId) {
      const { data } = await api.post('/chat/sessions', { title: 'New chat' })
      currentActiveId = String(data.id)
      const conv = { id: currentActiveId, title: data.title || 'New chat', messages: [] }
      setConversations((prev) => [conv, ...prev])
      setActiveId(currentActiveId)
    }

    const userMsg: ChatMessage = { id: crypto.randomUUID(), role: 'user', query }
    setConversations((prev) => prev.map((c) => (c.id === currentActiveId ? { ...c, title: c.messages.length === 0 ? query.slice(0, 40) : c.title, messages: [...c.messages, userMsg] } : c)))
    setInput('')
    setLoading(true)
    setActiveId(currentActiveId)

    try {
      const response = await fetch(`/api/chat/sessions/${currentActiveId}/messages/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ content: query }),
      })
      const reader = response.body?.getReader()
      if (!reader) throw new Error('Streaming not available')
      const decoder = new TextDecoder()
      let streamed = ''
      let parsedResults: SearchResult[] = []
      let hasAnswer = true
      let suggestions: string[] = []
      let actualDbId: number | string | undefined = undefined

      const assistantMsgTempId = crypto.randomUUID()
      const assistantMsg: ChatMessage = { id: assistantMsgTempId, role: 'assistant', answer: '', results: [], hasAnswer: true, suggestions: [] }
      setConversations((prev) => prev.map((c) => (c.id === currentActiveId ? { ...c, messages: [...c.messages, assistantMsg] } : c)))

      while (true) {
        const { value, done } = await reader.read()
        if (done) break
        const chunk = decoder.decode(value)
        const parts = chunk.split('\n\n')
        for (const part of parts) {
          const trimmed = part.trim()
          if (!trimmed) continue

          const lines = trimmed.split('\n').map((line) => line.trim())
          for (const line of lines) {
            if (!line.startsWith('data:')) continue
            const data = line.slice(5).trim()
            if (!data || data === '{}' || data === 'done' || data === 'error') continue
            if (data.startsWith('{') && data.endsWith('}')) {
              try {
                const parsed = JSON.parse(data)
                if (typeof parsed.answer === 'string') streamed = parsed.answer
                if (Array.isArray(parsed.results)) parsedResults = parsed.results
                if (typeof parsed.has_answer === 'boolean') hasAnswer = parsed.has_answer
                if (Array.isArray(parsed.suggestions)) suggestions = parsed.suggestions
                if (typeof parsed.message_id === 'number') actualDbId = parsed.message_id
              } catch {
                streamed += data
              }
            } else {
              streamed += data
            }

            setConversations((prev) =>
              prev.map((c) =>
                c.id === currentActiveId
                  ? {
                      ...c,
                      messages: c.messages.map((m) =>
                        m.id === assistantMsgTempId || m.id === actualDbId
                          ? {
                              ...m,
                              id: actualDbId || m.id,
                              answer: streamed,
                              results: parsedResults,
                              hasAnswer,
                              suggestions,
                            }
                          : m
                      ),
                    }
                  : c
              )
            )
          }
        }
      }
    } catch (err: any) {
      const assistantMsg: ChatMessage = { id: crypto.randomUUID(), role: 'assistant', error: err.response?.data?.detail || err.message || 'Chat failed' }
      setConversations((prev) => prev.map((c) => (c.id === currentActiveId ? { ...c, messages: [...c.messages, assistantMsg] } : c)))
    } finally {
      setLoading(false)
    }
  }

  const handleFeedbackInit = (msgId: number | string, helpful: boolean) => {
    setFeedbackMsgId(msgId)
    setFeedbackHelpful(helpful)
    setFeedbackComment('')
  }

  const handleFeedbackSubmit = async () => {
    if (!feedbackMsgId || feedbackHelpful === null) return
    setFeedbackLoading(true)
    try {
      await submitFeedback(Number(feedbackMsgId), feedbackHelpful, feedbackComment)
      setConversations((prev) =>
        prev.map((c) => ({
          ...c,
          messages: c.messages.map((msg) =>
            msg.id === feedbackMsgId
              ? { ...msg, feedbackSubmitted: feedbackHelpful ? 'up' : 'down' }
              : msg
          ),
        }))
      )
      setFeedbackMsgId(null)
      setFeedbackHelpful(null)
      setFeedbackComment('')
    } catch (err) {
      console.error("Failed to submit feedback", err)
    } finally {
      setFeedbackLoading(false)
    }
  }

  const startVoiceInput = () => {
    const SpeechRecognition = (window as any).webkitSpeechRecognition || (window as any).SpeechRecognition
    if (!SpeechRecognition) {
      window.alert('Voice input is not supported in this browser.')
      return
    }
    const recognition = new SpeechRecognition()
    recognition.lang = 'en-US'
    recognition.interimResults = false
    recognition.continuous = false
    recognitionRef.current = recognition
    recognition.onstart = () => setListening(true)
    recognition.onerror = () => setListening(false)
    recognition.onend = () => setListening(false)
    recognition.onresult = (event: any) => {
      const transcript = Array.from(event.results).map((r: any) => r[0].transcript).join(' ')
      setInput(transcript)
      if (transcript.trim()) {
        void handleSend(undefined, transcript)
      }
    }
    recognition.start()
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
              onClick={() => {
                setActiveId(c.id)
                void loadSessionMessages(c.id)
              }}
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
                    <div className="chat-page-message-bubble user-message-bubble">{m.query || m.content}</div>
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

                    {m.results && m.results.length > 0 ? (
                      <div className="chat-page-results-list">
                        <div className="chat-page-results-summary">
                          {m.results.length} source{m.results.length !== 1 ? 's' : ''} found
                        </div>
                        {m.results.map((r, i) => {
                          const pct = confidencePercent(r)
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
                              <div className="chat-page-result-preview">{(r as any).text || r.text_preview}</div>
                              {(r.file_path || r.path) ? (
                                <div className="chat-page-result-path">{r.file_path || r.path}</div>
                              ) : null}
                            </div>
                          )
                        })}
                      </div>
                    ) : null}

                    {m.suggestions && m.suggestions.length > 0 ? (
                      <div className="chat-page-suggestion-row" style={{ marginTop: '12px' }}>
                        {m.suggestions.map((suggestion) => (
                          <button
                            key={suggestion}
                            className="chat-page-suggestion-chip"
                            onClick={() => handleSend(undefined, suggestion)}
                            style={{
                              border: `1px solid ${color.border}`,
                              borderRadius: radius.lg,
                              padding: '6px 12px',
                              background: color.bg,
                              color: color.adminAccent,
                              cursor: 'pointer',
                              fontSize: '12.5px',
                              fontWeight: 500,
                              transition: 'all 0.12s',
                            }}
                            onMouseEnter={(e) => {
                              e.currentTarget.style.background = color.adminAccentSoft;
                              e.currentTarget.style.borderColor = color.adminAccent;
                            }}
                            onMouseLeave={(e) => {
                              e.currentTarget.style.background = color.bg;
                              e.currentTarget.style.borderColor = color.border;
                            }}
                          >
                            {suggestion}
                          </button>
                        ))}
                      </div>
                    ) : null}

                    <div style={{ marginTop: '12px', borderTop: `1px solid ${color.border}`, paddingTop: '10px' }}>
                      {m.feedbackSubmitted ? (
                        <div style={{ fontSize: '12.5px', display: 'flex', alignItems: 'center', gap: '6px', color: m.feedbackSubmitted === 'up' ? color.success : color.danger, fontWeight: 500 }}>
                          {m.feedbackSubmitted === 'up' ? (
                            <>
                              <ThumbsUp size={13} fill={color.success} /> Rated as helpful
                            </>
                          ) : (
                            <>
                              <ThumbsDown size={13} fill={color.danger} /> Rated as unhelpful
                            </>
                          )}
                        </div>
                      ) : feedbackMsgId === m.id ? (
                        <div style={{ background: '#fcfbf9', border: `1px dashed ${color.border}`, borderRadius: radius.md, padding: '12px', display: 'flex', flexDirection: 'column', gap: '8px', maxWidth: '400px' }}>
                          <div style={{ fontSize: '12px', fontWeight: 600, color: color.textPrimary }}>
                            {feedbackHelpful ? 'What did you find helpful?' : 'How can we improve this answer?'}
                          </div>
                          <textarea
                            value={feedbackComment}
                            onChange={(e) => setFeedbackComment(e.target.value)}
                            placeholder="Add optional comments..."
                            style={{
                              width: '100%',
                              minHeight: '60px',
                              fontSize: '12.5px',
                              padding: '8px',
                              borderRadius: radius.sm,
                              border: `1px solid ${color.border}`,
                              outline: 'none',
                              resize: 'vertical',
                              fontFamily: font
                            }}
                          />
                          <div style={{ display: 'flex', gap: '8px', justifyContent: 'flex-end' }}>
                            <button
                              onClick={() => {
                                setFeedbackMsgId(null);
                                setFeedbackHelpful(null);
                                setFeedbackComment('');
                              }}
                              style={{
                                padding: '4px 10px',
                                border: `1px solid ${color.border}`,
                                background: 'white',
                                borderRadius: radius.sm,
                                fontSize: '12px',
                                cursor: 'pointer'
                              }}
                            >
                              Cancel
                            </button>
                            <button
                              disabled={feedbackLoading}
                              onClick={handleFeedbackSubmit}
                              style={{
                                padding: '4px 12px',
                                border: 'none',
                                background: color.chatAccent,
                                color: 'white',
                                borderRadius: radius.sm,
                                fontSize: '12px',
                                fontWeight: 500,
                                cursor: 'pointer'
                              }}
                            >
                              {feedbackLoading ? 'Submitting...' : 'Submit'}
                            </button>
                          </div>
                        </div>
                      ) : (
                        <div className="chat-page-feedback-row" style={{ display: 'flex', gap: '8px' }}>
                          <button
                            className="chat-page-feedback-button"
                            onClick={() => handleFeedbackInit(m.id, true)}
                            style={{
                              display: 'inline-flex',
                              alignItems: 'center',
                              gap: '6px',
                              padding: '5px 12px',
                              border: `1px solid ${color.border}`,
                              borderRadius: '999px',
                              background: '#fff',
                              color: color.textSecondary,
                              cursor: 'pointer',
                              fontSize: '12px'
                            }}
                            aria-label="Helpful response"
                          >
                            <ThumbsUp size={13} /> Helpful
                          </button>
                          <button
                            className="chat-page-feedback-button"
                            onClick={() => handleFeedbackInit(m.id, false)}
                            style={{
                              display: 'inline-flex',
                              alignItems: 'center',
                              gap: '6px',
                              padding: '5px 12px',
                              border: `1px solid ${color.border}`,
                              borderRadius: '999px',
                              background: '#fff',
                              color: color.textSecondary,
                              cursor: 'pointer',
                              fontSize: '12px'
                            }}
                            aria-label="Unhelpful response"
                          >
                            <ThumbsDown size={13} /> Unhelpful
                          </button>
                        </div>
                      )}
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
              type="button"
              onClick={startVoiceInput}
              className={`chat-page-send-button ${listening ? 'listening' : ''}`}
              aria-label="Voice input"
            >
              <Mic size={16} />
            </button>
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
