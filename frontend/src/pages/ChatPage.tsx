import { useState, useRef, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { Send, Plus, MessageSquare, ArrowLeft, LogOut, FileText, Loader2, Mic, ThumbsUp, ThumbsDown, HardDrive, Upload, X, MoreHorizontal, Pencil, Trash2, Search, PanelLeftClose, PanelLeftOpen, Square, Sun, Moon } from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import api, { logout, submitFeedback, extractFileText, extractDriveFileText, getDriveFiles } from '../services/api'
import { useTheme } from '../ThemeContext'
import './ChatPage.css'



import { SearchResult, ChatMessage, Conversation } from '../types'

function confidencePercent(r: SearchResult): number {
  let val = 0
  if (typeof r.confidence_score === 'number' && r.confidence_score > 0) val = r.confidence_score * 100
  else if (typeof r.combined_score === 'number' && r.combined_score > 0) val = r.combined_score * 100
  else if (typeof r.semantic_score === 'number' && r.semantic_score > 0) val = r.semantic_score * 100
  else if (typeof r.score === 'number' && r.score > 0) val = r.score > 1 ? r.score : r.score * 100
  return Math.min(Math.max(val, 0), 100)
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
  const [fullText, setFullText] = useState<string | null>(null)
  const [loadingFullText, setLoadingFullText] = useState(false)
  const [viewMode, setViewMode] = useState<'snippet' | 'full'>('snippet')

  useEffect(() => {
    if (previewSource) {
      const docId = previewSource.document_id || (previewSource as any).doc_id
      if (docId) {
        setLoadingFullText(true)
        setFullText(null)
        setViewMode('snippet')
        api.get(`/documents/${docId}/text`)
          .then(res => {
            setFullText(res.data.extracted_text)
          })
          .catch(() => {
            setFullText("Could not load document text or permission denied.")
          })
          .finally(() => {
            setLoadingFullText(false)
          })
      } else {
        setFullText("Document ID not available for full text preview.")
        setLoadingFullText(false)
      }
    } else {
      setFullText(null)
    }
  }, [previewSource])

  const highlightSnippet = (textBody: string, snippet: string) => {
    if (!snippet || !textBody) return textBody;
    const index = textBody.toLowerCase().indexOf(snippet.toLowerCase().trim());
    if (index === -1) {
      // Fallback: try sentence overlap or return as is
      return textBody;
    }
    const before = textBody.substring(0, index);
    const matched = textBody.substring(index, index + snippet.length);
    const after = textBody.substring(index + snippet.length);
    return (
      <>
        {before}
        <mark style={{ backgroundColor: '#ffe066', padding: '2px 0', borderRadius: '2px', fontWeight: 'bold', color: 'black' }}>{matched}</mark>
        {after}
      </>
    );
  };

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
  const [driveFolderId, setDriveFolderId] = useState('')
  const [driveFiles, setDriveFiles] = useState<any[]>([])
  const [driveLoading, setDriveLoading] = useState(false)
  const [driveCredentials, setDriveCredentials] = useState<any>(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [groupBy, setGroupBy] = useState<'none' | 'date'>('none')
  const [menuOpenId, setMenuOpenId] = useState<string | null>(null)
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const { isDark, toggleDark, theme } = useTheme()
  const color = theme.color
  const radius = theme.radius
  const font = theme.font

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
    } catch (err: any) { alert("Delete failed: " + (err?.response?.data?.detail || err?.message)) }
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
      abortControllerRef.current = null
    }
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
      setDriveCredentials(parsed)
      setDriveFiles([])
      setDriveError('')
    } catch {
      setDriveError('Invalid JSON. Paste your service account credentials.')
    }
  }

  const handleBrowseDrive = async () => {
    if (!driveCredentials) return
    setDriveLoading(true)
    setDriveError('')
    try {
      const files = await getDriveFiles(driveCredentials, driveFolderId || undefined)
      setDriveFiles(files)
    } catch (err: any) {
      setDriveError(err.response?.data?.detail || 'Failed to list files from Google Drive')
    } finally {
      setDriveLoading(false)
    }
  }

  const handleSelectDriveFile = async (f: any) => {
    if (!driveCredentials) return
    setDriveLoading(true)
    setDriveError('')
    try {
      const result = await extractDriveFileText(driveCredentials, f)
      setSessionDoc({ filename: result.filename, text: result.text })
      setSessionDrive({ label: result.filename })
      setShowDriveModal(false)
      // Reset credentials/files state for next time
      setDriveCredentials(null)
      setDriveFiles([])
      setDriveFolderId('')
      setDriveJson('')
    } catch (err: any) {
      setDriveError(err.response?.data?.detail || 'Failed to connect document from Drive')
    } finally {
      setDriveLoading(false)
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

  const filteredConversations = searchQuery
    ? conversations.filter(c => c.title.toLowerCase().includes(searchQuery.toLowerCase()))
    : conversations

  const groupedConversations = filteredConversations.reduce((acc: Record<string, Conversation[]>, c) => {
    const group = 'Recent'
    if (!acc[group]) acc[group] = []
    acc[group].push(c)
    return acc
  }, {})

  const handleRename = async (sessionId: string, newTitle: string) => {
    try {
      await api.patch(`/chat/sessions/${sessionId}`, { title: newTitle })
      setConversations(prev => prev.map(c => c.id === sessionId ? { ...c, title: newTitle } : c))
    } catch (err: any) { alert("Delete failed: " + (err?.response?.data?.detail || err?.message)) }
  }

  const handleDelete = async (sessionId: string) => {
    if (!window.confirm('Delete this chat?')) return
    try {
      await api.delete(`/chat/sessions/${Number(sessionId)}`)
      setConversations(prev => prev.filter(c => String(c.id) !== String(sessionId)))
      if (activeId === sessionId) {
        const remaining = conversations.filter(c => c.id !== sessionId)
        if (remaining.length > 0) { setActiveId(remaining[0].id); loadSessionMessages(remaining[0].id) }
        else handleNewChat()
      }
    } catch (err: any) { alert("Delete failed: " + (err?.response?.data?.detail || err?.message)) }
  }

  return (
    <div className="chat-page-root" style={{ background: color.bg, color: color.textPrimary, fontFamily: font }}>
      <aside className="chat-page-sidebar" style={{
        width: sidebarOpen ? '260px' : '0',
        minWidth: sidebarOpen ? '260px' : '0',
        overflow: 'hidden',
        transition: 'width 0.2s ease, min-width 0.2s ease',
        background: isDark ? '#1a1a1a' : '#f0f4f0',
        borderRight: `1px solid ${isDark ? '#2e2e2e' : '#d0dbd0'}`,
        display: 'flex',
        flexDirection: 'column',
        height: '100vh',
        flexShrink: 0,
      }}>
        {/* Top: Dashboard link (admin only) */}
        {isAdmin && (
          <button onClick={() => navigate('/documents')}
            style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '14px 16px 10px', border: 'none', background: 'transparent', cursor: 'pointer', fontSize: '13px', fontWeight: 500, color: isDark ? '#6E9163' : '#4a7a5a', width: '100%', textAlign: 'left', borderBottom: `1px solid ${isDark ? '#2e2e2e' : '#d0dbd0'}` }}>
            <ArrowLeft size={14} /> Back to Dashboard
          </button>
        )}

        {/* Enterprise RAG title */}
        <div style={{ padding: '14px 16px 8px', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <span style={{ fontSize: '15px', fontWeight: 700, color: isDark ? '#6E9163' : '#3a6b3a', letterSpacing: '-0.02em' }}>Enterprise RAG</span>
          <button onClick={() => setSidebarOpen(false)} style={{ border: 'none', background: 'transparent', cursor: 'pointer', color: isDark ? '#666' : '#999', padding: '2px', display: 'flex', alignItems: 'center' }} title="Close sidebar">
            <PanelLeftClose size={16} />
          </button>
        </div>

        {/* New chat button */}
        <div style={{ padding: '0 12px 10px' }}>
          <button onClick={handleNewChat}
            style={{ width: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px', padding: '9px', borderRadius: '8px', border: `1px solid ${isDark ? '#3a3a3a' : '#c0d0c0'}`, background: isDark ? '#252525' : 'white', color: isDark ? '#e0e0e0' : '#2a2a2a', fontSize: '13px', fontWeight: 500, cursor: 'pointer' }}>
            <Plus size={15} /> New chat
          </button>
        </div>

        {/* Search */}
        <div style={{ padding: '0 12px 8px' }}>
          <div style={{ position: 'relative' }}>
            <Search size={13} style={{ position: 'absolute', left: '9px', top: '50%', transform: 'translateY(-50%)', color: isDark ? '#666' : '#888', pointerEvents: 'none' }} />
            <input type="text" placeholder="Search chats..." value={searchQuery} onChange={e => setSearchQuery(e.target.value)}
              style={{ width: '100%', padding: '7px 8px 7px 30px', fontSize: '12px', border: `1px solid ${isDark ? '#3a3a3a' : '#c0d0c0'}`, borderRadius: '7px', background: isDark ? '#252525' : 'white', color: isDark ? '#e0e0e0' : '#2a2a2a', outline: 'none', boxSizing: 'border-box' }} />
          </div>
        </div>

        {/* Group by */}
        <div style={{ padding: '0 12px 8px', display: 'flex', alignItems: 'center', gap: '6px' }}>
          <span style={{ fontSize: '11px', color: isDark ? '#666' : '#888' }}>Group by:</span>
          {(['none', 'date'] as const).map(g => (
            <button key={g} onClick={() => setGroupBy(g)}
              style={{ fontSize: '11px', padding: '3px 10px', borderRadius: '20px', border: `1px solid ${groupBy === g ? '#6E9163' : (isDark ? '#3a3a3a' : '#c0d0c0')}`, background: groupBy === g ? '#6E9163' : 'transparent', color: groupBy === g ? 'white' : (isDark ? '#999' : '#666'), cursor: 'pointer', textTransform: 'capitalize' }}>
              {g === 'none' ? 'None' : 'Date'}
            </button>
          ))}
        </div>

        {/* Chat list */}
        <div style={{ flex: 1, overflowY: 'auto', padding: '4px 8px' }}>
          {filteredConversations.length === 0 && searchQuery && (
            <div style={{ fontSize: '12px', color: isDark ? '#666' : '#999', textAlign: 'center', padding: '20px 0' }}>No chats found</div>
          )}
          {groupBy === 'none' ? filteredConversations.map((c) => (
            <div key={c.id} style={{ position: 'relative', display: 'flex', alignItems: 'center', borderRadius: '7px', marginBottom: '2px', background: c.id === activeId ? (isDark ? '#2e2e2e' : '#dceadc') : 'transparent' }}
              onMouseEnter={e => { const btn = e.currentTarget.querySelector('.dots-btn') as HTMLElement; if (btn) btn.style.opacity = '1' }}
              onMouseLeave={e => { const btn = e.currentTarget.querySelector('.dots-btn') as HTMLElement; if (btn && menuOpenId !== c.id) btn.style.opacity = '0' }}>
              <button onClick={() => { setActiveId(c.id); void loadSessionMessages(c.id) }}
                style={{ flex: 1, display: 'flex', alignItems: 'center', gap: '8px', padding: '8px 10px', border: 'none', background: 'transparent', cursor: 'pointer', textAlign: 'left', overflow: 'hidden', color: c.id === activeId ? (isDark ? '#e0e0e0' : '#1a3a1a') : (isDark ? '#b0b0b0' : '#3a3a3a'), fontSize: '13px' }}>
                <MessageSquare size={13} style={{ flexShrink: 0, opacity: 0.6 }} />
                <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{c.title}</span>
              </button>
              <button className="dots-btn" onClick={(e) => { e.stopPropagation(); setMenuOpenId(menuOpenId === c.id ? null : c.id) }}
                style={{ opacity: c.id === activeId ? 1 : 0, transition: 'opacity 0.1s', padding: '6px 6px', border: 'none', background: 'transparent', cursor: 'pointer', color: isDark ? '#888' : '#666', flexShrink: 0 }}>
                <MoreHorizontal size={14} />
              </button>
              {menuOpenId === c.id && (
                <div style={{ position: 'absolute', right: '4px', top: '100%', background: isDark ? '#2a2a2a' : 'white', border: `1px solid ${isDark ? '#3a3a3a' : '#d0d0d0'}`, borderRadius: '8px', boxShadow: '0 4px 16px rgba(0,0,0,0.15)', zIndex: 50, minWidth: '150px', padding: '4px' }} onClick={e => e.stopPropagation()}>
                  <button onClick={() => { const t = prompt('Rename chat:', c.title); if (t) handleRename(c.id, t); setMenuOpenId(null) }}
                    style={{ width: '100%', display: 'flex', alignItems: 'center', gap: '8px', padding: '8px 10px', border: 'none', background: 'transparent', cursor: 'pointer', fontSize: '13px', color: isDark ? '#e0e0e0' : '#2a2a2a', borderRadius: '6px' }}
                    onMouseEnter={e => e.currentTarget.style.background = isDark ? '#333' : '#f5f5f5'}
                    onMouseLeave={e => e.currentTarget.style.background = 'transparent'}>
                    <Pencil size={13} /> Rename
                  </button>
                  <button onClick={() => { handleDelete(c.id); setMenuOpenId(null) }}
                    style={{ width: '100%', display: 'flex', alignItems: 'center', gap: '8px', padding: '8px 10px', border: 'none', background: 'transparent', cursor: 'pointer', fontSize: '13px', color: '#e05050', borderRadius: '6px' }}
                    onMouseEnter={e => e.currentTarget.style.background = isDark ? '#2e1a1a' : '#fff0f0'}
                    onMouseLeave={e => e.currentTarget.style.background = 'transparent'}>
                    <Trash2 size={13} /> Delete
                  </button>
                </div>
              )}
            </div>
          )) : Object.entries(groupedConversations).map(([group, chats]) => (
            <div key={group}>
              <div style={{ fontSize: '10px', fontWeight: 600, color: isDark ? '#555' : '#999', textTransform: 'uppercase', letterSpacing: '0.07em', padding: '8px 10px 4px' }}>{group}</div>
              {(chats as Conversation[]).map((c) => (
                <div key={c.id} style={{ position: 'relative', display: 'flex', alignItems: 'center', borderRadius: '7px', marginBottom: '2px', background: c.id === activeId ? (isDark ? '#2e2e2e' : '#dceadc') : 'transparent' }}
                  onMouseEnter={e => { const btn = e.currentTarget.querySelector('.dots-btn') as HTMLElement; if (btn) btn.style.opacity = '1' }}
                  onMouseLeave={e => { const btn = e.currentTarget.querySelector('.dots-btn') as HTMLElement; if (btn && menuOpenId !== c.id) btn.style.opacity = '0' }}>
                  <button onClick={() => { setActiveId(c.id); void loadSessionMessages(c.id) }}
                    style={{ flex: 1, display: 'flex', alignItems: 'center', gap: '8px', padding: '8px 10px', border: 'none', background: 'transparent', cursor: 'pointer', textAlign: 'left', overflow: 'hidden', color: c.id === activeId ? (isDark ? '#e0e0e0' : '#1a3a1a') : (isDark ? '#b0b0b0' : '#3a3a3a'), fontSize: '13px' }}>
                    <MessageSquare size={13} style={{ flexShrink: 0, opacity: 0.6 }} />
                    <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{c.title}</span>
                  </button>
                  <button className="dots-btn" onClick={(e) => { e.stopPropagation(); setMenuOpenId(menuOpenId === c.id ? null : c.id) }}
                    style={{ opacity: c.id === activeId ? 1 : 0, transition: 'opacity 0.1s', padding: '6px 6px', border: 'none', background: 'transparent', cursor: 'pointer', color: isDark ? '#888' : '#666', flexShrink: 0 }}>
                    <MoreHorizontal size={14} />
                  </button>
                  {menuOpenId === c.id && (
                    <div style={{ position: 'absolute', right: '4px', top: '100%', background: isDark ? '#2a2a2a' : 'white', border: `1px solid ${isDark ? '#3a3a3a' : '#d0d0d0'}`, borderRadius: '8px', boxShadow: '0 4px 16px rgba(0,0,0,0.15)', zIndex: 50, minWidth: '150px', padding: '4px' }} onClick={e => e.stopPropagation()}>
                      <button onClick={() => { const t = prompt('Rename chat:', c.title); if (t) handleRename(c.id, t); setMenuOpenId(null) }}
                        style={{ width: '100%', display: 'flex', alignItems: 'center', gap: '8px', padding: '8px 10px', border: 'none', background: 'transparent', cursor: 'pointer', fontSize: '13px', color: isDark ? '#e0e0e0' : '#2a2a2a', borderRadius: '6px' }}
                        onMouseEnter={e => e.currentTarget.style.background = isDark ? '#333' : '#f5f5f5'}
                        onMouseLeave={e => e.currentTarget.style.background = 'transparent'}>
                        <Pencil size={13} /> Rename
                      </button>
                      <button onClick={() => { handleDelete(c.id); setMenuOpenId(null) }}
                        style={{ width: '100%', display: 'flex', alignItems: 'center', gap: '8px', padding: '8px 10px', border: 'none', background: 'transparent', cursor: 'pointer', fontSize: '13px', color: '#e05050', borderRadius: '6px' }}
                        onMouseEnter={e => e.currentTarget.style.background = isDark ? '#2e1a1a' : '#fff0f0'}
                        onMouseLeave={e => e.currentTarget.style.background = 'transparent'}>
                        <Trash2 size={13} /> Delete
                      </button>
                    </div>
                  )}
                </div>
              ))}
            </div>
          ))}
        </div>

        {/* Footer: dark mode toggle + logout */}
        <div style={{ padding: '10px 12px', borderTop: `1px solid ${isDark ? '#2e2e2e' : '#d0dbd0'}`, display: 'flex', flexDirection: 'column', gap: '6px' }}>
          <button onClick={toggleDark}
            style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '8px 10px', border: `1px solid ${isDark ? '#3a3a3a' : '#c0d0c0'}`, borderRadius: '7px', background: 'transparent', cursor: 'pointer', fontSize: '13px', color: isDark ? '#b0b0b0' : '#555', width: '100%' }}>
            {isDark ? <Sun size={14} /> : <Moon size={14} />}
            {isDark ? 'Light mode' : 'Dark mode'}
          </button>
          <button onClick={handleLogout}
            style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '8px 10px', border: 'none', background: 'transparent', cursor: 'pointer', fontSize: '13px', color: isDark ? '#888' : '#666', width: '100%' }}>
            <LogOut size={14} /> Log out
          </button>
        </div>
      </aside>

      <main className="chat-page-main" style={{ background: isDark ? "#212121" : "#f7f5f1" }}>
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



        {/* Sidebar toggle in top left of main area */}
        {!sidebarOpen && (
          <button onClick={() => setSidebarOpen(true)}
            style={{ position: 'fixed', top: '10px', left: '10px', zIndex: 100, background: isDark ? '#2a2a2a' : 'white', border: `1px solid ${isDark ? '#3a3a3a' : '#d0d0d0'}`, borderRadius: '7px', padding: '6px 8px', cursor: 'pointer', color: isDark ? '#b0b0b0' : '#555', display: 'flex', alignItems: 'center' }}>
            <PanelLeftOpen size={16} />
          </button>
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
                      <div className="chat-page-message-answer-plain" style={{ color: isDark ? "#f0f0f0" : "#2B2A27" }}>
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
                                  <span className={`chat-page-result-percent ${pct >= 70 ? 'success' : pct >= 40 ? 'warning' : 'danger'}`}>{Math.min(pct, 99).toFixed(0)}%</span>
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
                        <div style={{ background: color.surface, border: `1px dashed ${color.border}`, borderRadius: radius.md, padding: '12px', display: 'flex', flexDirection: 'column', gap: '8px', maxWidth: '400px' }}>
                          <div style={{ fontSize: '12px', fontWeight: 600, color: color.textPrimary }}>{feedbackHelpful ? 'What did you find helpful?' : 'How can we improve this answer?'}</div>
                          <textarea value={feedbackComment} onChange={(e) => setFeedbackComment(e.target.value)} placeholder="Add optional comments..." style={{ width: '100%', minHeight: '60px', fontSize: '12.5px', padding: '8px', borderRadius: radius.sm, border: `1px solid ${color.border}`, outline: 'none', resize: 'vertical', fontFamily: font, background: color.bg, color: color.textPrimary }} />
                          <div style={{ display: 'flex', gap: '8px', justifyContent: 'flex-end' }}>
                            <button onClick={() => { setFeedbackMsgId(null); setFeedbackHelpful(null); setFeedbackComment('') }} style={{ padding: '4px 10px', border: `1px solid ${color.border}`, background: color.surface, color: color.textPrimary, borderRadius: radius.sm, fontSize: '12px', cursor: 'pointer' }}>Cancel</button>
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

        <form onSubmit={handleSend} className="chat-page-form" style={{ background: isDark ? "#1a1a1a" : "white", borderTopColor: isDark ? "#2e2e2e" : undefined }}>
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

            <input type="text" value={input} onChange={(e) => setInput(e.target.value)} placeholder="Ask a question about your documents..." className="chat-page-input" style={{ background: isDark ? "#2a2a2a" : "white", color: isDark ? "#f0f0f0" : "#2B2A27", borderColor: isDark ? "#3a3a3a" : undefined }} />
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
          <div style={{ background: color.surface, borderRadius: radius.lg, padding: '24px', width: '520px', maxWidth: '90vw', boxShadow: '0 8px 40px rgba(0,0,0,0.12)', maxHeight: '80vh', display: 'flex', flexDirection: 'column' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px', flexShrink: 0 }}>
              <div style={{ fontSize: '15px', fontWeight: 600, color: color.textPrimary }}>Connect to Google Drive</div>
              <button onClick={() => { setShowDriveModal(false); setDriveCredentials(null); setDriveFiles([]); setDriveError(''); setDriveJson(''); }} style={{ border: 'none', background: 'transparent', cursor: 'pointer', color: color.textTertiary }}><X size={18} /></button>
            </div>
            
            {driveError && (
              <div style={{ color: color.danger, background: isDark ? '#2c1e1e' : '#fcebeb', padding: '8px 12px', borderRadius: radius.sm, fontSize: '12px', marginBottom: '12px', flexShrink: 0 }}>
                {driveError}
              </div>
            )}

            {!driveCredentials ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', flex: 1, overflowY: 'auto' }}>
                <div style={{ fontSize: '12px', color: color.textTertiary }}>
                  Upload your service account credentials JSON. This connection is only for this chat session.
                </div>
                <input
                  type="file"
                  accept=".json"
                  onChange={e => {
                    const file = e.target.files?.[0];
                    if (!file) return;
                    const reader = new FileReader();
                    reader.onload = (ev) => setDriveJson(ev.target?.result as string);
                    reader.readAsText(file);
                  }}
                  style={{ width: '100%', padding: '10px', border: `1px solid ${color.border}`, borderRadius: radius.sm, fontSize: '13px', cursor: 'pointer', background: isDark ? '#2a2a2a' : '#fff', color: color.textPrimary }}
                />
                {driveJson && <div style={{ fontSize: '11px', color: color.chatAccent }}>JSON file loaded successfully</div>}
                
                <div style={{ display: 'flex', gap: '10px', marginTop: '16px', justifyContent: 'flex-end', flexShrink: 0 }}>
                  <button onClick={() => { setShowDriveModal(false); setDriveError(''); setDriveJson(''); }} style={{ padding: '8px 16px', border: `1px solid ${color.border}`, borderRadius: radius.sm, background: 'white', fontSize: '13px', cursor: 'pointer', color: color.textSecondary }}>Cancel</button>
                  <button onClick={handleDriveConnect} disabled={!driveJson} style={{ padding: '8px 16px', border: 'none', borderRadius: radius.sm, background: color.chatAccent, color: 'white', fontSize: '13px', cursor: 'pointer', fontWeight: 500, opacity: !driveJson ? 0.6 : 1 }}>Next</button>
                </div>
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', flex: 1, overflow: 'hidden' }}>
                <div style={{ fontSize: '12px', color: color.textSecondary, background: color.chatAccentSoft, padding: '8px 12px', borderRadius: radius.sm, display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexShrink: 0 }}>
                  <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', marginRight: '8px' }}>Connected: <strong>{driveCredentials.client_email}</strong></span>
                  <button onClick={() => { setDriveCredentials(null); setDriveFiles([]); setDriveJson(''); }} style={{ border: 'none', background: 'transparent', cursor: 'pointer', color: color.chatAccent, fontSize: '11px', fontWeight: 600, flexShrink: 0 }}>Disconnect</button>
                </div>

                <div style={{ display: 'flex', gap: '8px', alignItems: 'center', flexShrink: 0 }}>
                  <input
                    type="text"
                    placeholder="Optional Folder ID (from Drive URL)..."
                    value={driveFolderId}
                    onChange={e => setDriveFolderId(e.target.value)}
                    style={{ flex: 1, padding: '8px 12px', border: `1px solid ${color.border}`, borderRadius: radius.sm, fontSize: '12.5px', background: isDark ? '#2a2a2a' : '#fff', color: color.textPrimary }}
                  />
                  <button
                    onClick={handleBrowseDrive}
                    disabled={driveLoading}
                    style={{ padding: '8px 16px', border: 'none', borderRadius: radius.sm, background: color.chatAccent, color: 'white', fontSize: '12.5px', cursor: 'pointer', fontWeight: 500, display: 'flex', alignItems: 'center', gap: '6px' }}
                  >
                    {driveLoading ? <Loader2 size={13} className="animate-spin" /> : <HardDrive size={13} />}
                    Browse
                  </button>
                </div>

                <div style={{ flex: 1, overflowY: 'auto', border: `1px solid ${color.border}`, borderRadius: radius.md, background: isDark ? '#1e1e1e' : '#fafafa', display: 'flex', flexDirection: 'column' }}>
                  {driveFiles.length === 0 ? (
                    <div style={{ padding: '40px 20px', textAlign: 'center', color: color.textTertiary, fontSize: '12.5px' }}>
                      {driveLoading ? 'Loading files...' : 'No files loaded. Click Browse to view available files.'}
                    </div>
                  ) : (
                    <div style={{ display: 'flex', flexDirection: 'column' }}>
                      <div style={{ padding: '8px 12px', borderBottom: `1px solid ${color.border}`, fontSize: '11px', color: color.textTertiary, fontWeight: 500, flexShrink: 0 }}>
                        {driveFiles.length} supported files found
                      </div>
                      {driveFiles.map((f, i) => (
                        <div
                          key={f.drive_file_id}
                          style={{
                            padding: '10px 12px',
                            borderBottom: i < driveFiles.length - 1 ? `1px solid ${color.border}` : 'none',
                            display: 'flex',
                            alignItems: 'center',
                            gap: '8px',
                            fontSize: '12.5px'
                          }}
                        >
                          <FileText size={14} style={{ color: color.chatAccent, flexShrink: 0 }} />
                          <div style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', color: color.textPrimary }} title={f.name}>
                            {f.name}
                          </div>
                          <span style={{ fontSize: '10px', color: color.textTertiary, textTransform: 'uppercase', flexShrink: 0 }}>{f.file_type}</span>
                          <button
                            onClick={() => handleSelectDriveFile(f)}
                            disabled={driveLoading}
                            style={{
                              padding: '4px 8px',
                              borderRadius: radius.sm,
                              border: `1px solid ${color.chatAccent}`,
                              background: color.chatAccentSoft,
                              color: color.chatAccent,
                              fontSize: '11px',
                              fontWeight: 500,
                              cursor: driveLoading ? 'not-allowed' : 'pointer'
                            }}
                          >
                            Select
                          </button>
                        </div>
                      ))}
                    </div>
                  )}
                </div>

                <div style={{ display: 'flex', justifyContent: 'flex-end', flexShrink: 0, marginTop: '8px' }}>
                  <button
                    onClick={() => { setShowDriveModal(false); setDriveCredentials(null); setDriveFiles([]); setDriveError(''); setDriveJson(''); }}
                    style={{ padding: '8px 16px', border: `1px solid ${color.border}`, borderRadius: radius.sm, background: 'white', fontSize: '13px', cursor: 'pointer', color: color.textSecondary }}
                  >
                    Close
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Citation Preview Modal */}
      {previewSource && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.5)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 200, padding: '20px' }}>
          <div style={{ background: color.surface, borderRadius: radius.lg, padding: '24px', width: '700px', maxWidth: '100%', maxHeight: '85vh', overflowY: 'auto', boxShadow: '0 8px 40px rgba(0,0,0,0.15)', display: 'flex', flexDirection: 'column' }}>
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

              {/* View Mode Tabs */}
              <div style={{ display: 'flex', gap: '8px', marginTop: '16px', borderBottom: `1px solid ${color.border}`, paddingBottom: '8px' }}>
                <button
                  type="button"
                  onClick={() => setViewMode('snippet')}
                  style={{
                    padding: '6px 12px',
                    border: 'none',
                    borderRadius: radius.sm,
                    background: viewMode === 'snippet' ? color.chatAccent : 'transparent',
                    color: viewMode === 'snippet' ? 'white' : color.textPrimary,
                    fontSize: '13px',
                    fontWeight: 500,
                    cursor: 'pointer'
                  }}
                >
                  Context Snippet
                </button>
                <button
                  type="button"
                  onClick={() => setViewMode('full')}
                  style={{
                    padding: '6px 12px',
                    border: 'none',
                    borderRadius: radius.sm,
                    background: viewMode === 'full' ? color.chatAccent : 'transparent',
                    color: viewMode === 'full' ? 'white' : color.textPrimary,
                    fontSize: '13px',
                    fontWeight: 500,
                    cursor: 'pointer'
                  }}
                >
                  Full Document
                </button>
              </div>
              
              <div style={{ marginTop: '12px' }}>
                {viewMode === 'snippet' ? (
                  <>
                    <div style={{ fontWeight: 600, marginBottom: '8px' }}>Matched Context Snippet:</div>
                    <div style={{ background: '#fcfbf9', border: `1px solid ${color.border}`, borderRadius: radius.md, padding: '16px', maxHeight: '300px', overflowY: 'auto', whiteSpace: 'pre-wrap', fontFamily: font, fontSize: '13px', lineHeight: 1.5 }}>
                      {(previewSource as any).parent_text || (previewSource as any).text || previewSource.text_preview}
                    </div>
                  </>
                ) : (
                  <>
                    <div style={{ fontWeight: 600, marginBottom: '8px' }}>Full Extracted Text (Matched Citation Highlighted):</div>
                    {loadingFullText ? (
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '13.5px', color: color.textSecondary, padding: '20px' }}>
                        <Loader2 size={16} className="animate-spin" /> Loading full document text...
                      </div>
                    ) : (
                      <div style={{ background: '#fcfbf9', border: `1px solid ${color.border}`, borderRadius: radius.md, padding: '16px', maxHeight: '350px', overflowY: 'auto', whiteSpace: 'pre-wrap', fontFamily: font, fontSize: '13px', lineHeight: 1.6 }}>
                        {highlightSnippet(fullText || '', (previewSource as any).parent_text || (previewSource as any).text || previewSource.text_preview || '')}
                      </div>
                    )}
                  </>
                )}
              </div>
            </div>
          </div>
        </div>
      )}

      <input ref={fileInputRef} type="file" accept=".pdf,.docx,.pptx,.txt,.png,.jpg,.jpeg,.csv,.xlsx,.xls,.md" style={{ display: 'none' }} onChange={handleFileUpload} />
    </div>
  )
}
