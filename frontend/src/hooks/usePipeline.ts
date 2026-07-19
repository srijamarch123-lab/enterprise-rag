import { useState, useCallback } from 'react'
import api from '../services/api'

export type DocProgress = {
  id: number
  filename: string
  status: 'waiting' | 'extracting' | 'chunking' | 'embedding' | 'done' | 'skipped' | 'failed'
  error?: string
}

function mapStatus(backendStatus: any): DocProgress['status'] {
  const s = String(backendStatus?.value ?? backendStatus ?? '').toLowerCase()
  if (s.includes('embedded') || s === 'done') return 'done'
  if (s.includes('fail')) return 'failed'
  if (s.includes('extracting')) return 'extracting'
  if (s.includes('extracted') || s.includes('chunking')) return 'chunking'
  if (s.includes('chunked') || s.includes('embedding')) return 'embedding'
  return 'waiting'
}

export function usePipeline() {
  const [progress, setProgress] = useState<DocProgress[]>([])
  const [running, setRunning] = useState(false)
  const [summary, setSummary] = useState<{ done: number; skipped: number; failed: number } | null>(null)

  const syncDocumentStatuses = useCallback(async (targetDocIds?: number[]) => {
    try {
      const { data } = await api.get('/documents')
      if (!Array.isArray(data)) return null

      const docMap = new Map<number, any>()
      data.forEach((d: any) => docMap.set(d.id, d))

      setProgress((prev) => {
        const baseDocs = prev.length > 0 ? prev : data.map((d: any) => ({
          id: d.id,
          filename: d.filename,
          status: mapStatus(d.status),
          error: d.extraction_error || undefined,
        }))
        
        return baseDocs.map((doc) => {
          const fresh = docMap.get(doc.id)
          if (!fresh) return doc
          const st = mapStatus(fresh.status)

          return {
            ...doc,
            filename: fresh.filename || doc.filename,
            status: st,
            error: fresh.extraction_error || undefined,
          }
        })
      })

      const allDocs = Array.from(docMap.values())
      const relevant = targetDocIds && targetDocIds.length > 0 ? allDocs.filter(d => targetDocIds.includes(d.id)) : allDocs
      const isAllFinished = relevant.every(d => {
        const s = String(d.status?.value ?? d.status ?? '').toLowerCase()
        return s.includes('embedded') || s.includes('fail')
      })

      const finalDone = relevant.filter(d => {
        const s = String(d.status?.value ?? d.status ?? '').toLowerCase()
        return s.includes('embedded')
      }).length

      const finalFailed = relevant.filter(d => {
        const s = String(d.status?.value ?? d.status ?? '').toLowerCase()
        return s.includes('fail')
      }).length

      return { isAllFinished, done: finalDone, skipped: 0, failed: finalFailed }
    } catch (e) {
      console.error('Failed to sync document statuses:', e)
      return null
    }
  }, [])

  const runPipeline = useCallback(async (docIds: { id: number; filename: string }[]) => {
    setRunning(true)
    setSummary(null)

    const ids = docIds.map(d => d.id)

    // Immediate status check before triggering
    const initSync = await syncDocumentStatuses(ids)
    if (initSync && initSync.isAllFinished) {
      setSummary({ done: initSync.done, skipped: initSync.skipped, failed: initSync.failed })
      setRunning(false)
      return
    }

    // Trigger backend processing for all pending files
    try {
      await api.post('/process-all')
    } catch (e) {
      console.error('Failed to trigger process-all:', e)
    }

    const maxAttempts = 60 // 90 seconds max
    for (let i = 0; i < maxAttempts; i++) {
      const result = await syncDocumentStatuses(ids)
      if (result && result.isAllFinished) {
        setSummary({ done: result.done, skipped: result.skipped, failed: result.failed })
        setRunning(false)
        return
      }
      await new Promise(resolve => setTimeout(resolve, 1500))
    }

    const finalResult = await syncDocumentStatuses(ids)
    if (finalResult) {
      setSummary({ done: finalResult.done, skipped: finalResult.skipped, failed: finalResult.failed })
    }
    setRunning(false)
  }, [syncDocumentStatuses])

  const retry = useCallback((failedDocs: DocProgress[]) => {
    const toRetry = failedDocs
      .filter(d => d.status === 'failed' || d.status === 'skipped')
      .map(d => ({ id: d.id, filename: d.filename }))
    if (toRetry.length > 0) void runPipeline(toRetry)
  }, [runPipeline])

  return { progress, setProgress, running, summary, setSummary, runPipeline, retry, syncDocumentStatuses }
}