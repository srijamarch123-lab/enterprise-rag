content = open('backend/app/routes/chat_sessions.py', 'r', encoding='utf-8').read()

old = '''    def event_stream():
        assistant_chunks: list[str] = []
        try:
            if client:
                response = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=agent_messages,
                    temperature=0.0,
                    stream=True,
                )
                for chunk in response:
                    content = chunk.choices[0].delta.content if chunk.choices else None
                    if content:
                        assistant_chunks.append(content)
                        yield f"data: {content}\\n\\n"
            else:
                llm = LLMService()
                for token in llm.stream_chat_completion(prompt_messages, max_tokens=900):
                    assistant_chunks.append(token)
                    yield f"data: {token}\\n\\n"'''

new = '''    def event_stream():
        assistant_chunks: list[str] = []
        try:
            openai_success = False
            if client:
                try:
                    response = client.chat.completions.create(
                        model="gpt-4o-mini",
                        messages=agent_messages,
                        temperature=0.0,
                        stream=True,
                    )
                    for chunk in response:
                        content = chunk.choices[0].delta.content if chunk.choices else None
                        if content:
                            assistant_chunks.append(content)
                            yield f"data: {content}\\n\\n"
                    openai_success = True
                except Exception as openai_err:
                    import logging
                    logging.getLogger(__name__).warning("OpenAI failed, falling back to Groq: %s", openai_err)
                    assistant_chunks = []
            if not openai_success:
                llm = LLMService()
                for token in llm.stream_chat_completion(prompt_messages, max_tokens=900):
                    assistant_chunks.append(token)
                    yield f"data: {token}\\n\\n"'''

if old in content:
    content = content.replace(old, new)
    open('backend/app/routes/chat_sessions.py', 'w', encoding='utf-8').write(content)
    print('Done')
else:
    print('FAILED')
    idx = content.find('def event_stream():')
    print('Found at:', idx)
    print(repr(content[idx:idx+200]))
