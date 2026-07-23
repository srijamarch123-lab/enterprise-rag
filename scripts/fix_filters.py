content = open('frontend/src/pages/ChatPage.tsx', 'r', encoding='utf-8', errors='ignore').read()

# Find the FILTERS section in the sidebar
idx = content.find('// Filters')
print('Filters comment at:', idx)
print('Context:', repr(content[idx:idx+300]))
