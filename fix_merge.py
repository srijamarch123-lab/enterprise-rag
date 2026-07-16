content = open('frontend/src/pages/ChatPage.tsx', 'r', encoding='utf-8', errors='ignore').read()

old = '''  const loadSessionMessages = async (sessionId: string) => {
    try {
      const { data } = await api.get(`/chat/sessions/${sessionId}`)
      const mappedMessages = (data.messages || []).map((m: any) => ({'''

new = '''  const loadSessionMessages = async (sessionId: string, mergeOnly = false) => {
    try {
      const { data } = await api.get(`/chat/sessions/${sessionId}`)
      const mappedMessages = (data.messages || []).map((m: any) => ({'''

if old in content:
    content = content.replace(old, new)
    print('Fix 1 done')
else:
    print('Fix 1 FAILED')

# Fix the setConversations call to merge instead of replace
old2 = '''      setConversations((prev) => prev.map((c) => (c.id === sessionId ? { ...c, messages: mappedMessages } : c)))'''
new2 = '''      setConversations((prev) => prev.map((c) => {
        if (c.id !== sessionId) return c
        if (mergeOnly) {
          // Keep local messages, only add ones from DB that have content
          const localIds = new Set(c.messages.map((m: any) => m.id))
          const newMsgs = mappedMessages.filter((m: any) => !localIds.has(m.id) && m.content)
          return { ...c, messages: [...c.messages, ...newMsgs] }
        }
        return { ...c, messages: mappedMessages }
      }))'''

if old2 in content:
    content = content.replace(old2, new2)
    print('Fix 2 done')
else:
    print('Fix 2 FAILED')

# Use mergeOnly=true in the finally block
old3 = 'setTimeout(() => loadSessionMessages(currentActiveId), 2000)'
new3 = 'setTimeout(() => loadSessionMessages(currentActiveId, true), 1500)'

if old3 in content:
    content = content.replace(old3, new3)
    print('Fix 3 done')
else:
    print('Fix 3 FAILED')
    idx = content.find('loadSessionMessages(currentActiveId)')
    print('Found at:', idx)
    print(repr(content[idx-10:idx+60]))

open('frontend/src/pages/ChatPage.tsx', 'w', encoding='utf-8').write(content)
