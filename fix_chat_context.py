content = open('backend/app/routes/chat_sessions.py', 'r', encoding='utf-8').read()

# Fix 1: Allow multiple docs to accumulate in session
old = '''    if req.session_context and not (session.session_metadata or {}).get("session_doc"):
        session.session_metadata = {
            **(session.session_metadata or {}),
            "session_doc": req.session_context,
            "session_doc_name": req.session_doc_name or "uploaded_document"
        }'''

new = '''    if req.session_context:
        existing_meta = session.session_metadata or {}
        existing_docs = existing_meta.get("session_docs", [])
        new_doc = {"name": req.session_doc_name or "uploaded_document", "text": req.session_context}
        existing_docs.append(new_doc)
        session.session_metadata = {
            **existing_meta,
            "session_docs": existing_docs,
            "session_doc": req.session_context,
            "session_doc_name": req.session_doc_name or "uploaded_document"
        }'''

if old in content:
    content = content.replace(old, new)
    print("Fix 1 done")
else:
    print("Fix 1 FAILED")

# Fix 2: Use all accumulated docs as context
old2 = '''    session_doc_text = req.session_context or (session.session_metadata or {}).get("session_doc")
    if session_doc_text:
        extra_chunks = [{"text": session_doc_text, "filename": "uploaded_document", "combined_score": 1.0}]'''

new2 = '''    existing_meta = session.session_metadata or {}
    session_docs = existing_meta.get("session_docs", [])
    extra_chunks = []
    if req.session_context:
        extra_chunks.append({"text": req.session_context, "filename": req.session_doc_name or "uploaded_document", "combined_score": 1.0})
    elif session_docs:
        for doc in session_docs:
            extra_chunks.append({"text": doc["text"], "filename": doc["name"], "combined_score": 1.0})'''

if old2 in content:
    content = content.replace(old2, new2)
    print("Fix 2 done")
else:
    print("Fix 2 FAILED")

open('backend/app/routes/chat_sessions.py', 'w', encoding='utf-8').write(content)
