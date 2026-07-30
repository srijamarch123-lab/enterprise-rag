with open('backend/app/services/llm_service.py', 'r', encoding='utf-8') as f:
    content = f.read()

old = '''def _gemini_stream(messages, max_tokens=900):
    try:
        import google.generativeai as genai
        import os
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("No Gemini API key configured")
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-1.5-flash")
        system = next((m["content"] for m in messages if m["role"] == "system"), "")
        user_msgs = [m["content"] for m in messages if m["role"] != "system"]
        prompt = system + "\\n\\n" + "\\n".join(user_msgs)
        response = model.generate_content(prompt, stream=True)
        for chunk in response:
            if chunk.text:
                yield chunk.text
    except Exception as e:
        raise RuntimeError(f"Gemini failed: {e}")'''

new = '''def _gemini_stream(messages, max_tokens=900):
    import os, requests, json
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("No Gemini API key")
    system = next((m["content"] for m in messages if m["role"] == "system"), "")
    user_msgs = [m["content"] for m in messages if m["role"] != "system"]
    prompt = system + "\\n\\n" + "\\n".join(user_msgs)
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={api_key}"
    body = {"contents": [{"parts": [{"text": prompt}]}], "generationConfig": {"maxOutputTokens": max_tokens}}
    resp = requests.post(url, json=body, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    text = data["candidates"][0]["content"]["parts"][0]["text"]
    yield text'''

if old in content:
    content = content.replace(old, new)
    with open('backend/app/services/llm_service.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print('Done')
else:
    print('FAILED')
    idx = content.find('def _gemini_stream')
    print('Found at:', idx)
