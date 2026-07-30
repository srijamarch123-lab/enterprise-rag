with open('backend/app/main.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Find allow_origins list and add new URL
import re
match = re.search(r'allow_origins=\[(.*?)\]', content, re.DOTALL)
if match:
    print('Current origins:', match.group(0)[:200])
    old = match.group(0)
    if 'ai-doc-search-production' not in old:
        new = old.rstrip(']') + ', "https://ai-doc-search-production.up.railway.app"]'
        content = content.replace(old, new)
        with open('backend/app/main.py', 'w', encoding='utf-8') as f:
            f.write(content)
        print('Done')
    else:
        print('Already there')
else:
    print('FAILED')
