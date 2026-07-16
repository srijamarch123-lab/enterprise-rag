content = open('frontend/src/pages/ChatPage.tsx', 'r', encoding='utf-8', errors='ignore').read()

# After stream ends, reload session messages from DB
old = "    } finally {\n      setLoading(false)\n    }"
new = """    } finally {
      setLoading(false)
      // Reload messages from DB to ensure answer is displayed
      if (currentActiveId) {
        setTimeout(() => loadSessionMessages(currentActiveId!), 500)
      }
    }"""

if old in content:
    content = content.replace(old, new)
    open('frontend/src/pages/ChatPage.tsx', 'w', encoding='utf-8').write(content)
    print('Done')
else:
    print('FAILED')
    idx = content.find('setLoading(false)')
    print('Found at:', idx)
    print(repr(content[idx-20:idx+50]))
