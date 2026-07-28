import { useState, useEffect } from 'react'
import { ClipboardList } from 'lucide-react'
import api from '../services/api'
import { useTheme } from '../ThemeContext'

interface LogEntry {
  id: number
  user_id: number | null
  action: string
  timestamp: string
  ip_address: string | null
  details: any
}

interface UserMap {
  [id: number]: string
}

export default function UserLogPage() {
  const { theme, isDark } = useTheme()
  const { color, font, radius } = theme
  const [logs, setLogs] = useState<LogEntry[]>([])
  const [userMap, setUserMap] = useState<UserMap>({})
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [page, setPage] = useState(0)
  const limit = 20

  useEffect(() => {
    api.get('/admin/users').then(res => {
      const map: UserMap = {}
      res.data.forEach((u: any) => { map[u.id] = u.email })
      setUserMap(map)
    }).catch(() => {})
  }, [])

  useEffect(() => { fetchLogs(page) }, [page])

  const fetchLogs = async (p: number) => {
    setLoading(true)
    setError('')
    try {
      const res = await api.get(`/admin/audit-logs?skip=${p * limit}&limit=${limit}`)
      setLogs(res.data)
    } catch {
      setError('Failed to load audit logs')
    } finally {
      setLoading(false)
    }
  }

  const fmt = (ts: string) => {
    if (!ts) return "";
    const dateStr = ts.endsWith('Z') || ts.includes('+') ? ts : `${ts}Z`;
    return new Date(dateStr).toLocaleString('en-IN', { timeZone: 'Asia/Kolkata' });
  }

  const hasPrev = page > 0
  const hasNext = logs.length === limit

  return (
    <div style={{ padding: '32px', fontFamily: font, background: color.bg, minHeight: '100vh' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '24px' }}>
        <ClipboardList size={20} color={color.adminAccent} />
        <h1 style={{ fontSize: '18px', fontWeight: 600, color: color.textPrimary, margin: 0 }}>User Log</h1>
      </div>

      {error && (
        <div style={{ padding: '12px 16px', background: color.dangerSoft, color: color.danger, borderRadius: radius.sm, marginBottom: '16px', fontSize: '13px' }}>
          {error}
        </div>
      )}

      {loading ? (
        <div style={{ color: color.textTertiary, fontSize: '13px' }}>Loading logs...</div>
      ) : logs.length === 0 ? (
        <div style={{ color: color.textTertiary, fontSize: '13px' }}>No logs found.</div>
      ) : (
        <>
          <div style={{ background: color.surface, border: `1px solid ${color.border}`, borderRadius: radius.md, overflow: 'hidden' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '12px' }}>
              <thead>
                <tr style={{ background: isDark ? '#242424' : '#f7faf8', borderBottom: `1px solid ${color.border}` }}>
                  {['Time', 'User', 'Action', 'IP Address', 'Details'].map(h => (
                    <th key={h} style={{ padding: '10px 14px', textAlign: 'left', fontWeight: 500, color: color.textTertiary, whiteSpace: 'nowrap' }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {logs.map((l, i) => {
                  const userEmail = l.user_id ? (userMap[l.user_id] || `User #${l.user_id}`) : ''
                  return (
                    <tr key={l.id} style={{ borderBottom: i < logs.length - 1 ? `1px solid ${color.border}` : 'none' }}>
                      <td style={{ padding: '10px 14px', color: color.textPrimary, whiteSpace: 'nowrap' }}>{fmt(l.timestamp)}</td>
                      <td style={{ padding: '10px 14px', color: color.textSecondary, fontSize: '11px' }}>{userEmail}</td>
                      <td style={{ padding: '10px 14px' }}>
                        <span style={{ padding: '3px 8px', borderRadius: '20px', fontSize: '11px', fontWeight: 500, background: color.adminAccentSoft, color: color.adminAccent }}>
                          {l.action}
                        </span>
                      </td>
                      <td style={{ padding: '10px 14px', color: color.textTertiary, fontFamily: 'monospace' }}>{l.ip_address || ''}</td>
                      <td style={{ padding: '10px 14px', color: color.textSecondary, maxWidth: '260px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                        {l.details ? JSON.stringify(l.details) : ''}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>

          <div style={{ display: 'flex', gap: '10px', marginTop: '16px', alignItems: 'center' }}>
            <button
              onClick={() => setPage(p => p - 1)}
              disabled={!hasPrev}
              style={{ padding: '7px 16px', border: `1px solid ${color.border}`, borderRadius: radius.sm, background: color.surface, fontSize: '12px', cursor: hasPrev ? 'pointer' : 'not-allowed', color: hasPrev ? color.adminAccent : color.textTertiary }}
            >
              Previous
            </button>
            <span style={{ fontSize: '12px', color: color.textTertiary }}>
              Page {page + 1} &nbsp;&nbsp; {logs.length} entries
            </span>
            <button
              onClick={() => setPage(p => p + 1)}
              disabled={!hasNext}
              style={{ padding: '7px 16px', border: `1px solid ${color.border}`, borderRadius: radius.sm, background: color.surface, fontSize: '12px', cursor: hasNext ? 'pointer' : 'not-allowed', color: hasNext ? color.adminAccent : color.textTertiary }}
            >
              Next
            </button>
          </div>
        </>
      )}
    </div>
  )
}
