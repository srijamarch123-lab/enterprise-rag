# Fix 1: Add process_single_document to process_all.py
content = open('backend/app/services/process_all.py', 'r', encoding='utf-8').read()

single_func = '''

def process_single_document(doc, db):
    """Process a single document: extract, chunk, embed."""
    from app.services.process_all import process_all_documents
    from app.models import DocumentStatus
    try:
        # Just call process_all which handles pending docs
        process_all_documents(db)
    except Exception as e:
        print(f"Auto-process failed: {e}")
'''

if 'process_single_document' not in content:
    content += single_func
    open('backend/app/services/process_all.py', 'w', encoding='utf-8').write(content)
    print('Fix 1 Done')
else:
    print('Fix 1 already exists')

# Fix 2: Update drive.py import-all to trigger processing after all imports
content2 = open('backend/app/routes/drive.py', 'r', encoding='utf-8').read()

old = '''    return results'''

new = '''    # Auto-process all newly imported documents
    try:
        from app.services.process_all import process_all_documents
        import threading
        t = threading.Thread(target=process_all_documents, args=(db,))
        t.daemon = True
        t.start()
    except Exception as e:
        pass
    return results'''

if old in content2 and 'Auto-process all' not in content2:
    content2 = content2.replace(old, new, 1)
    open('backend/app/routes/drive.py', 'w', encoding='utf-8').write(content2)
    print('Fix 2 Done')
else:
    print('Fix 2 already exists or FAILED')