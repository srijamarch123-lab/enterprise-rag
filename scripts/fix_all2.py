content = open('frontend/src/pages/ChatPage.tsx', 'r', encoding='utf-8', errors='ignore').read()

# Fix 1: Remove the setTimeout loadSessionMessages that causes duplication
idx = 12447
# Find the full line
line_start = content.rfind('\n', 0, idx)
line_end = content.find('\n', idx)
bad_line = content[line_start:line_end+1]
print("Removing line:", repr(bad_line))
content = content[:line_start] + content[line_end+1:]
print("Duplication fix done")

# Fix 2: Fix delete - use correct endpoint
old_delete = "await api.delete(`/chat/sessions/${sessionId}`)"
new_delete = "await api.delete(`/chat/sessions/${sessionId}`).catch(() => api.delete(`/sessions/${sessionId}`))"
if old_delete in content:
    content = content.replace(old_delete, new_delete)
    print("Delete endpoint fix done")

open('frontend/src/pages/ChatPage.tsx', 'w', encoding='utf-8').write(content)
