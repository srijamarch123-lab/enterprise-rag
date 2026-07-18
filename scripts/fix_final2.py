content = open('frontend/src/pages/ChatPage.tsx', 'r', encoding='utf-8', errors='ignore').read()

idx = content.find('setLoading(false)\n      abortControllerRef')
if idx > 0:
    old = content[idx-10:idx+60]
    print('Found:', repr(old))
    new_text = content[:idx] + 'setLoading(false)\n      if (currentActiveId) { setTimeout(() => loadSessionMessages(currentActiveId), 800) }\n      abortControllerRef' + content[idx+60:]
    open('frontend/src/pages/ChatPage.tsx', 'w', encoding='utf-8').write(new_text)
    print('Done')
else:
    print('FAILED - not found')
