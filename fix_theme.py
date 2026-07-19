# Update theme.ts with dark mode support
theme_content = """// Design tokens with light and dark mode support
export const lightTheme = {
  color: {
    bg: '#F7F5F1',
    surface: '#FFFFFF',
    surfaceMuted: '#EDEAE1',
    border: '#DAD4C6',
    borderStrong: '#C7C0AE',
    textPrimary: '#2B2A27',
    textSecondary: '#63604F',
    textTertiary: '#8B8574',
    adminAccent: '#4E6E88',
    adminAccentHover: '#405C74',
    adminAccentSoft: '#D9E3EA',
    chatAccent: '#6E9163',
    chatAccentHover: '#5C7C52',
    chatAccentSoft: '#DCEAD5',
    success: '#5C9576',
    successSoft: '#DFEEE5',
    warning: '#C99149',
    warningSoft: '#F5E7D0',
    danger: '#BC6459',
    dangerSoft: '#F3DEDB',
  },
  font: "'Inter', system-ui, -apple-system, sans-serif",
  radius: { sm: '6px', md: '10px', lg: '14px' },
} as const

export const darkTheme = {
  color: {
    bg: '#0f0f0f',
    surface: '#1a1a1a',
    surfaceMuted: '#242424',
    border: '#2e2e2e',
    borderStrong: '#3a3a3a',
    textPrimary: '#f0f0f0',
    textSecondary: '#a0a0a0',
    textTertiary: '#666666',
    adminAccent: '#6E9163',
    adminAccentHover: '#5C7C52',
    adminAccentSoft: '#1e2e1c',
    chatAccent: '#6E9163',
    chatAccentHover: '#5C7C52',
    chatAccentSoft: '#1e2e1c',
    success: '#5C9576',
    successSoft: '#1a2e22',
    warning: '#C99149',
    warningSoft: '#2e2010',
    danger: '#BC6459',
    dangerSoft: '#2e1510',
  },
  font: "'Inter', system-ui, -apple-system, sans-serif",
  radius: { sm: '6px', md: '10px', lg: '14px' },
} as const

export const theme = lightTheme
"""
open('frontend/src/theme.ts', 'w', encoding='utf-8').write(theme_content)
print('Theme updated')

# Update ChatPage to use dark mode
content = open('frontend/src/pages/ChatPage.tsx', 'r', encoding='utf-8', errors='ignore').read()

# Add darkTheme import
old_import = "import { theme } from '../theme'"
new_import = "import { lightTheme, darkTheme } from '../theme'"
if old_import in content:
    content = content.replace(old_import, new_import)
    print('Theme import fixed')
else:
    print('Theme import not found')

# Add dark mode state after other states
old_state = "  const [sidebarOpen, setSidebarOpen] = useState(true)"
new_state = """  const [sidebarOpen, setSidebarOpen] = useState(true)
  const [isDark, setIsDark] = useState(false)
  const color = (isDark ? darkTheme : lightTheme).color
  const radius = (isDark ? darkTheme : lightTheme).radius
  const font = (isDark ? darkTheme : lightTheme).font"""
if old_state in content:
    content = content.replace(old_state, new_state)
    print('Dark mode state added')
else:
    print('Dark mode state not found')

# Remove old const { color, font, radius } = theme line if exists
old_theme_line = "  const { color, font, radius } = theme"
if old_theme_line in content:
    content = content.replace(old_theme_line, '')
    print('Old theme line removed')

# Add dark mode toggle button in topbar
old_topbar = "        {/* Sidebar toggle button */}"
new_topbar = """        {/* Dark mode toggle */}
        <button onClick={() => setIsDark(d => !d)}
          title={isDark ? 'Switch to light mode' : 'Switch to dark mode'}
          style={{ position: 'fixed', top: '12px', right: '16px', zIndex: 100, background: isDark ? '#2a2a2a' : 'white', border: `1px solid ${color.border}`, borderRadius: '6px', padding: '5px 10px', cursor: 'pointer', color: color.textSecondary, display: 'flex', alignItems: 'center', gap: '6px', fontSize: '12px' }}>
          {isDark ? '?? Light' : '?? Dark'}
        </button>
        {/* Sidebar toggle button */}"""
if old_topbar in content:
    content = content.replace(old_topbar, new_topbar)
    print('Dark toggle button added')
else:
    print('Topbar not found')

# Apply dark mode to root div
old_root = '    <div className="chat-page-root">'
new_root = '    <div className="chat-page-root" style={{ background: color.bg, color: color.textPrimary, fontFamily: font }}>'
if old_root in content:
    content = content.replace(old_root, new_root)
    print('Root div updated')

open('frontend/src/pages/ChatPage.tsx', 'w', encoding='utf-8').write(content)
