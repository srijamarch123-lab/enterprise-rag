with open('backend/app/services/llm_service.py', 'r', encoding='utf-8') as f:
    content = f.read()

old = '''            except Exception as e:
                logger.error("Groq stream also failed: %s", e)
                raise'''

new = '''            except Exception as e:
                logger.error("Groq stream also failed: %s", e)
                try:
                    logger.info("Falling back to Gemini")
                    yield from _gemini_stream(messages, max_tokens=max_tokens)
                except Exception as gemini_err:
                    logger.error("Gemini also failed: %s", gemini_err)
                    raise'''

if old in content:
    content = content.replace(old, new)
    with open('backend/app/services/llm_service.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print('Done')
else:
    print('FAILED')
