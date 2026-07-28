content = open('frontend/src/pages/ChatPage.tsx', 'r', encoding='utf-8', errors='ignore').read()

old = '<div className="chat-page-result-preview" style={{ overflow: "hidden", display: "-webkit-box", WebkitLineClamp: 4, WebkitBoxOrient: "vertical", fontSize: "12px" }}>{((r as any).text || r.text_preview || "").slice(0, 300)}</div>'

new = '<div className="chat-page-result-preview" style={{ overflow: "hidden", display: "-webkit-box", WebkitLineClamp: 3, WebkitBoxOrient: "vertical", fontSize: "12px", lineHeight: "1.5", maxHeight: "4.5em" }}>{((r as any).text || r.text_preview || "").slice(0, 200)}</div>'

if old in content:
    content = content.replace(old, new)
    open('frontend/src/pages/ChatPage.tsx', 'w', encoding='utf-8').write(content)
    print('Done')
else:
    print('FAILED - searching...')
    idx = content.find('chat-page-result-preview')
    print(repr(content[idx:idx+200]))
