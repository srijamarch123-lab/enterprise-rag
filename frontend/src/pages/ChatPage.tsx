import { useState, useRef, useEffect } from 'react'
import { Send, Plus, HardDrive, Upload, X, FileText, LogOut, MessageSquare } from 'lucide-react'
import { search, logout } from '../services/api'

interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  results?: any[]
  hasAnswer?: boolean
}

interface Chat {
  id: string
  title: string
  messages: Message[]
}

interface Props {
  onLogout?: () => void
}

export default function ChatPage({ onLogout }: Props) {
  const [chats, setChats] = useState<Chat[]>([{ id: '1', title: 'New chat', messages: [] }])
  const [activeChatId, setActiveChatId] = useState('1')
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [showPlus, setShowPlus] = useState(false)
  const [sessionDrive, setSessionDrive] = useState<{ connected: boolean; credentials_json: any; label: string } | null>(null)
  const [showDriveModal, setShowDriveModal] = useState(false)
  const [driveJson, setDriveJson] = useState('')
  const [driveError, setDriveError] = useState('')
  const bottomRef = useRef<HTMLDivElement>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const plusRef = useRef<HTMLDivElement>(null)

  const activeChat = chats.find(c => c.id === activeChatId)!

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [activeChat?.messages])

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (plusRef.current && !plusRef.current.contains(e.target as Node)) setShowPlus(false)
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  const newChat = () => {
    const id = Date.now().toString()
    setChats(prev => [{ id, title: 'New chat', messages: [] }, ...prev])
    setActiveChatId(id)
    setSessionDrive(null)
  }

  const handleSend = async () => {
    if (!input.trim() || loading) return
    const userText = input.trim()
    setInput('')

    const userMsg: Message = { id: Date.now().toString(), role: 'user', content: userText }

    setChats(prev => prev.map(c => {
      if (c.id !== activeChatId) return c
      const isFirst = c.messages.length === 0
      return {
        ...c,
        title: isFirst ? userText.slice(0, 40) : c.title,
        messages: [...c.messages, userMsg],
      }
    }))

    setLoading(true)
    try {
      const res = await search(userText, 5)
      const results: any[] = res.results || []
      const hasAnswer: boolean = res.has_answer ?? false

      let content = ''
      if (!hasAnswer || results.length === 0) {
        content = 'No confident answer found. Try rephrasing your question.'
      } else {
        content = results.map((r, i) =>
          `${i + 1}. ${r.filename}${r.page_number ? ` · Page ${r.page_number}` : ''}\n${r.text_preview}`
        ).join('\n\n')
      }

      const assistantMsg: Message = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content,
        results,
        hasAnswer,
      }

      setChats(prev => prev.map(c =>
        c.id === activeChatId ? { ...c, messages: [...c.messages, assistantMsg] } : c
      ))
    } catch {
      const errMsg: Message = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: 'Something went wrong. Please try again.',
        hasAnswer: false,
      }
      setChats(prev => prev.map(c =>
        c.id === activeChatId ? { ...c, messages: [...c.messages, errMsg] } : c
      ))
    } finally {
      setLoading(false)
    }
  }

  const handleDriveConnect = () => {
    setDriveError('')
    try {
      const parsed = JSON.parse(driveJson)
      setSessionDrive({ connected: true, credentials_json: parsed, label: parsed.client_email || 'Drive connected' })
      setShowDriveModal(false)
      setDriveJson('')
    } catch {
      setDriveError('Invalid JSON. Paste your service account credentials.')
    }
  }

  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    setSessionDrive({ connected: true, credentials_json: null, label: file.name })
    setShowPlus(false)
  }

  const handleLogout = async () => {
    try {
      await logout()
    } catch {
      // ignore
    } finally {
      if (onLogout) {
        onLogout()
      } else {
        window.location.href = '/login'
      }
    }
  }

  return (
    <div style={{ display: 'flex', height: '100vh', fontFamily: 'Inter, system-ui, sans-serif', background: '#f7faf8' }}>

      {/* Chat history sidebar */}
      <aside style={{ width: '240px', background: '#1a1a1a', display: 'flex', flexDirection: 'column', flexShrink: 0 }}>
        <div style={{ padding: '16px 12px 12px', borderBottom: '1px solid #2a2a2a' }}>
          <div style={{ fontSize: '13px', fontWeight: 600, color: '#e8f5ee', marginBottom: '12px' }}>Enterprise RAG</div>
          <button
            onClick={newChat}
            style={{ width: '100%', padding: '8px 12px', background: '#2a2a2a', border: '1px solid #3a3a3a', borderRadius: '8px', color: '#e0e0e0', fontSize: '13px', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '8px' }}
          >
            <Plus size={14} /> New chat
          </button>
        </div>

        <div style={{ flex: 1, overflow: 'auto', padding: '8px' }}>
          {chats.map(c => (
            <button
              key={c.id}
              onClick={() => setActiveChatId(c.id)}
              style={{ width: '100%', padding: '8px 10px', background: c.id === activeChatId ? '#2a2a2a' : 'transparent', border: 'none', borderRadius: '6px', color: c.id === activeChatId ? '#e8f5ee' : '#888', fontSize: '12px', cursor: 'pointer', textAlign: 'left', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '2px' }}
            >
              <MessageSquare size={12} style={{ flexShrink: 0 }} />
              {c.title}
            </button>
          ))}
        </div>

        <button
          onClick={handleLogout}
          style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '14px 16px', borderTop: '1px solid #2a2a2a', background: 'transparent', border: 'none', cursor: 'pointer', fontSize: '12px', color: '#888', width: '100%', textAlign: 'left' }}
        >
          <LogOut size={13} /> Log out
        </button>
      </aside>

      {/* Main chat area */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>

        {/* Top bar */}
        <div style={{ height: '48px', borderBottom: '1px solid #e0ece6', background: 'white', display: 'flex', alignItems: 'center', padding: '0 20px', justifyContent: 'space-between', flexShrink: 0 }}>
          <span style={{ fontSize: '14px', fontWeight: 500, color: '#1a5c2e' }}>
            {activeChat.title === 'New chat' ? 'Ask anything' : activeChat.title}
          </span>
          {sessionDrive?.connected && (
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '11px', color: '#4a7a5a', background: '#e8f5ee', padding: '3px 10px', borderRadius: '20px', border: '1px solid #c8e6d0' }}>
              <HardDrive size={11} />
              {sessionDrive.label}
              <X size={11} style={{ cursor: 'pointer', marginLeft: '2px' }} onClick={() => setSessionDrive(null)} />
            </div>
          )}
        </div>

        {/* Messages */}
        <div style={{ flex: 1, overflow: 'auto', padding: '24px 0' }}>
          {activeChat.messages.length === 0 ? (
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100%', gap: '12px' }}>
              <div style={{ fontSize: '28px', fontWeight: 300, color: '#1a5c2e' }}>What do you want to know?</div>
              <div style={{ fontSize: '14px', color: '#7a9a7a' }}>Search across your organisation's documents</div>
            </div>
          ) : (
            <div style={{ maxWidth: '720px', margin: '0 auto', padding: '0 24px', display: 'flex', flexDirection: 'column', gap: '24px' }}>
              {activeChat.messages.map(msg => (
                <div key={msg.id} style={{ display: 'flex', flexDirection: 'column', alignItems: msg.role === 'user' ? 'flex-end' : 'flex-start' }}>
                  {msg.role === 'user' ? (
                    <div style={{ background: '#1a5c2e', color: 'white', padding: '10px 16px', borderRadius: '18px 18px 4px 18px', fontSize: '14px', maxWidth: '80%', lineHeight: 1.5 }}>
                      {msg.content}
                    </div>
                  ) : (
                    <div style={{ maxWidth: '100%' }}>
                      {!msg.hasAnswer ? (
                        <div style={{ padding: '14px 18px', background: '#fff8e8', border: '1px solid #f0d080', borderRadius: '12px', fontSize: '13px', color: '#7a6020' }}>
                          No confident answer found. Try rephrasing your question.
                        </div>
                      ) : (
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                          {msg.results?.map((r: any, i: number) => (
                            <div key={i} style={{ background: 'white', border: '1px solid #e0ece6', borderRadius: '12px', padding: '14px 16px' }}>
                              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px' }}>
                                <FileText size={13} style={{ color: '#4a7a5a', flexShrink: 0 }} />
                                <span style={{ fontSize: '13px', fontWeight: 500, color: '#1a5c2e' }}>{r.filename}</span>
                                {r.page_number && <span style={{ fontSize: '11px', color: '#7a9a7a' }}>· Page {r.page_number}</span>}
                                <span style={{ marginLeft: 'auto', fontSize: '11px', background: '#e8f5ee', color: '#1a5c2e', padding: '2px 8px', borderRadius: '20px' }}>
                                  {r.combined_score ? `${(r.combined_score * 100).toFixed(1)}%` : `${((r.semantic_score || 0) * 100).toFixed(1)}%`}
                                </span>
                              </div>
                              <div style={{ fontSize: '13px', color: '#4a5a4a', lineHeight: 1.6 }}>{r.text_preview}</div>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              ))}
              {loading && (
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: '#7a9a7a', fontSize: '13px' }}>
                  <div style={{ width: '6px', height: '6px', background: '#4a7a5a', borderRadius: '50%', animation: 'pulse 1s infinite' }} />
                  Searching...
                </div>
              )}
              <div ref={bottomRef} />
            </div>
          )}
        </div>

        {/* Input area */}
        <div style={{ padding: '16px 24px 24px', background: 'white', borderTop: '1px solid #e0ece6', flexShrink: 0 }}>
          <div style={{ maxWidth: '720px', margin: '0 auto', position: 'relative' }}>
            <div style={{ display: 'flex', alignItems: 'flex-end', gap: '8px', background: '#f7faf8', border: '1.5px solid #c8e6d0', borderRadius: '16px', padding: '10px 12px' }}>

              {/* Plus button */}
              <div ref={plusRef} style={{ position: 'relative', flexShrink: 0 }}>
                <button
                  onClick={() => setShowPlus(p => !p)}
                  style={{ width: '32px', height: '32px', borderRadius: '50%', border: '1px solid #c8e6d0', background: 'white', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#4a7a5a' }}
                >
                  <Plus size={16} />
                </button>
                {showPlus && (
                  <div style={{ position: 'absolute', bottom: '44px', left: 0, background: 'white', border: '1px solid #e0ece6', borderRadius: '12px', padding: '6px', minWidth: '200px', boxShadow: '0 4px 20px rgba(0,0,0,0.1)', zIndex: 10 }}>
                    <button
                      onClick={() => { setShowDriveModal(true); setShowPlus(false) }}
                      style={{ width: '100%', display: 'flex', alignItems: 'center', gap: '10px', padding: '10px 12px', border: 'none', background: 'transparent', borderRadius: '8px', cursor: 'pointer', fontSize: '13px', color: '#1a5c2e' }}
                      onMouseEnter={e => (e.currentTarget.style.background = '#f0faf4')}
                      onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}
                    >
                      <HardDrive size={15} /> Connect to Drive
                    </button>
                    <button
                      onClick={() => { fileInputRef.current?.click(); setShowPlus(false) }}
                      style={{ width: '100%', display: 'flex', alignItems: 'center', gap: '10px', padding: '10px 12px', border: 'none', background: 'transparent', borderRadius: '8px', cursor: 'pointer', fontSize: '13px', color: '#1a5c2e' }}
                      onMouseEnter={e => (e.currentTarget.style.background = '#f0faf4')}
                      onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}
                    >
                      <Upload size={15} /> Upload document
                    </button>
                  </div>
                )}
              </div>

              <textarea
                value={input}
                onChange={e => setInput(e.target.value)}
                onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend() } }}
                placeholder="Ask a question about your documents..."
                rows={1}
                style={{ flex: 1, border: 'none', background: 'transparent', resize: 'none', outline: 'none', fontSize: '14px', color: '#1a1a1a', lineHeight: 1.5, maxHeight: '120px', overflowY: 'auto', paddingTop: '6px' }}
                onInput={e => {
                  const t = e.target as HTMLTextAreaElement
                  t.style.height = 'auto'
                  t.style.height = Math.min(t.scrollHeight, 120) + 'px'
                }}
              />

              <button
                onClick={handleSend}
                disabled={loading || !input.trim()}
                style={{ width: '36px', height: '36px', borderRadius: '10px', border: 'none', background: loading || !input.trim() ? '#c8e6d0' : '#1a5c2e', color: 'white', cursor: loading || !input.trim() ? 'not-allowed' : 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0, transition: 'background 0.15s' }}
              >
                <Send size={15} />
              </button>
            </div>
            <div style={{ textAlign: 'center', fontSize: '11px', color: '#7a9a7a', marginTop: '8px' }}>
              Press Enter to send · Shift+Enter for new line
            </div>
          </div>
        </div>
      </div>

      {/* Drive modal */}
      {showDriveModal && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.4)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 100 }}>
          <div style={{ background: 'white', borderRadius: '16px', padding: '24px', width: '480px', maxWidth: '90vw' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
              <div style={{ fontSize: '15px', fontWeight: 600, color: '#1a5c2e' }}>Connect to Google Drive</div>
              <button onClick={() => setShowDriveModal(false)} style={{ border: 'none', background: 'transparent', cursor: 'pointer', color: '#7a9a7a' }}><X size={18} /></button>
            </div>
            <div style={{ fontSize: '12px', color: '#7a9a7a', marginBottom: '12px' }}>
              Paste your service account credentials JSON. This connection is only for this chat session.
            </div>
            <textarea
              value={driveJson}
              onChange={e => setDriveJson(e.target.value)}
              placeholder='{ "type": "service_account", ... }'
              rows={8}
              style={{ width: '100%', border: '1px solid #c8e6d0', borderRadius: '8px', padding: '10px', fontSize: '12px', fontFamily: 'monospace', resize: 'vertical', outline: 'none', boxSizing: 'border-box' }}
            />
            {driveError && <div style={{ color: '#c00', fontSize: '12px', marginTop: '6px' }}>{driveError}</div>}
            <div style={{ display: 'flex', gap: '10px', marginTop: '16px', justifyContent: 'flex-end' }}>
              <button onClick={() => setShowDriveModal(false)} style={{ padding: '8px 16px', border: '1px solid #c8e6d0', borderRadius: '8px', background: 'white', fontSize: '13px', cursor: 'pointer', color: '#4a7a5a' }}>Cancel</button>
              <button onClick={handleDriveConnect} style={{ padding: '8px 16px', border: 'none', borderRadius: '8px', background: '#1a5c2e', color: 'white', fontSize: '13px', cursor: 'pointer' }}>Connect</button>
            </div>
          </div>
        </div>
      )}

      <input ref={fileInputRef} type="file" accept=".pdf,.docx,.pptx,.txt" style={{ display: 'none' }} onChange={handleFileUpload} />

      <style>{`@keyframes pulse { 0%,100%{opacity:1} 50%{opacity:0.3} }`}</style>
    </div>
  )
}
