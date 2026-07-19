content = open('frontend/src/pages/ChatPage.tsx', 'r', encoding='utf-8', errors='ignore').read()

# Find all loadSessionMessages calls
import re
matches = [(m.start(), content[max(0,m.start()-50):m.start()+100]) for m in re.finditer('loadSessionMessages', content)]
print(f"Found {len(matches)} loadSessionMessages calls:")
for pos, ctx in matches:
    print(f"At {pos}:", repr(ctx[:80]))
    print()

# Find delete handler
idx = content.find('handleDelete')
print("handleDelete at:", idx)
print("Context:", repr(content[idx:idx+300]))
