content = open('frontend/src/pages/ChatPage.tsx', 'r', encoding='utf-8', errors='ignore').read()

# Only show top 3 sources instead of all 8
old = '{m.results && m.results.length > 0 ? ('
new = '{m.results && m.results.length > 0 ? ('

# Find and update the results map to only show first 3
old2 = '{m.results.map((r, i) => {'
new2 = '{m.results.slice(0, 3).map((r, i) => {'

if old2 in content:
    content = content.replace(old2, new2)
    open('frontend/src/pages/ChatPage.tsx', 'w', encoding='utf-8').write(content)
    print('Done - limited to top 3 sources')
else:
    print('FAILED')
    idx = content.find('m.results.map')
    print('Found at:', idx)
    print(repr(content[idx:idx+50]))
