import { useState } from 'react'
import { UserCheck } from 'lucide-react'
import api from '../services/api'

export default function AddAdminPage() {
  const [email, setEmail] = useState('')
  const [loading, setLoading] = useState(false)
  const [success, setSuccess] = useState('')
  const [error, setError] = useState('')

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!email.trim()) return
    setLoading(true)
    setSuccess('')
    setError('')
    try {
      const res = await api.post('/admin/users/promote-to-admin', { email: email.trim() })
      setSuccess(res.data.message)
      setEmail('')
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Something went wrong')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{ padding: '40px', maxWidth: '480px' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '8px' }}>
        <UserCheck size={20} color="#1a5c2e" />
        <h1 style={{ fontSize: '18px', fontWeight: 600, color: '#1a5c2e', margin: 0 }}>Add Admin</h1>
      </div>
      <p style={{ fontSize: '13px', color: '#7a9a7a', marginBottom: '28px', lineHeight: 1.6 }}>
        Enter an employee's email to grant them admin access.
        Their current session will be invalidated and they will need to log in again.
      </p>

      <form onSubmit={handleSubmit}>
        <label style={{ fontSize: '12px', fontWeight: 500, color: '#4a7a5a', display: 'block', marginBottom: '6px' }}>
          Employee email
        </label>
        <input
          type="email"
          value={email}
          onChange={e => { setEmail(e.target.value); setSuccess(''); setError('') }}
          placeholder="employee@company.com"
          required
          style={{ width: '100%', padding: '10px 14px', fontSize: '14px', border: '1px solid #c8e6d0', borderRadius: '10px', outline: 'none', background: 'white', boxSizing: 'border-box', marginBottom: '16px' }}
        />

        {success && (
          <div style={{ padding: '12px 16px', background: '#e8f5ee', border: '1px solid #c8e6d0', borderRadius: '8px', fontSize: '13px', color: '#1a5c2e', marginBottom: '16px' }}>
            ? {success}
          </div>
        )}
        {error && (
          <div style={{ padding: '12px 16px', background: '#fee', border: '1px solid #fcc', borderRadius: '8px', fontSize: '13px', color: '#c00', marginBottom: '16px' }}>
            {error}
          </div>
        )}

        <button
          type="submit"
          disabled={loading || !email.trim()}
          style={{ padding: '10px 24px', background: loading || !email.trim() ? '#c8e6d0' : '#1a5c2e', color: 'white', border: 'none', borderRadius: '10px', fontSize: '14px', fontWeight: 500, cursor: loading || !email.trim() ? 'not-allowed' : 'pointer', transition: 'background 0.15s' }}
        >
          {loading ? 'Promoting...' : 'Make admin'}
        </button>
      </form>
    </div>
  )
}
