import { useState, useCallback } from 'react'
import api from '../services/api'

export type DocProgress = {
  id: number
  filename: string
  status: 'waiting' | 'extracting' | 'chunking' | 'embedding' | 'done' | 'skipped' | 'failed'
  error?: string
}

export function usePipeline() {
  const [progress, setProgress] = useState<DocProgress[]>([])
  const [running, setRunning] = useState(false)
  const [summary, setSummary] = useState<{ done: number; skipped: number; failed: number } | null>(null)

  const update = (id: number, patch: Partial<DocProgress>) =>
    setProgress(prev => prev.map(d => d.id === id ? { ...d, ...patch } : d))

  const runPipeline = useCallback(async (docIds: { id: number; filename: string }[]) => {
    setRunning(true)
    setSummary(null)
    const initial: DocProgress[] = docIds.map(d => ({ ...d, status: 'waiting' }))
    setProgress(initial)

    // Trigger backend processing for all pending files in the database
    try {
      await api.post('/process-all')
    } catch (e) {
      console.error('Failed to trigger backend process-all:', e)
    }

    let done = 0, skipped = 0, failed = 0

    const promises = docIds.map(async (doc) => {
      try {
        await pollUntilProcessed(doc.id, (status, error) => {
          update(doc.id, { status, error })
        })
        done++
      } catch (e: any) {
        const errorMsg = e.message ?? 'Processing failed'
        if (errorMsg.toLowerCase().includes('no text')) {
          update(doc.id, { status: 'skipped', error: errorMsg })
          skipped++
        } else {
          update(doc.id, { status: 'failed', error: errorMsg })
          failed++
        }
      }
    })

    await Promise.all(promises)

    setSummary({ done, skipped, failed })
    setRunning(false)
  }, [])

  const retry = useCallback((failedDocs: DocProgress[]) => {
    const toRetry = failedDocs
      .filter(d => d.status === 'failed' || d.status === 'skipped')
      .map(d => ({ id: d.id, filename: d.filename }))
    if (toRetry.length > 0) runPipeline(toRetry)
  }, [runPipeline])

  return { progress, setProgress, running, summary, runPipeline, retry }
}

async function pollUntilProcessed(
  docId: number,
  onStatusUpdate: (status: DocProgress['status'], error?: string) => void
): Promise<void> {
  const maxAttempts = 120 // 4 minutes
  for (let i = 0; i < maxAttempts; i++) {
    const { data } = await api.get(`/documents/${docId}`)
    
    let uiStatus: DocProgress['status'] = 'waiting'
    if (data.status === 'extracting') {
      uiStatus = 'extracting'
    } else if (data.status === 'extracted') {
      uiStatus = 'chunking'
    } else if (data.status === 'chunked' || data.status === 'embedding') {
      uiStatus = 'embedding'
    } else if (data.status === 'embedded') {
      uiStatus = 'done'
      onStatusUpdate(uiStatus)
      return
    } else if (data.status === 'failed') {
      uiStatus = 'failed'
      onStatusUpdate(uiStatus, data.extraction_error ?? 'Processing failed')
      throw new Error(data.extraction_error ?? 'Processing failed')
    }
    
    onStatusUpdate(uiStatus)
    await sleep(2000)
  }
  throw new Error('Processing timed out')
}

function sleep(ms: number) {
  return new Promise(resolve => setTimeout(resolve, ms))
}