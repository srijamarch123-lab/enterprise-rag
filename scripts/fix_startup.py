content = open('backend/app/main.py', 'r', encoding='utf-8').read()
old = '@app.on_event("startup")\ndef on_startup():\n    init_db()\n    Path("uploads").mkdir(exist_ok=True)'
new = '@app.on_event("startup")\ndef on_startup():\n    init_db()\n    Path("uploads").mkdir(exist_ok=True)\n    from app.startup import create_default_admin\n    create_default_admin()'
if old in content:
    content = content.replace(old, new)
    open('backend/app/main.py', 'w', encoding='utf-8').write(content)
    print('Done')
else:
    print('FAILED')
