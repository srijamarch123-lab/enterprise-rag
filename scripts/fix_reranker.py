content = open('backend/app/routes/search_v1.py', 'r', encoding='utf-8').read()

old = '        merged_results = _rerank_with_cross_encoder(req.query, merged_results)'
new = '''        import os
        if not os.environ.get("DISABLE_RERANKER"):
            merged_results = _rerank_with_cross_encoder(req.query, merged_results)'''

if old in content:
    content = content.replace(old, new)
    open('backend/app/routes/search_v1.py', 'w', encoding='utf-8').write(content)
    print('Done')
else:
    print('FAILED')
