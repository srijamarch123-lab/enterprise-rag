content = open('frontend/src/pages/ChatPage.tsx', 'r', encoding='utf-8', errors='ignore').read()

# Add Sun, Moon to imports
old_import = "import { Send, Plus, MessageSquare, ArrowLeft, LogOut, FileText, Loader2, Mic, ThumbsUp, ThumbsDown, HardDrive, Upload, X, MoreHorizontal, Pencil, Trash2, Search, PanelLeftClose, PanelLeftOpen, Square } from 'lucide-react'"
new_import = "import { Send, Plus, MessageSquare, ArrowLeft, LogOut, FileText, Loader2, Mic, ThumbsUp, ThumbsDown, HardDrive, Upload, X, MoreHorizontal, Pencil, Trash2, Search, PanelLeftClose, PanelLeftOpen, Square, Sun, Moon } from 'lucide-react'"
if old_import in content:
    content = content.replace(old_import, new_import)
    print('Sun/Moon imports added')
else:
    print('Import line not found - trying partial fix')
    idx = content.find("Square } from 'lucide-react'")
    if idx > 0:
        content = content[:idx] + "Square, Sun, Moon } from 'lucide-react'" + content[idx + len("Square } from 'lucide-react'"):]
        print('Partial import fix done')

# Fix dark mode to load from localStorage
old_dark_state = "  const [isDark, setIsDark] = useState(false)"
new_dark_state = "  const [isDark, setIsDark] = useState(() => localStorage.getItem('darkMode') === 'true')"
if old_dark_state in content:
    content = content.replace(old_dark_state, new_dark_state)
    print('Dark mode persistence added')
else:
    print('Dark state not found')

# Remove floating dark mode toggle button from topbar
old_toggle = """        {/* Dark mode toggle */}
        <button onClick={() => setIsDark(d => !d)}
          title={isDark ? 'Switch to light mode' : 'Switch to dark mode'}
          style={{ position: 'fixed', top: '12px', right: '16px', zIndex: 100, background: isDark ? '#2a2a2a' : 'white', border: `1px solid ${color.border}`, borderRadius: '6px', padding: '5px 10px', cursor: 'pointer', color: color.textSecondary, display: 'flex', alignItems: 'center', gap: '6px', fontSize: '12px' }}>
          {isDark ? '?? Light' : '?? Dark'}
        </button>"""
if old_toggle in content:
    content = content.replace(old_toggle, '')
    print('Floating toggle removed')
else:
    print('Floating toggle not found')

# Fix sidebar toggle button position - put it in the main header area instead of floating
old_sidebar_toggle = """        {/* Sidebar toggle button */}
        <button onClick={() => setSidebarOpen(o => !o)}
          style={{ position: 'fixed', top: '12px', left: sidebarOpen ? '252px' : '12px', zIndex: 100, background: 'white', border: `1px solid ${color.border}`, borderRadius: '6px', padding: '5px', cursor: 'pointer', color: color.textSecondary, transition: 'left 0.2s', display: 'flex', alignItems: 'center' }}>
          {sidebarOpen ? <PanelLeftClose size={16} /> : <PanelLeftOpen size={16} />}
        </button>"""
if old_sidebar_toggle in content:
    content = content.replace(old_sidebar_toggle, '')
    print('Old sidebar toggle removed')
else:
    print('Old sidebar toggle not found')

# Add sidebar toggle to topbar cleanly
old_topbar_content = '        <div className="chat-page-content-wrap">'
new_topbar_content = """        {/* Sidebar toggle in top left of main area */}
        {!sidebarOpen && (
          <button onClick={() => setSidebarOpen(true)}
            style={{ position: 'fixed', top: '10px', left: '10px', zIndex: 100, background: isDark ? '#2a2a2a' : 'white', border: `1px solid ${isDark ? '#3a3a3a' : '#d0d0d0'}`, borderRadius: '7px', padding: '6px 8px', cursor: 'pointer', color: isDark ? '#b0b0b0' : '#555', display: 'flex', alignItems: 'center' }}>
            <PanelLeftOpen size={16} />
          </button>
        )}
        <div className="chat-page-content-wrap">"""
if old_topbar_content in content:
    content = content.replace(old_topbar_content, new_topbar_content)
    print('Clean sidebar toggle added')
else:
    print('Content wrap not found')

# Add close sidebar button inside sidebar header
old_sidebar_title = '          <span style={{ fontSize: \'15px\', fontWeight: 700, color: isDark ? \'#6E9163\' : \'#3a6b3a\', letterSpacing: \'-0.02em\' }}>Enterprise RAG</span>'
new_sidebar_title = """          <span style={{ fontSize: '15px', fontWeight: 700, color: isDark ? '#6E9163' : '#3a6b3a', letterSpacing: '-0.02em' }}>Enterprise RAG</span>
          <button onClick={() => setSidebarOpen(false)} style={{ border: 'none', background: 'transparent', cursor: 'pointer', color: isDark ? '#666' : '#999', padding: '2px', display: 'flex', alignItems: 'center' }} title="Close sidebar">
            <PanelLeftClose size={16} />
          </button>"""
if old_sidebar_title in content:
    content = content.replace(old_sidebar_title, new_sidebar_title)
    print('Close button in sidebar added')
else:
    print('Sidebar title not found')

open('frontend/src/pages/ChatPage.tsx', 'w', encoding='utf-8').write(content)
