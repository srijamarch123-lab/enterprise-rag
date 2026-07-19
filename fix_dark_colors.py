content = open('frontend/src/pages/ChatPage.tsx', 'r', encoding='utf-8', errors='ignore').read()

# Fix answer text color
old_answer = '      <div className="chat-page-message-answer-plain">'
new_answer = '      <div className="chat-page-message-answer-plain" style={{ color: isDark ? "#f0f0f0" : "#2B2A27" }}>'
if old_answer in content:
    content = content.replace(old_answer, new_answer)
    print('Answer color fixed')
else:
    print('Answer div not found')

# Fix chat input background
old_input = 'className="chat-page-input"'
new_input = 'className="chat-page-input" style={{ background: isDark ? "#2a2a2a" : "white", color: isDark ? "#f0f0f0" : "#2B2A27", borderColor: isDark ? "#3a3a3a" : undefined }}'
if old_input in content:
    content = content.replace(old_input, new_input)
    print('Input color fixed')
else:
    print('Input not found')

# Fix form background
old_form_bg = 'className="chat-page-form"'
new_form_bg = 'className="chat-page-form" style={{ background: isDark ? "#1a1a1a" : "white", borderTopColor: isDark ? "#2e2e2e" : undefined }}'
if old_form_bg in content:
    content = content.replace(old_form_bg, new_form_bg)
    print('Form bg fixed')
else:
    print('Form not found')

# Fix main area background
old_main = 'className="chat-page-main"'
new_main = 'className="chat-page-main" style={{ background: isDark ? "#212121" : "#f7f5f1" }}'
if old_main in content:
    content = content.replace(old_main, new_main)
    print('Main bg fixed')
else:
    print('Main not found')

# Fix result cards in dark mode
old_result_card = '                            <div key={r.chunk_id || i} style={{ background: \'white\', border: `1px solid ${color.border}`, borderRadius: \'12px\', padding: \'14px 16px\' }}>'
new_result_card = '                            <div key={r.chunk_id || i} style={{ background: isDark ? "#2a2a2a" : "white", border: `1px solid ${isDark ? "#3a3a3a" : color.border}`, borderRadius: "12px", padding: "14px 16px", color: isDark ? "#f0f0f0" : "#2B2A27" }}>'
if old_result_card in content:
    content = content.replace(old_result_card, new_result_card)
    print('Result card fixed')
else:
    print('Result card not found')

open('frontend/src/pages/ChatPage.tsx', 'w', encoding='utf-8').write(content)
