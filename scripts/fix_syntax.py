content = open('frontend/src/pages/ChatPage.tsx', 'r', encoding='utf-8', errors='ignore').read()

old = "      setLoading(false)      abortControllerRef  }"
new = "      setLoading(false)\n      abortControllerRef.current = null\n    }"

if old in content:
    content = content.replace(old, new)
    open('frontend/src/pages/ChatPage.tsx', 'w', encoding='utf-8').write(content)
    print('Done')
else:
    print('FAILED')
    idx = content.find('setLoading(false)')
    print(repr(content[idx:idx+80]))
