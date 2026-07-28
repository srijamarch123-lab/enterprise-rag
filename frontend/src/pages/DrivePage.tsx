import { useState, useEffect } from 'react'
import { HardDrive, RefreshCw, Trash2, Plus, X } from 'lucide-react'
import api from '../services/api'

interface DriveConnection {
  id: number
  name: string
  email: string
  folder_id: string | null
  created_at: string
  last_synced: string | null
}

export default function DrivePage() {
  const [connections, setConnections] = useState<DriveConnection[]>([])
  const [loading, setLoading] = useState(true)
  const [showAdd, setShowAdd] = useState(false)
  const [jsonFile, setJsonFile] = useState<string>('')
  const [name, setName] = useState('Google Drive')
  const [folderId, setFolderId] = useState('')
  const [adding, setAdding] = useState(false)
  const [syncing, setSyncing] = useState<number | null>(null)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')

  const fetchConnections = async () => {
    setLoading(true)
    try {
      const res = await api.get('/drive-connections')
      setConnections(res.data)
    } catch {
      setError('Failed to load drive connections')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { fetchConnections() }, [])

  const handleAdd = async () => {
    if (!jsonFile) return
    setAdding(true)
    setError('')
    try {
      const parsed = JSON.parse(jsonFile)
      await api.post('/drive-connections', {
        name: name || 'Google Drive',
        credentials_json: parsed,
        folder_id: folderId || null
      })
      setSuccess('Drive connected successfully!')
      setShowAdd(false)
      setJsonFile('')
      setName('Google Drive')
      setFolderId('')
      fetchConnections()
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Failed to connect drive')
    } finally {
      setAdding(false)
    }
  }

  const handleSync = async (id: number) => {
    setSyncing(id)
    setError('')
    try {
      await api.post(`/drive-connections/${id}/sync`)
      setSuccess('Sync started! Documents will be processed in the background.')
      fetchConnections()
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Sync failed')
    } finally {
      setSyncing(null)
    }
  }

  const handleDelete = async (id: number) => {
    if (!window.confirm('Remove this drive connection?')) return
    try {
      await api.delete(`/drive-connections/${id}`)
      setConnections(prev => prev.filter(c => c.id !== id))
      setSuccess('Drive connection removed')
    } catch {
      setError('Failed to remove connection')
    }
  }

  const fmt = (ts: string | null) => ts ? new Date(ts).toLocaleString() : 'Never'

  return (
    <div style={{ padding: '32px', fontFamily: 'Inter, system-ui, sans-serif', maxWidth: '900px' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '24px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <HardDrive size={20} color="#1a5c2e" />
          <h1 style={{ fontSize: '18px', fontWeight: 600, color: '#1a5c2e', margin: 0 }}>Google Drive Connections</h1>
        </div>
        <button onClick={() => setShowAdd(true)}
          style={{ display: 'flex', alignItems: 'center', gap: '6px', padding: '8px 16px', background: '#1a5c2e', color: 'white', border: 'none', borderRadius: '8px', fontSize: '13px', fontWeight: 500, cursor: 'pointer' }}>
          <Plus size={14} /> Connect Drive
        </button>
      </div>

      {error && <div style={{ padding: '10px 14px', background: '#fee', border: '1px solid #fcc', borderRadius: '8px', color: '#c00', fontSize: '13px', marginBottom: '16px' }}>{error}</div>}
      {success && <div style={{ padding: '10px 14px', background: '#e8f5ee', border: '1px solid #c8e6d0', borderRadius: '8px', color: '#1a5c2e', fontSize: '13px', marginBottom: '16px' }}>{success}</div>}

      {loading ? (
        <div style={{ color: '#7a9a7a', fontSize: '13px' }}>Loading...</div>
      ) : connections.length === 0 ? (
        <div style={{ textAlign: 'center', padding: '60px 20px', color: '#7a9a7a' }}>
          <HardDrive size={40} style={{ marginBottom: '12px', opacity: 0.3 }} />
          <div style={{ fontSize: '15px', fontWeight: 500, marginBottom: '6px' }}>No drives connected</div>
          <div style={{ fontSize: '13px' }}>Connect a Google Drive to start importing documents</div>
        </div>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: '16px' }}>
          {connections.map(c => (
            <div key={c.id} style={{ background: 'white', border: '1px solid #e0ece6', borderRadius: '12px', padding: '20px' }}>
              <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: '12px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                  <div style={{ width: '36px', height: '36px', background: '#e8f5ee', borderRadius: '8px', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                    <HardDrive size={18} color="#1a5c2e" />
                  </div>
                  <div>
                    <div style={{ fontSize: '14px', fontWeight: 600, color: '#1a1a1a' }}>{c.name}</div>
                    <div style={{ fontSize: '11px', color: '#7a9a7a', marginTop: '2px' }}>{c.email}</div>
                  </div>
                </div>
                <button onClick={() => handleDelete(c.id)}
                  style={{ border: 'none', background: 'transparent', cursor: 'pointer', color: '#ccc', padding: '2px' }}
                  onMouseEnter={e => e.currentTarget.style.color = '#c00'}
                  onMouseLeave={e => e.currentTarget.style.color = '#ccc'}>
                  <X size={15} />
                </button>
              </div>

              {c.folder_id && <div style={{ fontSize: '11px', color: '#7a9a7a', marginBottom: '8px' }}>Folder: {c.folder_id}</div>}
              <div style={{ fontSize: '11px', color: '#7a9a7a', marginBottom: '14px' }}>Last synced: {fmt(c.last_synced)}</div>

              <button onClick={() => handleSync(c.id)} disabled={syncing === c.id}
                style={{ width: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '6px', padding: '8px', background: syncing === c.id ? '#e8f5ee' : '#f0faf4', border: '1px solid #c8e6d0', borderRadius: '7px', fontSize: '13px', color: '#1a5c2e', cursor: syncing === c.id ? 'not-allowed' : 'pointer', fontWeight: 500 }}>
                <RefreshCw size={13} style={{ animation: syncing === c.id ? 'spin 1s linear infinite' : 'none' }} />
                {syncing === c.id ? 'Syncing...' : 'Sync Now'}
              </button>
            </div>
          ))}
        </div>
      )}

      {/* Add Drive Modal */}
      {showAdd && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.4)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 100 }}>
          <div style={{ background: 'white', borderRadius: '16px', padding: '28px', width: '500px', maxWidth: '90vw' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
              <div style={{ fontSize: '16px', fontWeight: 600, color: '#1a5c2e' }}>Connect Google Drive</div>
              <button onClick={() => setShowAdd(false)} style={{ border: 'none', background: 'transparent', cursor: 'pointer', color: '#7a9a7a' }}><X size={18} /></button>
            </div>

            <label style={{ fontSize: '12px', fontWeight: 500, color: '#4a7a5a', display: 'block', marginBottom: '4px' }}>Connection Name</label>
            <input value={name} onChange={e => setName(e.target.value)} placeholder="e.g. HR Documents Drive"
              style={{ width: '100%', padding: '8px 12px', border: '1px solid #c8e6d0', borderRadius: '8px', fontSize: '13px', marginBottom: '14px', boxSizing: 'border-box', outline: 'none' }} />

            <label style={{ fontSize: '12px', fontWeight: 500, color: '#4a7a5a', display: 'block', marginBottom: '4px' }}>Service Account JSON</label>
            <input type="file" accept=".json" onChange={e => { const f = e.target.files?.[0]; if (!f) return; const r = new FileReader(); r.onload = ev => setJsonFile(ev.target?.result as string); r.readAsText(f) }}
              style={{ width: '100%', padding: '8px', border: '1px solid #c8e6d0', borderRadius: '8px', fontSize: '13px', marginBottom: '4px', boxSizing: 'border-box', cursor: 'pointer' }} />
            {jsonFile && <div style={{ fontSize: '11px', color: '#1a5c2e', marginBottom: '14px' }}>JSON loaded successfully</div>}

            <label style={{ fontSize: '12px', fontWeight: 500, color: '#4a7a5a', display: 'block', marginBottom: '4px' }}>Folder ID (optional)</label>
            <input value={folderId} onChange={e => setFolderId(e.target.value)} placeholder="Leave empty to import all files"
              style={{ width: '100%', padding: '8px 12px', border: '1px solid #c8e6d0', borderRadius: '8px', fontSize: '13px', marginBottom: '20px', boxSizing: 'border-box', outline: 'none' }} />

            <div style={{ display: 'flex', gap: '10px', justifyContent: 'flex-end' }}>
              <button onClick={() => setShowAdd(false)} style={{ padding: '8px 16px', border: '1px solid #c8e6d0', borderRadius: '8px', background: 'white', fontSize: '13px', cursor: 'pointer', color: '#4a7a5a' }}>Cancel</button>
              <button onClick={handleAdd} disabled={!jsonFile || adding}
                style={{ padding: '8px 20px', border: 'none', borderRadius: '8px', background: !jsonFile || adding ? '#c8e6d0' : '#1a5c2e', color: 'white', fontSize: '13px', fontWeight: 500, cursor: !jsonFile || adding ? 'not-allowed' : 'pointer' }}>
                {adding ? 'Connecting...' : 'Connect'}
              </button>
            </div>
          </div>
        </div>
      )}

      <style>{`@keyframes spin { from { transform: rotate(0deg) } to { transform: rotate(360deg) } }`}</style>
    </div>
  )
}
