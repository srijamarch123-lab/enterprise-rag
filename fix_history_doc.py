with open('backend/app/routes/chat_sessions.py', 'r', encoding='utf-8') as f:
    content = f.read()

old = '    # When doc uploaded, use shorter history to save tokens for doc context\n    max_hist_tokens = 500 if has_uploaded_doc else 1500\n    history_for_prompt = truncate_chat_history(history_for_prompt, max_tokens=max_hist_tokens)'
new = '    # When doc uploaded, only keep last 1 Q&A pair to save tokens\n    if has_uploaded_doc and len(history_for_prompt) > 2:\n        history_for_prompt = history_for_prompt[-2:]\n    else:\n        history_for_prompt = truncate_chat_history(history_for_prompt)'

if old in content:
    content = content.replace(old, new)
    with open('backend/app/routes/chat_sessions.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print('Done')
else:
    print('FAILED')
    idx = content.find('When doc uploaded')
    print('Found at:', idx)
    print(repr(content[idx:idx+150]))
