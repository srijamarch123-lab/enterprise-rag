content = open('backend/app/main.py', 'r', encoding='utf-8').read()
old = 'allow_origins=["http://localhost:5173", "http://localhost:3000", "https://enterprise-rag-ysa4.onrender.com", "https://*.onrender.com"],'
new = 'allow_origins=["http://localhost:5173", "http://localhost:3000", "https://enterprise-rag-ysa4.onrender.com", "https://*.onrender.com", "https://passionate-friendship-production.up.railway.app"],'
if old in content:
    content = content.replace(old, new)
    open('backend/app/main.py', 'w', encoding='utf-8').write(content)
    print('Done')
else:
    print('FAILED - checking current origins')
    import re
    match = re.search(r'allow_origins=\[.*?\]', content)
    if match:
        print(match.group())
