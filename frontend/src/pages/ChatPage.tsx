import { useState, useRef, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { Send, Plus, MessageSquare, ArrowLeft, LogOut, FileText, Loader2, Mic, ThumbsUp, ThumbsDown, HardDrive, Upload, X, Square } from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import api, { logout, submitFeedback, extractFileText } from '../services/api'
import { theme } from '../theme'
import './ChatPage.css'

const { color, font, radius } = theme

import { SearchResult, ChatMessage, Conversation } from '../types'

function confidencePercent(r: SearchResult): number {
  if (typeof r.confidence_score === 'number') return r.confidence_score * 100
  if (typeof r.combined_score === 'number') return r.combined_score * 100
  if (r.search_type === 'semantic' && typeof r.semantic_score === 'number') return r.semantic_score * 100
  return 0
}

function newConversation(): Conversation {
  return { id: crypto.randomUUID(), title: 'New chat', messages: [] }
}

interface ChatPageProps {
  role?: string
  onLogout?: () => void
}

export default function ChatPage({ role, onLogout }: ChatPageProps) {
  const navigate = useNavigate()
  const isAdmin = role === 'admin'

  const [conversations, setConversations] = useState<Conversation[]>([newConversation()])
  const [activeId, setActiveId] = useState<string | null>(null)
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [listening, setListening] = useState(false)
  const bottomRef = useRef<HTMLDivElement>(null)
  const recognitionRef = useRef<any>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const plusRef = useRef<HTMLDivElement>(null)
  const abortControllerRef = useRef<AbortController | null>(null)
  const [previewSource, setPreviewSource] = useState<SearchResult | null>(null)
  // Filters
  const [filterDept, setFilterDept] = useState('')
  const [filterFileType, setFilterFileType] = useState('')
  const [filterDateRange, setFilterDateRange] = useState('')

  // Plus menu
  const [showPlus, setShowPlus] = useState(false)
  const [showDriveModal, setShowDriveModal] = useState(false)
  const [driveJson, setDriveJson] = useState('')
  const [driveError, setDriveError] = useState('')
  const [sessionDrive, setSessionDrive] = useState<{ label: string } | null>(null)
  const [sessionDoc, setSessionDoc] = useState<{ filename: string; text: string } | null>(null)
  const [uploadingDoc, setUploadingDoc] = useState(false)

  // Feedback
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

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (plusRef.current && !plusRef.current.contains(e.target as Node)) setShowPlus(false)
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  const handleLogout = async () => {
    try { await logout() } catch {}
    if (onLogout) onLogout()
    else window.location.href = '/login'
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
    setSessionDrive(null)
    setSessionDoc(null)
  }

  const loadSessionMessages = async (sessionId: string, mergeOnly = false) => {
    try {
      const { data } = await api.get(`/chat/sessions/${sessionId}`)
      const mappedMessages = (data.messages || []).map((m: any) => ({
        id: m.id,
        role: m.role,
        content: m.content,
        answer: m.role === 'assistant' ? m.content : undefined,
        query: m.role === 'user' ? m.content : undefined,
        results: Array.isArray(m?.metadata?.results) ? m.metadata.results : [],
        hasAnswer: typeof m?.metadata?.has_answer === 'boolean' ? m.metadata.has_answer : undefined,
        suggestions: Array.isArray(m?.metadata?.suggestions) ? m.metadata.suggestions : [],
        feedbackSubmitted: m?.metadata?.feedbackSubmitted,
      }))
      setConversations((prev) => prev.map((c) => {
        if (c.id !== sessionId) return c
        const title = data.title && data.title !== 'New chat' ? data.title : c.title
        if (mergeOnly) {
          const localIds = new Set(c.messages.map((m: any) => m.id))
          const hasTempIds = c.messages.some((m: any) => typeof m.id === 'string' && m.id.length > 20)
          if (!hasTempIds || mappedMessages.length >= c.messages.length) {
            return { ...c, title, messages: mappedMessages }
          }
          const newMsgs = mappedMessages.filter((m: any) => {
            if (localIds.has(m.id)) return false
            const existsInLocal = c.messages.some((local: any) => 
              local.role === m.role && 
              ((local.query || local.content || local.answer) === (m.query || m.content || m.answer))
            )
            return !existsInLocal && m.content
          })
          return { ...c, title, messages: [...c.messages, ...newMsgs] }
        }
        return { ...c, title, messages: mappedMessages }
      }))
      // Restore uploaded doc if session has one
      if (data.session_doc && data.session_doc_name) {
        setSessionDoc({ filename: data.session_doc_name, text: data.session_doc })
        setSessionDrive({ label: data.session_doc_name })
      } else {
        setSessionDoc(null)
        setSessionDrive(null)
      }
    } catch {}
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

    const userMsgTempId = crypto.randomUUID()
    const userMsg: ChatMessage = { id: userMsgTempId, role: 'user', query }
    setConversations((prev) => prev.map((c) => (c.id === currentActiveId ? { ...c, title: c.messages.length === 0 ? query.slice(0, 40) : c.title, messages: [...c.messages, userMsg] } : c)))
    setInput('')
    setLoading(true)
    setActiveId(currentActiveId)
    const controller = new AbortController()
    abortControllerRef.current = controller

    try {
      const baseUrl = import.meta.env.VITE_API_URL || ''
      const response = await fetch(`${baseUrl}/api/chat/sessions/${currentActiveId}/messages/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        signal: controller.signal,
        body: JSON.stringify({
          content: query,
          session_context: sessionDoc ? `The user has uploaded a document called "${sessionDoc.filename}". Use this as additional context:\n\n${sessionDoc.text}` : undefined,
          session_doc_name: sessionDoc?.filename,
          department: filterDept || undefined,
          file_type: filterFileType || undefined,
          date_range: filterDateRange || undefined,
        }),
      })
      const reader = response.body?.getReader()
      if (!reader) throw new Error('Streaming not available')
      const decoder = new TextDecoder()
      let streamed = ''
      let parsedResults: SearchResult[] = []
      let hasAnswer = true
      let suggestions: string[] = []
      let actualUserDbId: number | string | undefined = undefined
      let actualDbId: number | string | undefined = undefined

      const assistantMsgTempId = crypto.randomUUID()
      const assistantMsg: ChatMessage = { id: assistantMsgTempId, role: 'assistant', answer: '', results: [], hasAnswer: true, suggestions: [] }
      setConversations((prev) => prev.map((c) => (c.id === currentActiveId ? { ...c, messages: [...c.messages, assistantMsg] } : c)))

      let buffer = ''
      while (true) {
        const { value, done } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        const parts = buffer.split('\n\n')
        buffer = parts.pop() || ''
        
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
                if (typeof parsed.user_message_id === 'number') actualUserDbId = parsed.user_message_id
                if (typeof parsed.message_id === 'number') actualDbId = parsed.message_id
              } catch { streamed += data }
            } else { streamed += data }

            setConversations((prev) =>
              prev.map((c) =>
                c.id === currentActiveId
                  ? {
                      ...c,
                      messages: c.messages.map((m) => {
                        if ((m.id === userMsgTempId || m.id === actualUserDbId) && actualUserDbId) {
                          return { ...m, id: actualUserDbId }
                        }
                        if (m.id === assistantMsgTempId || m.id === actualDbId) {
                          return { ...m, id: actualDbId || m.id, answer: streamed, results: parsedResults, hasAnswer, suggestions }
                        }
                        return m
                      }),
                    }
                  : c
              )
            )
          }
        }
      }
    } catch (err: any) {
      if (err.name === 'AbortError') {
        console.log('Stream aborted')
      } else {
        const assistantMsg: ChatMessage = { id: crypto.randomUUID(), role: 'assistant', error: err.response?.data?.detail || err.message || 'Chat failed' }
        setConversations((prev) => prev.map((c) => (c.id === currentActiveId ? { ...c, messages: [...c.messages, assistantMsg] } : c)))
      }
    } finally {
      setLoading(false)
      if (currentActiveId) { setTimeout(() => loadSessionMessages(currentActiveId, true), 1500) }
      abortControllerRef  }
  }

  const handleStopGeneration = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort()
      abortControllerRef.current = null
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
    const numId = Number(feedbackMsgId)
    if (isNaN(numId)) {
      console.warn('Cannot submit feedback for non-numeric message ID:', feedbackMsgId)
      return
    }
    setFeedbackLoading(true)
    try {
      await submitFeedback(numId, feedbackHelpful, feedbackComment)
      setConversations((prev) => prev.map((c) => ({ ...c, messages: c.messages.map((msg) => msg.id === feedbackMsgId ? { ...msg, feedbackSubmitted: feedbackHelpful ? 'up' : 'down' } : msg) })))
      setFeedbackMsgId(null)
      setFeedbackHelpful(null)
      setFeedbackComment('')
    } catch (err) { console.error('Failed to submit feedback', err) }
    finally { setFeedbackLoading(false) }
  }

  const startVoiceInput = () => {
    const SpeechRecognition = (window as any).webkitSpeechRecognition || (window as any).SpeechRecognition
    if (!SpeechRecognition) { window.alert('Voice input is not supported in this browser.'); return }
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
      if (transcript.trim()) void handleSend(undefined, transcript)
    }
    recognition.start()
  }

  const handleDriveConnect = () => {
    setDriveError('')
    try {
      const parsed = JSON.parse(driveJson)
      setSessionDrive({ label: parsed.client_email || 'Drive connected' })
      setShowDriveModal(false)
      setDriveJson('')
    } catch {
      setDriveError('Invalid JSON. Paste your service account credentials.')
    }
  }

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    setShowPlus(false)
    setUploadingDoc(true)
    try {
      const result = await extractFileText(file)
      setSessionDoc({ filename: result.filename, text: result.text })
      setSessionDrive({ label: result.filename })
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to read file')
    } finally {
      setUploadingDoc(false)
      if (fileInputRef.current) fileInputRef.current.value = ''
    }
  }

  return (
    <div className="chat-page-root">
      <aside className="chat-page-sidebar">
        {isAdmin && (
          <button onClick={() => navigate('/documents')} className="chat-page-sidebar-link" aria-label="Back to dashboard">
            <ArrowLeft size={15} strokeWidth={2} />
            Back to dashboard
          </button>
        )}

        <div className="chat-page-sidebar-top">
          <button onClick={handleNewChat} className="chat-page-button chat-page-button-primary">
            <Plus size={16} strokeWidth={2.25} />
            New chat
          </button>
        </div>

        <div style={{ padding: '0 16px 16px', borderBottom: `1px solid ${color.border}` }}>
          <div style={{ fontSize: '11px', fontWeight: 600, color: '#5a8a6a', marginBottom: '8px', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Filters</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            <div>
              <label style={{ display: 'block', fontSize: '10px', color: '#888780', marginBottom: '3px' }}>Department</label>
              <input
                type="text"
                placeholder="e.g. HR, Finance"
                value={filterDept}
                onChange={(e) => setFilterDept(e.target.value)}
                style={{
                  width: '100%',
                  padding: '5px 8px',
                  fontSize: '12px',
                  borderRadius: '5px',
                  border: `1px solid ${color.border}`,
                  background: '#fcfbf9',
                  color: '#1a3d2a',
                  outline: 'none',
                  boxSizing: 'border-box',
                }}
              />
            </div>
            <div>
              <label style={{ display: 'block', fontSize: '10px', color: '#888780', marginBottom: '3px' }}>File Type</label>
              <select
                value={filterFileType}
                onChange={(e) => setFilterFileType(e.target.value)}
                style={{
                  width: '100%',
                  padding: '5px 8px',
                  fontSize: '12px',
                  borderRadius: '5px',
                  border: `1px solid ${color.border}`,
                  background: '#fcfbf9',
                  color: '#1a3d2a',
                  outline: 'none',
                  boxSizing: 'border-box',
                }}
              >
                <option value="">All Formats</option>
                <option value="pdf">PDF Document</option>
                <option value="docx">Word (DOCX)</option>
                <option value="pptx">PowerPoint</option>
                <option value="txt">Text File</option>
                <option value="png">PNG Image</option>
                <option value="jpg">JPG Image</option>
                <option value="csv">CSV Spreadsheet</option>
                <option value="xlsx">Excel (XLSX)</option>
                <option value="md">Markdown</option>
              </select>
            </div>
            <div>
              <label style={{ display: 'block', fontSize: '10px', color: '#888780', marginBottom: '3px' }}>Upload Date</label>
              <select
                value={filterDateRange}
                onChange={(e) => setFilterDateRange(e.target.value)}
                style={{
                  width: '100%',
                  padding: '5px 8px',
                  fontSize: '12px',
                  borderRadius: '5px',
                  border: `1px solid ${color.border}`,
                  background: '#fcfbf9',
                  color: '#1a3d2a',
                  outline: 'none',
                  boxSizing: 'border-box',
                }}
              >
                <option value="">All Time</option>
                <option value="today">Past 24 Hours</option>
                <option value="week">Past Week</option>
                <option value="month">Past Month</option>
                <option value="year">Past Year</option>
              </select>
            </div>
          </div>
        </div>

        <div className="chat-page-sidebar-list">
          <div className="chat-page-sidebar-heading">Chats</div>
          {conversations.map((c) => (
            <button
              key={c.id}
              onClick={() => { setActiveId(c.id); void loadSessionMessages(c.id) }}
              className={`chat-page-chat-item ${c.id === activeId ? 'active' : ''}`}
              aria-current={c.id === activeId ? 'page' : undefined}
            >
              <MessageSquare size={14} />
              <span className="chat-page-chat-title">{c.title}</span>
            </button>
          ))}
        </div>

        <div className="chat-page-sidebar-footer">
          <button onClick={handleLogout} className="chat-page-sidebar-link" aria-label="Log out">
            <LogOut size={15} strokeWidth={2} />
            Log out
          </button>
        </div>
      </aside>

      <main className="chat-page-main">
        {/* Session drive indicator */}
        {sessionDrive && (
          <div style={{ padding: '6px 24px', background: color.chatAccentSoft, borderBottom: `1px solid ${color.border}`, display: 'flex', alignItems: 'center', gap: '8px', fontSize: '12px', color: color.chatAccentHover }}>
            <HardDrive size={12} />
            {sessionDrive.label}  connected for this chat only
            <button onClick={() => setSessionDrive(null)} style={{ marginLeft: 'auto', border: 'none', background: 'transparent', cursor: 'pointer', color: color.textTertiary, display: 'flex', alignItems: 'center' }}>
              <X size={13} />
            </button>
          </div>
        )}

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
                    {(m.answer || m.content) ? (
                      <div className="chat-page-message-answer-plain">
                        <ReactMarkdown remarkPlugins={[remarkGfm]}>{m.answer || m.content || ""}</ReactMarkdown>
                      </div>
                    ) : loading && m.id === active.messages[active.messages.length - 1]?.id ? (
                      <div style={{ display: 'flex', alignItems: 'center', gap: '6px', color: '#8B8574', fontSize: '13px', padding: '4px 0' }}>
                        <span style={{ display: 'inline-block', width: '6px', height: '6px', borderRadius: '50%', background: '#6E9163', animation: 'pulse-dot 1s infinite' }} />
                        <span style={{ display: 'inline-block', width: '6px', height: '6px', borderRadius: '50%', background: '#6E9163', animation: 'pulse-dot 1s infinite 0.2s' }} />
                        <span style={{ display: 'inline-block', width: '6px', height: '6px', borderRadius: '50%', background: '#6E9163', animation: 'pulse-dot 1s infinite 0.4s' }} />
                      </div>
                    ) : null}

                    {m.results && m.results.length > 0 ? (
                      <div className="chat-page-results-list">
                        <div className="chat-page-results-summary">{m.results.length} source{m.results.length !== 1 ? 's' : ''} found</div>
                        {m.results.map((r, i) => {
                          const pct = confidencePercent(r)
                          return (
                            <div key={r.chunk_id || i} className="chat-page-result-card" onClick={() => setPreviewSource(r)} style={{ cursor: 'pointer' }}>
                              <div className="chat-page-result-header">
                                <div className="chat-page-result-meta">
                                  <FileText size={14} />
                                  <span className="chat-page-result-title">{r.doc_name || r.filename || `Document ${r.doc_id ?? ''}`}</span>
                                  <span className="chat-page-result-badge">{r.search_type}</span>
                                </div>
                                <div className="chat-page-result-score">
                                  <span className={`chat-page-result-percent ${pct >= 70 ? 'success' : pct >= 40 ? 'warning' : 'danger'}`}>{pct.toFixed(0)}%</span>
                                  <progress value={Math.min(pct, 100)} max={100} className={`chat-page-result-progress ${pct >= 70 ? 'success' : pct >= 40 ? 'warning' : 'danger'}`} />
                                </div>
                              </div>
                              <div className="chat-page-result-preview">{r.text || r.text_preview}</div>
                              {(r.file_path || r.path) ? <div className="chat-page-result-path">
                                {r.drive_url ? (
                                  <a href={r.drive_url} target="_blank" rel="noopener noreferrer" onClick={(e) => e.stopPropagation()} style={{ color: color.adminAccent, fontSize: "11px", textDecoration: "none", display: "flex", alignItems: "center", gap: "4px" }}>
                                    View in Google Drive
                                  </a>
                                ) : (r.file_path || r.path) ? (
                                  <span style={{ fontSize: "11px", color: color.textTertiary }}>{r.file_path || r.path}</span>
                                ) : null}
                              </div> : null}
                            </div>
                          )
                        })}
                      </div>
                    ) : null}

                    {m.suggestions && m.suggestions.length > 0 ? (
                      <div className="chat-page-suggestion-row" style={{ marginTop: '12px' }}>
                        {m.suggestions.map((suggestion) => (
                          <button key={suggestion} className="chat-page-suggestion-chip" onClick={() => handleSend(undefined, suggestion)}>{suggestion}</button>
                        ))}
                      </div>
                    ) : null}

                    <div style={{ marginTop: '12px', borderTop: `1px solid ${color.border}`, paddingTop: '10px' }}>
                      {m.feedbackSubmitted ? (
                        <div style={{ fontSize: '12.5px', display: 'flex', alignItems: 'center', gap: '6px', color: m.feedbackSubmitted === 'up' ? color.success : color.danger, fontWeight: 500 }}>
                          {m.feedbackSubmitted === 'up' ? <><ThumbsUp size={13} fill={color.success} /> Rated as helpful</> : <><ThumbsDown size={13} fill={color.danger} /> Rated as unhelpful</>}
                        </div>
                      ) : feedbackMsgId === m.id ? (
                        <div style={{ background: '#fcfbf9', border: `1px dashed ${color.border}`, borderRadius: radius.md, padding: '12px', display: 'flex', flexDirection: 'column', gap: '8px', maxWidth: '400px' }}>
                          <div style={{ fontSize: '12px', fontWeight: 600, color: color.textPrimary }}>{feedbackHelpful ? 'What did you find helpful?' : 'How can we improve this answer?'}</div>
                          <textarea value={feedbackComment} onChange={(e) => setFeedbackComment(e.target.value)} placeholder="Add optional comments..." style={{ width: '100%', minHeight: '60px', fontSize: '12.5px', padding: '8px', borderRadius: radius.sm, border: `1px solid ${color.border}`, outline: 'none', resize: 'vertical', fontFamily: font }} />
                          <div style={{ display: 'flex', gap: '8px', justifyContent: 'flex-end' }}>
                            <button onClick={() => { setFeedbackMsgId(null); setFeedbackHelpful(null); setFeedbackComment('') }} style={{ padding: '4px 10px', border: `1px solid ${color.border}`, background: 'white', borderRadius: radius.sm, fontSize: '12px', cursor: 'pointer' }}>Cancel</button>
                            <button disabled={feedbackLoading} onClick={handleFeedbackSubmit} style={{ padding: '4px 12px', border: 'none', background: color.chatAccent, color: 'white', borderRadius: radius.sm, fontSize: '12px', fontWeight: 500, cursor: 'pointer' }}>{feedbackLoading ? 'Submitting...' : 'Submit'}</button>
                          </div>
                        </div>
                      ) : (
                        <div className="chat-page-feedback-row">
                          <button className="chat-page-feedback-button" onClick={() => handleFeedbackInit(m.id, true)} aria-label="Helpful response"><ThumbsUp size={13} /> Helpful</button>
                          <button className="chat-page-feedback-button" onClick={() => handleFeedbackInit(m.id, false)} aria-label="Unhelpful response"><ThumbsDown size={13} /> Unhelpful</button>
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

            {/* Plus button */}
            <div ref={plusRef} style={{ position: 'relative', flexShrink: 0 }}>
              <button
                type="button"
                onClick={() => setShowPlus(p => !p)}
                style={{ width: '46px', height: '46px', borderRadius: radius.md, border: `1px solid ${color.border}`, background: color.surface, cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', color: color.textSecondary }}
              >
                <Plus size={18} />
              </button>
              {showPlus && (
                <div style={{ position: 'absolute', bottom: '54px', left: 0, background: color.surface, border: `1px solid ${color.border}`, borderRadius: radius.lg, padding: '6px', minWidth: '200px', boxShadow: '0 4px 20px rgba(0,0,0,0.08)', zIndex: 10 }}>
                  <button
                    type="button"
                    onClick={() => { setShowDriveModal(true); setShowPlus(false) }}
                    style={{ width: '100%', display: 'flex', alignItems: 'center', gap: '10px', padding: '10px 12px', border: 'none', background: 'transparent', borderRadius: radius.sm, cursor: 'pointer', fontSize: '13px', color: color.textPrimary }}
                    onMouseEnter={e => (e.currentTarget.style.background = color.chatAccentSoft)}
                    onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}
                  >
                    <HardDrive size={15} /> Connect to Drive
                  </button>
                  <button
                    type="button"
                    onClick={() => { fileInputRef.current?.click(); setShowPlus(false) }}
                    style={{ width: '100%', display: 'flex', alignItems: 'center', gap: '10px', padding: '10px 12px', border: 'none', background: 'transparent', borderRadius: radius.sm, cursor: 'pointer', fontSize: '13px', color: color.textPrimary }}
                    onMouseEnter={e => (e.currentTarget.style.background = color.chatAccentSoft)}
                    onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}
                  >
                    <Upload size={15} /> Upload document
                  </button>
                </div>
              )}
            </div>

            <input type="text" value={input} onChange={(e) => setInput(e.target.value)} placeholder="Ask a question about your documents..." className="chat-page-input" />
            {loading ? (
              <button type="button" onClick={handleStopGeneration} className="chat-page-stop-button" aria-label="Stop generation">
                <Square size={14} fill={color.chatAccent} color={color.chatAccent} style={{ marginRight: '6px' }} /> Stop
              </button>
            ) : (
              <>
                <button type="button" onClick={startVoiceInput} className={`chat-page-send-button ${listening ? 'listening' : ''}`} aria-label="Voice input"><Mic size={16} /></button>
                <button type="submit" disabled={!input.trim()} className="chat-page-send-button" aria-label="Send message"><Send size={16} /></button>
              </>
            )}
          </div>
        </form>
      </main>

      {/* Drive modal */}
      {showDriveModal && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.35)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 100 }}>
          <div style={{ background: color.surface, borderRadius: radius.lg, padding: '24px', width: '480px', maxWidth: '90vw', boxShadow: '0 8px 40px rgba(0,0,0,0.12)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
              <div style={{ fontSize: '15px', fontWeight: 600, color: color.textPrimary }}>Connect to Google Drive</div>
              <button onClick={() => setShowDriveModal(false)} style={{ border: 'none', background: 'transparent', cursor: 'pointer', color: color.textTertiary }}><X size={18} /></button>
            </div>
            <div style={{ fontSize: '12px', color: color.textTertiary, marginBottom: '12px' }}>
              Paste your service account credentials JSON. This connection is only for this chat session.
            </div>
            <textarea value={driveJson} onChange={e => setDriveJson(e.target.value)} placeholder='{ "type": "service_account", ... }' rows={8} style={{ width: '100%', border: `1px solid ${color.border}`, borderRadius: radius.sm, padding: '10px', fontSize: '12px', fontFamily: 'monospace', resize: 'vertical', outline: 'none', boxSizing: 'border-box' }} />
            {driveError && <div style={{ color: color.danger, fontSize: '12px', marginTop: '6px' }}>{driveError}</div>}
            <div style={{ display: 'flex', gap: '10px', marginTop: '16px', justifyContent: 'flex-end' }}>
              <button onClick={() => setShowDriveModal(false)} style={{ padding: '8px 16px', border: `1px solid ${color.border}`, borderRadius: radius.sm, background: 'white', fontSize: '13px', cursor: 'pointer', color: color.textSecondary }}>Cancel</button>
              <button onClick={handleDriveConnect} style={{ padding: '8px 16px', border: 'none', borderRadius: radius.sm, background: color.chatAccent, color: 'white', fontSize: '13px', cursor: 'pointer', fontWeight: 500 }}>Connect</button>
            </div>
          </div>
        </div>
      )}

      {/* Citation Preview Modal */}
      {previewSource && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.5)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 200, padding: '20px' }}>
          <div style={{ background: color.surface, borderRadius: radius.lg, padding: '24px', width: '600px', maxWidth: '100%', maxHeight: '85vh', overflowY: 'auto', boxShadow: '0 8px 40px rgba(0,0,0,0.15)', display: 'flex', flexDirection: 'column' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px', borderBottom: `1px solid ${color.border}`, paddingBottom: '12px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <FileText size={18} style={{ color: color.chatAccent }} />
                <span style={{ fontSize: '15px', fontWeight: 600, color: color.textPrimary }}>Source Document Details</span>
              </div>
              <button onClick={() => setPreviewSource(null)} style={{ border: 'none', background: 'transparent', cursor: 'pointer', color: color.textTertiary }}><X size={18} /></button>
            </div>
            
            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', fontSize: '13.5px', color: color.textPrimary, flex: 1 }}>
              <div>
                <strong>File Name:</strong> {previewSource.doc_name || previewSource.filename || 'Unknown'}
              </div>
              {previewSource.department && (
                <div>
                  <strong>Department:</strong> {previewSource.department}
                </div>
              )}
              {previewSource.access_level && (
                <div>
                  <strong>Access Level Required:</strong> {previewSource.access_level}
                </div>
              )}
              <div style={{ display: 'flex', gap: '16px' }}>
                <div>
                  <strong>Search Match Type:</strong> <span style={{ textTransform: 'capitalize', background: color.chatAccentSoft, padding: '2px 6px', borderRadius: radius.sm, fontSize: '12px', color: color.chatAccent }}>{previewSource.search_type}</span>
                </div>
                <div>
                  <strong>Confidence:</strong> {(confidencePercent(previewSource)).toFixed(0)}%
                </div>
              </div>
              {previewSource.file_path && (
                <div style={{ fontSize: '12px', color: color.textTertiary }}>
                  <strong>Path:</strong> {previewSource.file_path}
                </div>
              )}
              
              <div style={{ marginTop: '16px', borderTop: `1px solid ${color.border}`, paddingTop: '16px' }}>
                <div style={{ fontWeight: 600, marginBottom: '8px' }}>Matched Context Snippet:</div>
                <div style={{ background: '#fcfbf9', border: `1px solid ${color.border}`, borderRadius: radius.md, padding: '16px', maxHeight: '300px', overflowY: 'auto', whiteSpace: 'pre-wrap', fontFamily: font, fontSize: '13px', lineHeight: 1.5 }}>
                  {(previewSource as any).parent_text || (previewSource as any).text || previewSource.text_preview}
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      <input ref={fileInputRef} type="file" accept=".pdf,.docx,.pptx,.txt,.png,.jpg,.jpeg,.csv,.xlsx,.xls,.md" style={{ display: 'none' }} onChange={handleFileUpload} />
    </div>
  )
}
