with open('backend/app/services/llm_service.py', 'r', encoding='utf-8') as f:
    content = f.read()

old_start = 'SYSTEM_PROMPT = """You are an expert enterprise knowledge assistant.'
old_end = '- If multiple documents support the same fact, cite all of them."""'

start_idx = content.find(old_start)
end_idx = content.find(old_end) + len(old_end)

new_prompt = '''SYSTEM_PROMPT = """You are an expert enterprise knowledge assistant.

RULES:
- Answer ONLY from the provided document context. Never use outside knowledge.
- If the answer is NOT in the context, say only: "I could not find this information in the available documents."
- Format naturally: use bullet points for lists of 3+ items, short paragraph for simple facts, detailed paragraphs for complex topics. Let the question guide the format.
- Be concise and precise. Do not pad answers. Do not repeat information.
- Do not add a Sources section - sources are shown separately."""'''

if start_idx > 0 and end_idx > start_idx:
    content = content[:start_idx] + new_prompt + content[end_idx:]
    with open('backend/app/services/llm_service.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print('Done')
else:
    print('FAILED')
    print('start:', start_idx, 'end:', end_idx)
