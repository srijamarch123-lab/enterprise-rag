content = open('backend/app/services/auth.py', 'r', encoding='utf-8').read()
old = '    is_render = os.environ.get("RENDER") == "true"'
new = '    is_render = os.environ.get("RENDER") == "true" or os.environ.get("RAILWAY_ENVIRONMENT") is not None'
if old in content:
    content = content.replace(old, new)
    open('backend/app/services/auth.py', 'w', encoding='utf-8').write(content)
    print('Done')
else:
    print('FAILED')
