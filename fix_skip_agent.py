content = open('backend/app/routes/chat_sessions.py', 'r', encoding='utf-8').read()

old = '    agent_ran_tools = False\n    if client:'
new = '    agent_ran_tools = False\n    if client and not has_uploaded_doc:'

if old in content:
    content = content.replace(old, new)
    open('backend/app/routes/chat_sessions.py', 'w', encoding='utf-8').write(content)
    print('Done')
else:
    print('FAILED')
    idx = content.find('agent_ran_tools = False')
    print(repr(content[idx:idx+60]))
