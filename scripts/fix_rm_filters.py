content = open('frontend/src/pages/ChatPage.tsx', 'r', encoding='utf-8', errors='ignore').read()

# Find and remove the filters div block
start = content.find("        <div style={{ padding: '0 16px 16px', borderBottom: `1px solid ${color.border}` }}>\n          <div style={{ fontSize: '11px', fontWeight: 600, color: '#5a8a6a', marginBottom: '8px', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Filters</div>")

if start > 0:
    # Find the closing div - count nested divs
    pos = start
    depth = 0
    while pos < len(content):
        if content[pos:pos+4] == '<div':
            depth += 1
        elif content[pos:pos+6] == '</div>':
            depth -= 1
            if depth == 0:
                end = pos + 6
                break
        pos += 1
    
    print('Removing from', start, 'to', end)
    content = content[:start] + content[end:]
    open('frontend/src/pages/ChatPage.tsx', 'w', encoding='utf-8').write(content)
    print('Done')
else:
    print('FAILED - block not found')
