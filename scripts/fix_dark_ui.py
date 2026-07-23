content = open('frontend/src/pages/ChatPage.tsx', 'r', encoding='utf-8', errors='ignore').read()

# Fix message duplication - remove the setTimeout reload entirely
old_reload = """      if (currentActiveId) { setTimeout(() => loadSessionMessages(currentActiveId), 800) }
      abortControllerRef"""
new_reload = "      abortControllerRef"
if old_reload in content:
    content = content.replace(old_reload, new_reload)
    print('Duplication fix done')
else:
    print('Reload not found - searching...')
    idx = content.find('setTimeout(() => loadSessionMessages')
    if idx > 0:
        # Find the full line
        line_start = content.rfind('\n', 0, idx)
        line_end = content.find('\n', idx)
        print('Found at:', repr(content[line_start:line_end+1]))

open('frontend/src/pages/ChatPage.tsx', 'w', encoding='utf-8').write(content)
