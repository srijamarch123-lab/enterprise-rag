content = open('frontend/src/pages/ChatPage.tsx', 'r', encoding='utf-8', errors='ignore').read()

# Replace the entire fetch/stream block with a simple API call
old = '''      const response = await fetch(`/api/chat/sessions/${currentActiveId}/messages/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ content: query, session_context: sessionDoc ? `The user has uploaded a document called "${sessionDoc.filename}". Use this as additional context to answer questions:\\n\\n${sessionDoc.text}` : undefined, session_doc_name: sessionDoc?.filename }),
        signal: controller.signal,
      })
      const reader = response.body?.getReader()
      if (!reader) throw new Error('Streaming not available')
      const decoder = new TextDecoder()
      let streamed = ''
      let parsedResults: SearchResult[] = []
      let hasAnswer = true
      let suggestions: string[] = []
      let actualDbId: number | string | undefined = undefined

      const assistantMsgTempId = crypto.randomUUID()
      const assistantMsg: ChatMessage = { id: assistantMsgTempId, role: 'assistant', answer: '', results: [], hasAnswer: true, suggestions: [] }
      setConversations((prev) => prev.map((c) => (c.id === currentActiveId ? { ...c, messages: [...c.messages, assistantMsg] } : c)))

      while (true) {
        const { value, done } = await reader.read()
        if (done) break
        const chunk = decoder.decode(value)
        const parts = chunk.split('\\n\\n')
        for (const part of parts) {
          const trimmed = part.trim()
          if (!trimmed) continue
          const lines = trimmed.split('\\n').map((line) => line.trim())
          for (const line of lines) {
            if (!line.startsWith('data:')) continue
            const data = line.slice(5).trim()
            if (!data || data === '{}' || data === 'done' || data === 'error') continue
            if (data.startsWith('{') && data.endsWith('}')) {
              try {
                const parsed = JSON.parse(data)
                if (typeof parsed.answer === 'string') {
                  streamed = parsed.answer
                }
                if (Array.isArray(parsed.results)) parsedResults = parsed.results
                if (typeof parsed.has_answer === 'boolean') hasAnswer = parsed.has_answer
                if (Array.isArray(parsed.suggestions)) suggestions = parsed.suggestions
                if (typeof parsed.message_id === 'number') actualDbId = parsed.message_id
              } catch { streamed += data + ' ' }
            } else { streamed += data + ' ' }

            setConversations((prev) =>
              prev.map((c) =>
                c.id === currentActiveId
                  ? { ...c, messages: c.messages.map((m) => m.id === assistantMsgTempId || m.id === actualDbId ? { ...m, id: actualDbId || m.id, answer: streamed, results: parsedResults, hasAnswer, suggestions } : m) }
                  : c
              )
            )
          }
        }
      }'''

new = '''      // Simple REST approach - wait for full answer
      const assistantMsgTempId = crypto.randomUUID()
      const assistantMsg: ChatMessage = { id: assistantMsgTempId, role: 'assistant', answer: '...', results: [], hasAnswer: true, suggestions: [] }
      setConversations((prev) => prev.map((c) => (c.id === currentActiveId ? { ...c, messages: [...c.messages, assistantMsg] } : c)))

      const res = await api.post(`/chat/sessions/${currentActiveId}/messages`, {
        content: query,
        session_context: sessionDoc ? `The user has uploaded a document called "${sessionDoc.filename}". Use this as additional context:\\n\\n${sessionDoc.text}` : undefined,
      })
      const { answer, results, has_answer, suggestions, message_id } = res.data
      setConversations((prev) =>
        prev.map((c) =>
          c.id === currentActiveId
            ? { ...c, messages: c.messages.map((m) => m.id === assistantMsgTempId ? { ...m, id: message_id || m.id, answer: answer || 'No answer found.', results: results || [], hasAnswer: has_answer ?? true, suggestions: suggestions || [] } : m) }
            : c
        )
      )'''

if old in content:
    content = content.replace(old, new)
    open('frontend/src/pages/ChatPage.tsx', 'w', encoding='utf-8').write(content)
    print('Done')
else:
    print('FAILED - stream block not found')
    idx = content.find('fetch(`/api/chat/sessions/')
    print('fetch found at:', idx)
