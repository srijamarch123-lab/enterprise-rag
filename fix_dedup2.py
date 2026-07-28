content = open('backend/app/routes/search_v1.py', 'r', encoding='utf-8').read()

old = '        if merged_results:\n            merged_results = merged_results[:top_k]'
new = '''        if merged_results:
            merged_results = merged_results[:top_k]
            seen_files = {}
            deduped = []
            for r in merged_results:
                fname = r.get("filename") or r.get("doc_name") or ""
                score = r.get("combined_score") or r.get("semantic_score") or 0
                if fname not in seen_files or score > seen_files.get(fname, 0):
                    seen_files[fname] = score
                    deduped.append(r)
            merged_results = deduped'''

if old in content:
    content = content.replace(old, new)
    open('backend/app/routes/search_v1.py', 'w', encoding='utf-8').write(content)
    print('Done')
else:
    print('FAILED - searching...')
    idx = content.find('merged_results[:top_k]')
    print('Found at:', idx)
    print(repr(content[idx-50:idx+80]))
