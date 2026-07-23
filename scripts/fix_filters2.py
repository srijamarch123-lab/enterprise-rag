content = open('frontend/src/pages/ChatPage.tsx', 'r', encoding='utf-8', errors='ignore').read()

# Find FILTERS label in JSX
idx = content.find('FILTERS')
print('FILTERS JSX at:', idx)
if idx > 0:
    print('Context:', repr(content[idx-100:idx+500]))
