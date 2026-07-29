content = open('backend/app/routes/chat_sessions.py', 'r', encoding='utf-8').read()

# Find where extra_chunks and search happen
old = '''    extra_chunks = []
    existing_meta = session.session_metadata or {}
    session_docs = existing_meta.get("session_docs", [])
    extra_chunks = []
    if req.session_context:
        extra_chunks.append({"text": req.session_context, "filename": req.session_doc_name or "uploaded_document", "combined_score": 1.0})
    elif session_docs:
        for doc in session_docs:
            extra_chunks.append({"text": doc["text"], "filename": doc["name"], "combined_score": 1.0})
    prompt_messages = build_chat_prompt(req.content, extra_chunks + chunks, history_messages=history_for_prompt)'''

new = '''    extra_chunks = []
    existing_meta = session.session_metadata or {}
    session_docs = existing_meta.get("session_docs", [])
    has_uploaded_doc = bool(req.session_context or session_docs)
    if req.session_context:
        extra_chunks.append({"text": req.session_context, "filename": req.session_doc_name or "uploaded_document", "combined_score": 1.0})
    elif session_docs:
        for doc in session_docs:
            extra_chunks.append({"text": doc["text"], "filename": doc["name"], "combined_score": 1.0})
    # If user uploaded a doc, only use that doc - skip Qdrant search results
    if has_uploaded_doc:
        final_chunks = extra_chunks
    else:
        final_chunks = extra_chunks + chunks
    prompt_messages = build_chat_prompt(req.content, final_chunks, history_messages=history_for_prompt)'''

if old in content:
    content = content.replace(old, new)
    open('backend/app/routes/chat_sessions.py', 'w', encoding='utf-8').write(content)
    print('Done')
else:
    print('FAILED')
    idx = content.find('extra_chunks = []')
    print('Found at:', idx)
    print(repr(content[idx:idx+300]))
