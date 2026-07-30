content = open('frontend/src/pages/ChatPage.tsx', 'r', encoding='utf-8', errors='ignore').read()

old = '<div className="chat-page-message-answer-plain" style={{ color: isDark ? "#f0f0f0" : "#2B2A27" }}>'
new = '<div className="chat-page-message-answer-plain" style={{ color: isDark ? "#f0f0f0" : "#2B2A27", wordBreak: "break-word", overflowWrap: "break-word", whiteSpace: "pre-wrap" }}>'

if old in content:
    content = content.replace(old, new)
    open('frontend/src/pages/ChatPage.tsx', 'w', encoding='utf-8').write(content)
    print('Done')
else:
    print('FAILED')
    idx = content.find('chat-page-message-answer-plain')
    print(repr(content[idx:idx+150]))
