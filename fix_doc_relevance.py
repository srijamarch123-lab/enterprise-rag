with open('backend/app/routes/chat_sessions.py', 'r', encoding='utf-8') as f:
    content = f.read()

old = '''    if req.session_context:
        # Clean the session context - remove the instruction prefix, keep just the doc content
        doc_text = req.session_context
        prefix_markers = ['Use this as additional context', 'The user has uploaded']
        for marker in prefix_markers:
            if marker in doc_text:
                idx = doc_text.find('\\n\\n', doc_text.find(marker))
                if idx > 0:
                    doc_text = doc_text[idx+2:]
                break
        extra_chunks.append({"text": doc_text, "filename": req.session_doc_name or "uploaded_document", "combined_score": 1.0})'''

new = '''    if req.session_context:
        doc_text = req.session_context
        # Split into paragraphs and find most relevant to current query
        query_lower = req.content.lower()
        paragraphs = [p.strip() for p in doc_text.split('\\n') if len(p.strip()) > 50]
        # Score paragraphs by keyword overlap with query
        query_words = set(w for w in query_lower.split() if len(w) > 3)
        scored = []
        for p in paragraphs:
            score = sum(1 for w in query_words if w in p.lower())
            scored.append((score, p))
        scored.sort(reverse=True)
        # Take top relevant paragraphs up to 3000 chars
        selected = []
        total = 0
        for score, p in scored:
            if total + len(p) > 3000:
                break
            selected.append(p)
            total += len(p)
        # Also include first 500 chars for context
        intro = doc_text[:500]
        final_text = intro + "\\n\\n" + "\\n".join(selected) if selected else doc_text[:3000]
        extra_chunks.append({"text": final_text, "filename": req.session_doc_name or "uploaded_document", "combined_score": 1.0})'''

if old in content:
    content = content.replace(old, new)
    with open('backend/app/routes/chat_sessions.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print('Done')
else:
    print('FAILED')
    idx = content.find('if req.session_context:')
    print('Found at:', idx)
    print(repr(content[idx:idx+100]))
