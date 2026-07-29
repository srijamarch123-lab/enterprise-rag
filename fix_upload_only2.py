content = open('backend/app/routes/chat_sessions.py', 'r', encoding='utf-8').read()

idx = content.find('extra_chunks = []\n    existing_meta = session.session_metadata or {}')
if idx < 0:
    print('Not found')
else:
    # Find the end of this block (prompt_messages line)
    end_marker = 'prompt_messages = build_chat_prompt(req.content, extra_chunks + chunks, history_messages=history_for_prompt)'
    end_idx = content.find(end_marker, idx)
    if end_idx < 0:
        print('End marker not found')
        # Try alternative
        end_marker2 = 'prompt_messages = build_chat_prompt(req.content,'
        end_idx = content.find(end_marker2, idx)
        end_line_end = content.find('\n', end_idx) + 1
        print('Alt end found at:', end_idx)
        print(repr(content[end_idx:end_line_end]))
    else:
        end_line_end = content.find('\n', end_idx) + 1
        old_block = content[idx:end_line_end]
        print('Found block:', repr(old_block[:100]))
        
        new_block = '''extra_chunks = []
    existing_meta = session.session_metadata or {}
    session_docs = existing_meta.get("session_docs", [])
    has_uploaded_doc = bool(req.session_context or session_docs)
    if req.session_context:
        extra_chunks.append({"text": req.session_context, "filename": req.session_doc_name or "uploaded_document", "combined_score": 1.0})
    elif session_docs:
        for doc in session_docs:
            extra_chunks.append({"text": doc["text"], "filename": doc["name"], "combined_score": 1.0})
    final_chunks = extra_chunks if has_uploaded_doc else extra_chunks + chunks
    prompt_messages = build_chat_prompt(req.content, final_chunks, history_messages=history_for_prompt)
'''
        content = content[:idx] + new_block + content[end_line_end:]
        open('backend/app/routes/chat_sessions.py', 'w', encoding='utf-8').write(content)
        print('Done')
