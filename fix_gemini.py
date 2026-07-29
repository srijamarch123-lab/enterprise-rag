with open('backend/app/services/llm_service.py', 'r', encoding='utf-8') as f:
    content = f.read()

old = '''def _groq_stream(messages, max_tokens=900):
    try:
        from groq import Groq
        client = Groq(api_key=settings.groq_api_key)
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=messages,
            max_tokens=max_tokens,
            stream=True,
        )
        for chunk in response:
            content = chunk.choices[0].delta.content
            if content:
                yield content
    except Exception as e:
        raise'''

new = '''def _gemini_stream(messages, max_tokens=900):
    try:
        import google.generativeai as genai
        import os
        api_key = os.environ.get("GEMINI_API_KEY") or getattr(settings, "gemini_api_key", None)
        if not api_key:
            raise ValueError("No Gemini API key")
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-1.5-flash")
        # Convert messages to Gemini format
        system = next((m["content"] for m in messages if m["role"] == "system"), "")
        user_msgs = [m["content"] for m in messages if m["role"] != "system"]
        prompt = system + "\\n\\n" + "\\n".join(user_msgs)
        response = model.generate_content(prompt, stream=True)
        for chunk in response:
            if chunk.text:
                yield chunk.text
    except Exception as e:
        raise

def _groq_stream(messages, max_tokens=900):
    try:
        from groq import Groq
        client = Groq(api_key=settings.groq_api_key)
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=messages,
            max_tokens=max_tokens,
            stream=True,
        )
        for chunk in response:
            content = chunk.choices[0].delta.content
            if content:
                yield content
    except Exception as e:
        raise'''

if old in content:
    content = content.replace(old, new)
    with open('backend/app/services/llm_service.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print('Gemini added')
else:
    print('FAILED - finding groq stream')
    idx = content.find('def _groq_stream')
    print('Found at:', idx)
    print(repr(content[idx:idx+100]))
