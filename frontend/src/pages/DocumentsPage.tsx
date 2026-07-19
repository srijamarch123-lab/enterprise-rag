import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Trash2, RefreshCw } from 'lucide-react'
import { useState } from 'react'
import { getDocuments, deleteDocument, reprocessDocument, processAll } from '../services/api'
import StatusBadge from '../components/StatusBadge'
import { Document } from '../types'
import { useTheme } from '../ThemeContext'

export default function DocumentsPage() {
  const qc = useQueryClient()
  const { theme, isDark } = useTheme()
  const { color, font, radius } = theme
  const [statusFilter, setStatusFilter] = useState('')

  const { data: docs = [] as Document[], isLoading } = useQuery<Document[]>({
    queryKey: ['documents', statusFilter],
    queryFn: () => getDocuments(statusFilter ? { status: statusFilter } : undefined),
    refetchInterval: 5000,
  })

  const deleteMut = useMutation({
    mutationFn: (id: number) => deleteDocument(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['documents'] }),
  })

  const reprocessMut = useMutation({
    mutationFn: (id: number) => reprocessDocument(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['documents'] }),
  })

  const processAllMut = useMutation({
    mutationFn: () => processAll(),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['documents'] }),
  })

  const counts = {
    total: docs.length,
    embedded: docs.filter(d => d.status === 'embedded').length,
    failed: docs.filter(d => d.status === 'failed').length,
  }

  const statuses = ['', 'pending', 'extracting', 'extracted', 'chunking', 'chunked', 'embedding', 'embedded', 'failed']

  return (
    <div style={{ padding: '32px', fontFamily: font, background: color.bg, minHeight: '100vh' }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: '24px' }}>
        <div>
          <h1 style={{ fontSize: '20px', fontWeight: '600', color: color.textPrimary, margin: '0 0 4px' }}>Documents</h1>
          <p style={{ fontSize: '13px', color: color.textTertiary, margin: 0 }}>
            {counts.embedded} of {counts.total} embedded
            {counts.failed > 0 && ` · ${counts.failed} failed`}
          </p>
        </div>
        <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
          <select
            value={statusFilter}
            onChange={e => setStatusFilter(e.target.value)}
            style={{
              border: `1px solid ${color.border}`, borderRadius: radius.sm,
              padding: '7px 10px', fontSize: '12px', color: color.textPrimary,
              background: color.surface, outline: 'none',
            }}
          >
            {statuses.map(s => <option key={s} value={s}>{s || 'All statuses'}</option>)}
          </select>
          <button
            onClick={() => processAllMut.mutate()}
            disabled={processAllMut.isPending}
            style={{
              padding: '7px 12px', borderRadius: radius.sm, border: `1px solid ${color.border}`,
              background: color.adminAccent, color: '#fff', cursor: 'pointer', fontSize: '12px',
              fontWeight: '500', display: 'flex', alignItems: 'center', gap: '4px',
              opacity: processAllMut.isPending ? 0.7 : 1,
            }}
          >
            {processAllMut.isPending ? 'Processing...' : 'Process Pending'}
          </button>
          <button
            onClick={() => qc.invalidateQueries({ queryKey: ['documents'] })}
            style={{
              padding: '7px', borderRadius: radius.sm, border: `1px solid ${color.border}`,
              background: color.surface, cursor: 'pointer', display: 'flex', alignItems: 'center',
            }}
          >
            <RefreshCw size={13} color={color.textSecondary} />
          </button>
        </div>
      </div>

      {/* Summary cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '12px', marginBottom: '24px' }}>
        <SummaryCard label="Total documents" value={counts.total} color={color.textPrimary} bg={color.adminAccentSoft} />
        <SummaryCard label="Fully embedded" value={counts.embedded} color={color.success} bg={color.successSoft} />
        <SummaryCard label="Failed" value={counts.failed} color={color.danger} bg={color.dangerSoft} />
      </div>

      {/* Table */}
      {isLoading ? (
        <div style={{ textAlign: 'center', padding: '60px', color: color.textTertiary, fontSize: '13px' }}>Loading…</div>
      ) : docs.length === 0 ? (
        <div style={{
          textAlign: 'center', padding: '60px',
          background: color.surface, border: `1px solid ${color.border}`,
          borderRadius: radius.md, color: color.textTertiary, fontSize: '13px',
        }}>
          No documents yet. Import from Google Drive or upload files directly.
        </div>
      ) : (
        <div style={{ background: color.surface, border: `1px solid ${color.border}`, borderRadius: radius.md, overflow: 'hidden' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '13px' }}>
            <thead>
              <tr style={{ background: isDark ? '#242424' : '#f0faf3', borderBottom: `1px solid ${color.border}` }}>
                {['Name', 'Type', 'Department', 'Status', 'Pages', 'Chunks', 'Uploaded', ''].map(h => (
                  <th key={h} style={{ padding: '10px 14px', textAlign: 'left', fontWeight: '500', color: color.textTertiary, fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {docs.map((doc: Document, i: number) => (
                <tr
                  key={doc.id}
                  style={{ borderBottom: i < docs.length - 1 ? `1px solid ${color.border}` : 'none' }}
                >
                  <td style={{ padding: '10px 14px', color: color.textPrimary, fontWeight: '500', maxWidth: '220px' }}>
                    <div style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={doc.filename}>
                      <a
                        href={`${import.meta.env.VITE_API_URL || ''}/api/documents/${doc.id}/download`}
                        target="_blank"
                        rel="noreferrer"
                        style={{ color: color.textPrimary, textDecoration: 'none', cursor: 'pointer' }}
                        onMouseOver={(e) => (e.currentTarget.style.textDecoration = 'underline')}
                        onMouseOut={(e) => (e.currentTarget.style.textDecoration = 'none')}
                      >
                        {doc.filename}
                      </a>
                    </div>
                    {doc.status === 'failed' && doc.extraction_error && (
                      <div style={{
                        fontSize: '11px',
                        color: color.danger,
                        fontWeight: 'normal',
                        marginTop: '4px',
                        whiteSpace: 'normal',
                        wordBreak: 'break-word',
                        lineHeight: '1.2'
                      }}>
                        {doc.extraction_error}
                      </div>
                    )}
                  </td>
                  <td style={{ padding: '10px 14px', color: color.textSecondary, textTransform: 'uppercase', fontSize: '11px' }}>{doc.file_type}</td>
                  <td style={{ padding: '10px 14px', color: color.textSecondary }}>{doc.department ?? '—'}</td>
                  <td style={{ padding: '10px 14px' }}><StatusBadge status={doc.status} /></td>
                  <td style={{ padding: '10px 14px', color: color.textSecondary }}>{doc.page_count ?? '—'}</td>
                  <td style={{ padding: '10px 14px', color: color.textSecondary }}>{doc.chunk_count ?? '—'}</td>
                  <td style={{ padding: '10px 14px', color: color.textTertiary, fontSize: '11px' }}>
                    {new Date(doc.uploaded_at).toLocaleDateString()}
                  </td>
                  <td style={{ padding: '10px 14px', display: 'flex', gap: '8px', alignItems: 'center' }}>
                    <button
                      onClick={() => reprocessMut.mutate(doc.id)}
                      title="Reprocess Document"
                      disabled={reprocessMut.isPending}
                      style={{ background: 'none', border: 'none', cursor: 'pointer', padding: '4px', borderRadius: radius.sm, display: 'flex', alignItems: 'center' }}
                    >
                      <RefreshCw size={13} color={reprocessMut.isPending ? color.borderStrong : color.textSecondary} />
                    </button>
                    <button
                      onClick={() => deleteMut.mutate(doc.id)}
                      title="Delete Document"
                      style={{ background: 'none', border: 'none', cursor: 'pointer', padding: '4px', borderRadius: radius.sm, display: 'flex', alignItems: 'center' }}
                    >
                      <Trash2 size={13} color={color.danger} />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

function SummaryCard({ label, value, color, bg }: { label: string; value: number; color: string; bg: string }) {
  return (
    <div style={{ background: bg, borderRadius: '10px', padding: '14px 18px' }}>
      <div style={{ fontSize: '24px', fontWeight: '600', color }}>{value}</div>
      <div style={{ fontSize: '12px', color, opacity: 0.8, marginTop: '2px' }}>{label}</div>
    </div>
  )
}