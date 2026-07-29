with open('backend/app/services/llm_service.py', 'r', encoding='utf-8') as f:
    content = f.read()

old = 'logger.warning("Groq stream also failed: %s", groq_err)'
new = '''logger.warning("Groq stream also failed: %s", groq_err)
            try:
                logger.info("Falling back to Gemini")
                yield from _gemini_stream(messages, max_tokens=max_tokens)
                return
            except Exception as gemini_err:
                logger.warning("Gemini also failed: %s", gemini_err)'''

if old in content:
    content = content.replace(old, new)
    with open('backend/app/services/llm_service.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print('Gemini fallback chain added')
else:
    print('FAILED')
    idx = content.find('Groq stream also failed')
    print('Found at:', idx)
    print(repr(content[idx:idx+100]))
