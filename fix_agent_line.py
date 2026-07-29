with open('backend/app/routes/chat_sessions.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

print('Line 367:', repr(lines[366]))
lines[366] = lines[366].replace('if client:', 'if client and not has_uploaded_doc:')
print('Fixed to:', repr(lines[366]))

with open('backend/app/routes/chat_sessions.py', 'w', encoding='utf-8') as f:
    f.writelines(lines)
print('Done')
