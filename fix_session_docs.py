content = open('backend/app/routes/chat_sessions.py', 'r', encoding='utf-8').read()

old = '''    elif session_docs:
        for doc in session_docs:
            extra_chunks.append({"text": doc["text"], "filename": doc["name"], "combined_score": 1.0})'''

new = '''    elif session_docs:
        for doc in session_docs:
            doc_text = doc["text"]
            for marker in ['Use this as additional context', 'The user has uploaded']:
                if marker in doc_text:
                    idx = doc_text.find('\\n\\n', doc_text.find(marker))
                    if idx > 0:
                        doc_text = doc_text[idx+2:]
                    break
            extra_chunks.append({"text": doc_text, "filename": doc["name"], "combined_score": 1.0})'''

if old in content:
    content = content.replace(old, new)
    open('backend/app/routes/chat_sessions.py', 'w', encoding='utf-8').write(content)
    print('Done')
else:
    print('FAILED')
