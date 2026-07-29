content = open('frontend/src/pages/ChatPage.tsx', 'r', encoding='utf-8', errors='ignore').read()

old = "body: JSON.stringify({ content: query, session_context: sessionDoc ? `The user has uploaded a document called \"${sessionDoc.filename}\". Use this as additional context to answer questions:\\n\\n${sessionDoc.text}` : undefined, session_doc_name: sessionDoc?.filename }),"
new = "body: JSON.stringify({ content: query, session_context: sessionDoc ? sessionDoc.text : undefined, session_doc_name: sessionDoc?.filename }),"

if old in content:
    content = content.replace(old, new)
    open('frontend/src/pages/ChatPage.tsx', 'w', encoding='utf-8').write(content)
    print('Done')
else:
    print('FAILED')
    idx = content.find('session_context: sessionDoc')
    print('Found at:', idx)
    print(repr(content[idx:idx+200]))
