content = open('backend/app/routes/chat_sessions.py', 'r', encoding='utf-8').read()

old = '        extra_chunks.append({"text": req.session_context, "filename": req.session_doc_name or "uploaded_document", "combined_score": 1.0})'
new = '''        # Clean the session context - remove the instruction prefix, keep just the doc content
        doc_text = req.session_context
        prefix_markers = ['Use this as additional context', 'The user has uploaded']
        for marker in prefix_markers:
            if marker in doc_text:
                idx = doc_text.find('\\n\\n', doc_text.find(marker))
                if idx > 0:
                    doc_text = doc_text[idx+2:]
                break
        extra_chunks.append({"text": doc_text, "filename": req.session_doc_name or "uploaded_document", "combined_score": 1.0})'''

if old in content:
    content = content.replace(old, new)
    open('backend/app/routes/chat_sessions.py', 'w', encoding='utf-8').write(content)
    print('Done')
else:
    print('FAILED')
    idx = content.find('extra_chunks.append({"text": req.session_context')
    print('Found at:', idx)
    print(repr(content[idx:idx+100]))
