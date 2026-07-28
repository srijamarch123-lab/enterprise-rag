content = open('backend/app/routes/drive_connections.py', 'r', encoding='utf-8').read()

old = "new_files = [f for f in files if f['id'] not in existing_ids and f['name'] not in existing_names]"
new = """BLOCKED_FILENAMES = ['Enterprise_RAG_Proper_Blueprint', 'Enterprise_RAG_PM_Plan', 'Enterprise_RAG_Gantt', 'AI_Document_Search_Presentation', 'Enterprise_RAG_Master']
        new_files = [f for f in files if f['id'] not in existing_ids and f['name'] not in existing_names and not any(b in f['name'] for b in BLOCKED_FILENAMES)]"""

if old in content:
    content = content.replace(old, new)
    open('backend/app/routes/drive_connections.py', 'w', encoding='utf-8').write(content)
    print('Blueprint block done')
else:
    print('FAILED')
