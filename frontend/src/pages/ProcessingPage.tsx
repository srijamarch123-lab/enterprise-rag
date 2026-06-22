import { CheckCircle, XCircle, Loader, Clock, RefreshCw } from 'lucide-react'
import { usePipeline, DocProgress } from '../hooks/usePipeline'

const statusIcon = (status: DocProgress['status']) => {
  if (status === 'done') return <CheckCircle size={15} color="#27500A" />
  if (status === 'failed') return <XCircle size={15} color="#A32D2D" />
  if (status === 'skipped') return <XCircle size={15} color="#5F5E5A" />
  if (status === 'waiting') return <Clock size={15} color="#888780" />
  return <Loader size={15} color="#185FA5" style={{ animation: 'spin 1s linear infinite' }} />
}

const statusLabel = (status: DocProgress['status']) => {
  if (status === 'waiting') return 'Waiting'
  if (status === 'extracting') return 'Extracting text…'
  if (status === 'chunking') return 'Chunking…'
  if (status === 'embedding') return 'Embedding…'
  if (status === 'done') return 'Done'
  if (status === 'skipped') return 'Skipped'
  if (status === 'failed') return 'Failed'
  return status
}

const stageBar = (status: DocProgress['status']) => {
  const stages = ['extracting', 'chunking', 'embedding', 'done']
  const idx = stages.indexOf(status === 'done' ? 'done' : status)
  return (
    <div style={{ display: 'flex', gap: '4px', alignItems: 'center' }}>
      {['Extract', 'Chunk', 'Embed'].map((s, i) => {
        const active = idx === i
        const done = idx > i || status === 'done'
        return (
          <div key={s} style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
            <div style={{
              padding: '2px 7px',
              borderRadius: '4px',
              fontSize: '10px',
              fontWeight: '500',
              background: done ? '#c0dd97' : active ? '#e6f1fb' : '#f1efe8',
              color: done ? '#27500A' : active ? '#185FA5' : '#888780',
            }}>{s}</div>
            {i < 2 && <div style={{ width: '12px', height: '1px', background: done ? '#c0dd97' : '#d3d1c7' }} />}
          </div>
        )
      })}
    </div>
  )
}

export default function ProcessingPage({ externalProgress, externalRunning, externalSummary, externalRetry }: {
  externalProgress?: DocProgress[]
  externalRunning?: boolean
  externalSummary?: { done: number; skipped: number; failed: number } | null
  externalRetry?: (docs: DocProgress[]) => void
}) {
  const internal = usePipeline()
  const progress = externalProgress ?? internal.progress
  const running = externalRunning ?? internal.running
  const summary = externalSummary ?? internal.summary
  const retry = externalRetry ?? internal.retry

  const failed = progress.filter(d => d.status === 'failed' || d.status === 'skipped')
  const doneCount = progress.filter(d => d.status === 'done').length

  return (
    <div style={{ padding: '32px', maxWidth: '800px' }}>
      <style>{`@keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }`}</style>

      <div style={{ marginBottom: '24px' }}>
        <h1 style={{ fontSize: '20px', fontWeight: '600', color: '#1a3d2a', margin: '0 0 4px' }}>
          Processing pipeline
        </h1>
        <p style={{ fontSize: '13px', color: '#5a8a6a', margin: 0 }}>
          Documents are automatically extracted, chunked, and embedded.
        </p>
      </div>

      {progress.length === 0 && !running && (
        <div style={{
          background: '#fff',
          border: '1px solid #c8e6d0',
          borderRadius: '12px',
          padding: '48px',
          textAlign: 'center',
          color: '#5a8a6a',
          fontSize: '13px',
        }}>
          No processing activity yet. Import files from Google Drive or upload directly.
        </div>
      )}

      {progress.length > 0 && (
        <>
          {/* Summary bar */}
          <div style={{
            background: '#fff',
            border: '1px solid #c8e6d0',
            borderRadius: '10px',
            padding: '14px 18px',
            marginBottom: '16px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
          }}>
            <div style={{ display: 'flex', gap: '20px' }}>
              <Stat label="Total" value={progress.length} color="#1a3d2a" />
              <Stat label="Done" value={doneCount} color="#27500A" />
              <Stat label="Skipped" value={progress.filter(d => d.status === 'skipped').length} color="#5F5E5A" />
              <Stat label="Failed" value={progress.filter(d => d.status === 'failed').length} color="#A32D2D" />
            </div>
            {running && (
              <div style={{ fontSize: '12px', color: '#185FA5', display: 'flex', alignItems: 'center', gap: '6px' }}>
                <Loader size={13} style={{ animation: 'spin 1s linear infinite' }} />
                Processing {doneCount}/{progress.length}
              </div>
            )}
            {summary && !running && failed.length > 0 && (
              <button
                onClick={() => retry(failed)}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                  padding: '6px 12px',
                  borderRadius: '7px',
                  border: '1px solid #c8e6d0',
                  background: '#e8f5ee',
                  color: '#1a5c2e',
                  fontSize: '12px',
                  fontWeight: '500',
                  cursor: 'pointer',
                }}
              >
                <RefreshCw size={12} />
                Retry {failed.length} failed
              </button>
            )}
          </div>

          {/* Per-document list */}
          <div style={{
            background: '#fff',
            border: '1px solid #c8e6d0',
            borderRadius: '12px',
            overflow: 'hidden',
          }}>
            {progress.map((doc, i) => (
              <div
                key={doc.id}
                style={{
                  padding: '12px 18px',
                  borderBottom: i < progress.length - 1 ? '1px solid #edf5ee' : 'none',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '12px',
                  background: doc.status === 'done' ? '#fafff8' : '#fff',
                }}
              >
                <div style={{ flexShrink: 0 }}>{statusIcon(doc.status)}</div>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{
                    fontSize: '13px',
                    fontWeight: '500',
                    color: '#1a3d2a',
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    whiteSpace: 'nowrap',
                    marginBottom: '4px',
                  }}>
                    {doc.filename}
                  </div>
                  {doc.status === 'failed' || doc.status === 'skipped' ? (
                    <div style={{ fontSize: '11px', color: doc.status === 'failed' ? '#A32D2D' : '#5F5E5A' }}>
                      {doc.error}
                    </div>
                  ) : (
                    stageBar(doc.status)
                  )}
                </div>
                <div style={{ fontSize: '11px', color: '#5a8a6a', flexShrink: 0 }}>
                  {statusLabel(doc.status)}
                </div>
              </div>
            ))}
          </div>

          {/* Final summary */}
          {summary && !running && (
            <div style={{
              marginTop: '16px',
              padding: '12px 18px',
              borderRadius: '10px',
              background: summary.failed > 0 || summary.skipped > 0 ? '#fef9ec' : '#e8f5ee',
              border: `1px solid ${summary.failed > 0 || summary.skipped > 0 ? '#f5c04a' : '#c0dd97'}`,
              fontSize: '13px',
              color: '#1a3d2a',
            }}>
              ✓ {summary.done} processed successfully
              {summary.skipped > 0 && ` · ${summary.skipped} skipped (no text)`}
              {summary.failed > 0 && ` · ${summary.failed} failed`}
            </div>
          )}
        </>
      )}
    </div>
  )
}

function Stat({ label, value, color }: { label: string; value: number; color: string }) {
  return (
    <div>
      <div style={{ fontSize: '18px', fontWeight: '600', color }}>{value}</div>
      <div style={{ fontSize: '11px', color: '#5a8a6a' }}>{label}</div>
    </div>
  )
}