import os

# Calculate base path of the workspace relative to this script
base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
target_file = os.path.join(base_dir, 'frontend', 'src', 'pages', 'ChatPage.tsx')

if not os.path.exists(target_file):
    print(f"Error: Target file not found at {target_file}")
    exit(1)

content = open(target_file, 'r', encoding='utf-8', errors='ignore').read()

idx = content.find('value={driveJson}')
if idx > 0:
    # Find textarea start
    start = content.rfind('<textarea', 0, idx)
    # Find textarea end
    end = content.find('/>', idx) + 2
    print('Found textarea at:', start, 'to', end)
    print('Current:', repr(content[start:end]))
else:
    print('NOT FOUND')
