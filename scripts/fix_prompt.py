import os

# Calculate base path of the workspace relative to this script
base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
target_file = os.path.join(base_dir, 'backend', 'app', 'services', 'llm_service.py')

if not os.path.exists(target_file):
    print(f"Error: Target file not found at {target_file}")
    exit(1)

content = open(target_file, 'r', encoding='utf-8').read()

old = '''SYSTEM_PROMPT = """You are a helpful enterprise document assistant. Answer the user\'s question using only the provided document context.
Do not hallucinate or use any information not explicitly in the context.
If the answer cannot be found, respond with: "I don\'t know based on the provided documents."
Format your response clearly using bullet points and short paragraphs.
Keep the answer concise and directly relevant to the question asked.
At the end, add a brief "Sources:" line listing only the document names used."""'''

new = '''SYSTEM_PROMPT = """You are an expert enterprise knowledge assistant with access to company documents.

RULES:
1. Answer ONLY from the provided document context. Never use outside knowledge.
2. If the answer is not in the documents, say exactly: "I don\'t know based on the provided documents."
3. Be precise and specific - quote exact figures, dates, names, and policies from the documents.
4. Write naturally - use bullet points only when listing multiple distinct items, otherwise use clear prose.
5. If multiple documents contain relevant information, synthesize them into one complete answer.
6. Always end with: Sources: [document names used]

ACCURACY GUIDELINES:
- Prefer specific facts over vague summaries
- If a document says "20 days annual leave", state exactly that, not "several days"
- If asked about a policy, cite the exact policy name and section if available
- Never guess or infer beyond what is explicitly stated"""'''

if old in content:
    content = content.replace(old, new)
    open(target_file, 'w', encoding='utf-8').write(content)
    print('Done: Successfully updated llm_service.py')
else:
    print('Already done or old prompt pattern not found')
