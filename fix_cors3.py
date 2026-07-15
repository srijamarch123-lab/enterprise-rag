content = open('backend/app/main.py', 'r', encoding='utf-8').read()
old = '    allow_origin_regex=r"https://.*\.onrender\.com",'
new = '    allow_origin_regex=r"https://.*(\.onrender\.com|\.up\.railway\.app)",'
if old in content:
    content = content.replace(old, new)
    open('backend/app/main.py', 'w', encoding='utf-8').write(content)
    print('Done')
else:
    print('FAILED')
