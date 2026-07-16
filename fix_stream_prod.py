content = open('backend/app/routes/chat_sessions.py', 'r', encoding='utf-8').read()

old = '''    def event_stream():
        assistant_chunks: list[str] = []
        try:
            llm = LLMService()
            for token in llm.stream_chat_completion(prompt_messages, max_tokens=900):
                assistant_chunks.append(token)
                yield f"data: {token}\\n\\n"
            final_text = "".join(assistant_chunks).strip()
            if not final_text:
                final_text = build_fallback_answer(req.content, chunks)'''

new = '''    def event_stream():
        assistant_chunks: list[str] = []
        try:
            llm = LLMService()
            final_text = llm.chat_completion(prompt_messages, max_tokens=900)
            if not final_text:
                final_text = build_fallback_answer(req.content, chunks)
            assistant_chunks = [final_text]
            yield f"data: {final_text}\\n\\n"'''

if old in content:
    content = content.replace(old, new)
    open('backend/app/routes/chat_sessions.py', 'w', encoding='utf-8').write(content)
    print('Done')
else:
    print('FAILED')
    idx = content.find('def event_stream')
    print('Found at:', idx)
    print(repr(content[idx:idx+200]))
