import { Outlet, NavLink, useNavigate } from 'react-router-dom'
import { FileText, HardDrive, Users, LogOut, Cpu, MessageSquare, ClipboardList, UserCheck } from 'lucide-react'
import { logout } from '../services/api'

const nav = [
  { to: '/chat', icon: MessageSquare, label: 'Chat' },
  { to: '/documents', icon: FileText, label: 'Documents' },
  { to: '/processing', icon: Cpu, label: 'Processing' },
  { to: '/drive', icon: HardDrive, label: 'Google Drive' },
  { to: '/users', icon: Users, label: 'Users' },
  { to: '/user-log', icon: ClipboardList, label: 'User Log' },
  { to: '/add-admin', icon: UserCheck, label: 'Add Admin' },
]

export default function AdminLayout() {
  const navigate = useNavigate()

  const handleLogout = async () => {
    try { await logout() } finally { navigate('/login') }
  }

  return (
    <div style={{ display: 'flex', height: '100vh', overflow: 'hidden', fontFamily: 'Inter, system-ui, sans-serif' }}>
      <aside style={{ width: '220px', background: '#e8f5ee', borderRight: '1px solid #c8e6d0', display: 'flex', flexDirection: 'column', flexShrink: 0 }}>
        <div style={{ padding: '20px 16px 14px', borderBottom: '1px solid #c8e6d0' }}>
          <div style={{ fontSize: '13px', fontWeight: 600, color: '#1a5c2e', letterSpacing: '-0.01em' }}>Enterprise RAG</div>
          <div style={{ fontSize: '11px', color: '#5a8a6a', marginTop: '2px' }}>Admin Panel</div>
        </div>

        <nav style={{ flex: 1, padding: '12px 8px', display: 'flex', flexDirection: 'column', gap: '2px' }}>
          {nav.map(({ to, icon: Icon, label }) => (
            <NavLink
              key={to}
              to={to}
              style={({ isActive }) => ({
                display: 'flex', alignItems: 'center', gap: '8px',
                padding: '8px 10px', borderRadius: '8px',
                fontSize: '13px', fontWeight: 500, textDecoration: 'none',
                color: isActive ? '#1a5c2e' : '#4a7a5a',
                background: isActive ? '#c0dd97' : 'transparent',
                transition: 'all 0.1s',
              })}
            >
              <Icon size={15} />
              {label}
            </NavLink>
          ))}
        </nav>

        <button
          onClick={handleLogout}
          style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '14px 18px', borderTop: '1px solid #c8e6d0', background: 'transparent', border: 'none', cursor: 'pointer', fontSize: '13px', color: '#5a8a6a', width: '100%', textAlign: 'left' }}
        >
          <LogOut size={14} />
          Log out
        </button>
      </aside>

      <main style={{ flex: 1, overflow: 'auto', background: '#f7faf8' }}>
        <Outlet />
      </main>
    </div>
  )
}
