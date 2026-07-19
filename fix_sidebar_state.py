content = open('frontend/src/pages/ChatPage.tsx', 'r', encoding='utf-8', errors='ignore').read()

# Add missing imports
old_import = "import { Send, Plus, MessageSquare, ArrowLeft, LogOut, FileText, Loader2, Mic, ThumbsUp, ThumbsDown, HardDrive, Upload, X } from 'lucide-react'"
new_import = "import { Send, Plus, MessageSquare, ArrowLeft, LogOut, FileText, Loader2, Mic, ThumbsUp, ThumbsDown, HardDrive, Upload, X, MoreHorizontal, Pencil, Trash2, Search, PanelLeftClose, PanelLeftOpen } from 'lucide-react'"
if old_import in content:
    content = content.replace(old_import, new_import)
    print('Imports fixed')
else:
    idx = content.find("from 'lucide-react'")
    print('Import not found, at:', idx)

# Add state variables
old_state = "  const [uploadingDoc, setUploadingDoc] = useState(false)"
new_state = """  const [uploadingDoc, setUploadingDoc] = useState(false)
  const [searchQuery, setSearchQuery] = useState('')
  const [groupBy, setGroupBy] = useState<'none' | 'date'>('none')
  const [menuOpenId, setMenuOpenId] = useState<string | null>(null)
  const [sidebarOpen, setSidebarOpen] = useState(true)"""

if old_state in content:
    content = content.replace(old_state, new_state)
    print('State added')
else:
    print('State not found')

# Add helper functions before return
old_return = "  return (\n    <div className=\"chat-page-root\">"
new_return = """  const filteredConversations = searchQuery
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
    } catch {}
  }

  const handleDelete = async (sessionId: string) => {
    if (!window.confirm('Delete this chat?')) return
    try {
      await api.delete(`/chat/sessions/${sessionId}`)
      setConversations(prev => prev.filter(c => c.id !== sessionId))
      if (activeId === sessionId) {
        const remaining = conversations.filter(c => c.id !== sessionId)
        if (remaining.length > 0) { setActiveId(remaining[0].id); loadSessionMessages(remaining[0].id) }
        else handleNewChat()
      }
    } catch {}
  }

  return (
    <div className="chat-page-root">"""

if old_return in content:
    content = content.replace(old_return, new_return)
    print('Functions added')
else:
    print('Return not found')

# Add sidebar toggle button in topbar
old_topbar = """        <div className="chat-page-content-wrap">"""
new_topbar = """        {/* Sidebar toggle button */}
        <button onClick={() => setSidebarOpen(o => !o)}
          style={{ position: 'fixed', top: '12px', left: sidebarOpen ? '252px' : '12px', zIndex: 100, background: 'white', border: `1px solid ${color.border}`, borderRadius: '6px', padding: '5px', cursor: 'pointer', color: color.textSecondary, transition: 'left 0.2s', display: 'flex', alignItems: 'center' }}>
          {sidebarOpen ? <PanelLeftClose size={16} /> : <PanelLeftOpen size={16} />}
        </button>
        <div className="chat-page-content-wrap">"""

if old_topbar in content:
    content = content.replace(old_topbar, new_topbar)
    print('Toggle button added')
else:
    print('Topbar not found')

# Make sidebar collapsible
old_aside = '      <aside className="chat-page-sidebar">'
new_aside = '      <aside className="chat-page-sidebar" style={{ width: sidebarOpen ? undefined : "0", overflow: sidebarOpen ? undefined : "hidden", minWidth: sidebarOpen ? undefined : "0", borderRight: sidebarOpen ? undefined : "none", transition: "width 0.2s, min-width 0.2s" }}>'

if old_aside in content:
    content = content.replace(old_aside, new_aside)
    print('Sidebar collapsible added')
else:
    print('Aside not found')

open('frontend/src/pages/ChatPage.tsx', 'w', encoding='utf-8').write(content)
