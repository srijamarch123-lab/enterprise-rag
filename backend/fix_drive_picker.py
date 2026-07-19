content = open('frontend/src/pages/ChatPage.tsx', 'r', encoding='utf-8', errors='ignore').read()

idx = content.find('value={driveJson}')
if idx > 0:
    # Find textarea start
    start = content.rfind('<textarea', 0, idx)
    # Find textarea end
    end = content.find('/>', idx) + 2
    print('Found textarea at:', start, 'to', end)
    print('Current:', repr(content[start:end]))
else:
    print('NOT FOUND')
