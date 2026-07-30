with open('backend/app/main.py', 'r', encoding='utf-8') as f:
    content = f.read()

import re
old = re.search(r'allow_origin_regex=.*?,', content)
if old:
    content = content.replace(old.group(0), 'allow_origin_regex=r"https://.*(\.onrender\.com|\.up\.railway\.app)",')
    with open('backend/app/main.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print('Done')
else:
    print('FAILED')
