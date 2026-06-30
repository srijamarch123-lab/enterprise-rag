import { useState, useEffect } from 'react'
import { ClipboardList, LogIn } from 'lucide-react'
import api from '../services/api'

interface LogEntry {
  id: number
  user_id: number | null
  user_email: string | null
  user_role: string | null
  action: string
  timestamp: string
  ip_address: string | null
  details: any
  resource_type: string | null
  resource_id: number | null
}

const ACTION_COLORS: Record<string, { bg: string; color: string }> = {
  login:         { bg: '#e8f5ee', color: '#1a5c2e' },
  logout:        { bg: '#f0f0f0', color: '#555' },
  login_failed:  { bg: '#fee', color: '#c00' },
  role_change:   { bg: '#fff3cd', color: '#856404' },
  disable_user:  { bg: '#fee', color: '#c00' },
  enable_user:   { bg: '#e8f5ee', color: '#1a5c2e' },
  force_logout:  { bg: '#fde8e8', color: '#a00' },
  password_reset:{ bg: '#e8f0fe', color: '#1a56c2' },
}

export default function UserLogPage() {
  const [logs, setLogs] = useState<LogEntry[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [skip, setSkip] = useState(0)
  const [view, setView] = useState<'all' | 'login' | 'failed'>('all')
  const limit = 50

  const fetchLogs = async (s: number, v: 'all' | 'login' | 'failed') => {
    setLoading(true)
    setError('')
    try {
      const endpoint = v === 'login' ? `/admin/login-activity?skip=${s}&limit=${limit}`
        : v === 'failed' ? `/admin/audit-logs?action=login_failed&skip=${s}&limit=${limit}`
        : `/admin/audit-logs?skip=${s}&limit=${limit}`
      const res = await api.get(endpoint)
      setLogs(res.data)
    } catch {
      setError('Failed to load audit logs')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { fetchLogs(skip, view) }, [skip, view])

  const fmt = (ts: string) => new Date(ts).toLocaleString()

  return (
    <div style={{ padding: '32px', fontFamily: 'Inter, system-ui, sans-serif' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '24px' }}>
        {view === 'login' ? <LogIn size={20} color="#1a5c2e" /> : <ClipboardList size={20} color="#1a5c2e" />}
        <h1 style={{ fontSize: '18px', fontWeight: 600, color: '#1a5c2e', margin: 0 }}>
          {view === 'login' ? 'Login Activity' : view === 'failed' ? 'Failed Logins' : 'User Log'}
        </h1>
      </div>

      <div style={{ display: 'flex', gap: '8px', marginBottom: '20px' }}>
        <button
          onClick={() => { setView('login'); setSkip(0) }}
          style={{
            padding: '8px 14px',
            borderRadius: '8px',
            border: view === 'login' ? '1px solid #1a5c2e' : '1px solid #e0ece6',
            background: view === 'login' ? '#1a5c2e' : 'white',
            color: view === 'login' ? 'white' : '#1a5c2e',
            fontSize: '12px',
            fontWeight: 500,
            cursor: 'pointer',
          }}
        >
          Logins
        </button>
        <button
          onClick={() => { setView('failed'); setSkip(0) }}
          style={{
            padding: '8px 14px',
            borderRadius: '8px',
            border: view === 'failed' ? '1px solid #c00' : '1px solid #e0ece6',
            background: view === 'failed' ? '#c00' : 'white',
            color: view === 'failed' ? 'white' : '#c00',
            fontSize: '12px',
            fontWeight: 500,
            cursor: 'pointer',
          }}
        >
          Failed
        </button>
        <button
          onClick={() => { setView('all'); setSkip(0) }}
          style={{
            padding: '8px 14px',
            borderRadius: '8px',
            border: view === 'all' ? '1px solid #1a5c2e' : '1px solid #e0ece6',
            background: view === 'all' ? '#1a5c2e' : 'white',
            color: view === 'all' ? 'white' : '#1a5c2e',
            fontSize: '12px',
            fontWeight: 500,
            cursor: 'pointer',
          }}
        >
          All Logs
        </button>
      </div>

      {error && (
        <div style={{ padding: '12px 16px', background: '#fee', color: '#c00', borderRadius: '8px', marginBottom: '16px', fontSize: '13px' }}>
          {error}
        </div>
      )}

      {loading ? (
        <div style={{ color: '#7a9a7a', fontSize: '13px' }}>Loading logs...</div>
      ) : logs.length === 0 ? (
        <div style={{ color: '#7a9a7a', fontSize: '13px' }}>No logs found.</div>
      ) : (
        <>
          <div style={{ background: 'white', border: '1px solid #e0ece6', borderRadius: '12px', overflow: 'hidden' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '12px' }}>
              <thead>
                <tr style={{ background: '#f7faf8', borderBottom: '1px solid #e0ece6' }}>
                  {['Time', 'User', 'Role', 'Action', 'IP Address', ...(view === 'all' ? ['Details'] as const : [])].map(h => (
                    <th key={h} style={{ padding: '10px 14px', textAlign: 'left', fontWeight: 500, color: '#4a7a5a', whiteSpace: 'nowrap' }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {logs.map((l, i) => {
                  const colors = ACTION_COLORS[l.action] || { bg: '#f0f0f0', color: '#555' }
                  const isLoginView = view === 'login'
                  return (
                    <tr key={l.id} style={{ borderBottom: i < logs.length - 1 ? '1px solid #f0f5f2' : 'none' }}>
                      <td style={{ padding: '10px 14px', color: '#4a5a4a', whiteSpace: 'nowrap' }}>{fmt(l.timestamp)}</td>
                      <td style={{ padding: '10px 14px', color: '#1a5c2e', fontWeight: 500 }}>{l.user_email ?? (l.user_id ? `User ${l.user_id}` : '-')}</td>
                      <td style={{ padding: '10px 14px' }}>
                        <span style={{ padding: '2px 8px', borderRadius: '4px', fontSize: '11px', fontWeight: 500, background: '#f0f5f2', color: '#4a7a5a' }}>
                          {l.user_role ?? '-'}
                        </span>
                      </td>
                      <td style={{ padding: '10px 14px' }}>
                        <span style={{ padding: '3px 8px', borderRadius: '20px', fontSize: '11px', fontWeight: 500, background: colors.bg, color: colors.color }}>
                          {l.action}
                        </span>
                      </td>
                      <td style={{ padding: '10px 14px', color: '#7a9a7a', fontFamily: 'monospace' }}>{l.ip_address ?? '-'}</td>
                      {!isLoginView && (
                        <td style={{ padding: '10px 14px', color: '#4a5a4a', maxWidth: '200px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                          {l.details ? JSON.stringify(l.details) : '-'}
                        </td>
                      )}
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>

          <div style={{ display: 'flex', gap: '10px', marginTop: '16px', alignItems: 'center' }}>
            <button
              onClick={() => setSkip(s => Math.max(0, s - limit))}
              disabled={skip === 0}
              style={{ padding: '7px 16px', border: '1px solid #c8e6d0', borderRadius: '8px', background: 'white', fontSize: '12px', cursor: skip === 0 ? 'not-allowed' : 'pointer', color: skip === 0 ? '#aaa' : '#1a5c2e' }}
            >
              Previous
            </button>
            <span style={{ fontSize: '12px', color: '#7a9a7a' }}>Showing {skip + 1}-{skip + logs.length}</span>
            <button
              onClick={() => setSkip(s => s + limit)}
              disabled={logs.length < limit}
              style={{ padding: '7px 16px', border: '1px solid #c8e6d0', borderRadius: '8px', background: 'white', fontSize: '12px', cursor: logs.length < limit ? 'not-allowed' : 'pointer', color: logs.length < limit ? '#aaa' : '#1a5c2e' }}
            >
              Next
            </button>
          </div>
        </>
      )}
    </div>
  )
}