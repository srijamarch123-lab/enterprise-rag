import re

# Fix 1: System prompt - remove Sources line, improve quality
llm_content = open('backend/app/services/llm_service.py', 'r', encoding='utf-8').read()
old_prompt = '''SYSTEM_PROMPT = """You are a helpful enterprise document assistant. Answer the user\'s question directly, comprehensively, and in extreme detail using only the provided document context.
Do not hallucinate or use any information not explicitly in the context.
If the answer cannot be found, respond with: "I don\'t know based on the provided documents."
Provide a highly detailed, thorough, and descriptive answer that fully addresses the question. Avoid short, simple, or overly brief summaries. Make sure to:
1. Explain all related terms, definitions, policies, or procedures mentioned in the context.
2. Structure your answer logically, using paragraphs, headers, and bullet points or numbered lists where appropriate to make it highly informative and easy to read.
3. Elaborate on any contextual facts, instructions, timelines, or requirements present in the documents to ensure the explanation is exhaustive and complete.
At the end, add a brief "Sources:" line listing only the document names used."""'''

new_prompt = '''SYSTEM_PROMPT = """You are an expert enterprise knowledge assistant.

RULES:
- Answer ONLY from the provided document context. Never use outside knowledge.
- If the answer is not found, say only: "I don\'t know based on the provided documents." Do not show any sources.
- Write naturally - use bullet points only for lists of 3+ items, otherwise use clear prose.
- Be precise - cite exact figures, dates, names, and policies from the documents.
- Keep answers concise and directly relevant. Do NOT add a Sources section."""'''

if old_prompt in llm_content:
    llm_content = llm_content.replace(old_prompt, new_prompt)
    open('backend/app/services/llm_service.py', 'w', encoding='utf-8').write(llm_content)
    print('Fix 1 Done - system prompt updated')
else:
    print('Fix 1 FAILED')

# Fix 2: Frontend - limit preview to 4 lines
chat_content = open('frontend/src/pages/ChatPage.tsx', 'r', encoding='utf-8', errors='ignore').read()

old_preview = '<div className="chat-page-result-preview">{r.text || r.text_preview}</div>'
new_preview = '<div className="chat-page-result-preview" style={{ overflow: "hidden", display: "-webkit-box", WebkitLineClamp: 4, WebkitBoxOrient: "vertical", fontSize: "12px" }}>{((r as any).text || r.text_preview || "").slice(0, 300)}</div>'

if old_preview in chat_content:
    chat_content = chat_content.replace(old_preview, new_preview)
    print('Fix 2 Done - preview limited')
else:
    print('Fix 2 FAILED')

# Fix 3: Drive URL - show regardless of file_path
old_drive = '''{(r.file_path || r.path) ? <div className="chat-page-result-path">
                                {r.drive_url ? (
                                  <a href={r.drive_url} target="_blank" rel="noopener noreferrer" onClick={(e) => e.stopPropagation()} style={{ color: 
color.adminAccent, fontSize: "11px", textDecoration: "none", display: "flex", alignItems: "center", gap: "4px" }}>'''

idx = chat_content.find('{(r.file_path || r.path) ? <div className="chat-page-result-path">')
if idx > 0:
    # Find end of this block
    end = chat_content.find(': null}', idx) + 7
    old_block = chat_content[idx:end]
    new_block = '''{(r as any).drive_url ? (
                                <a href={(r as any).drive_url} target="_blank" rel="noopener noreferrer" onClick={(e) => e.stopPropagation()} style={{ color: color.adminAccent, fontSize: "11px", textDecoration: "none", display: "inline-flex", alignItems: "center", gap: "4px", marginTop: "4px" }}>
                                  View in Google Drive
                                </a>
                              ) : null}'''
    chat_content = chat_content[:idx] + new_block + chat_content[end:]
    print('Fix 3 Done - drive URL always shown')
else:
    print('Fix 3 FAILED')

# Fix 4: Strip Sources from answer text
old_md = '<ReactMarkdown remarkPlugins={[remarkGfm]}>{m.answer || m.content || ""}</ReactMarkdown>'
new_md = '<ReactMarkdown remarkPlugins={[remarkGfm]}>{(m.answer || m.content || "").replace(/\\n?Sources?:[\\s\\S]*$/i, "").trim()}</ReactMarkdown>'
if old_md in chat_content:
    chat_content = chat_content.replace(old_md, new_md)
    print('Fix 4 Done - Sources stripped from answer')
else:
    print('Fix 4 FAILED')
    idx2 = chat_content.find('ReactMarkdown remarkPlugins')
    print('Found at:', idx2)
    print(repr(chat_content[idx2:idx2+100]))

open('frontend/src/pages/ChatPage.tsx', 'w', encoding='utf-8').write(chat_content)
