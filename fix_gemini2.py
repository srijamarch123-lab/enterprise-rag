with open('backend/app/services/llm_service.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Add Gemini stream function before _groq_stream
old = 'def _groq_stream(messages: List[Any], max_tokens: int = 900):'
new = '''def _gemini_stream(messages, max_tokens=900):
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
        raise RuntimeError(f"Gemini failed: {e}")

def _groq_stream(messages: List[Any], max_tokens: int = 900):'''

if old in content:
    content = content.replace(old, new)
    with open('backend/app/services/llm_service.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print('Gemini stream added')
else:
    print('FAILED')
