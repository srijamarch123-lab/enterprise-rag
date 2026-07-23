content = open('frontend/src/pages/ChatPage.tsx', 'r', encoding='utf-8', errors='ignore').read()

old = "await api.delete(`/chat/sessions/${sessionId}`).catch(() => api.delete(`/sessions/${sessionId}`))"
new = "await api.delete(`/chat/sessions/${sessionId}`)"
content = content.replace(old, new)

open('frontend/src/pages/ChatPage.tsx', 'w', encoding='utf-8').write(content)
print('Done')
