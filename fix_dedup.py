content = open('backend/app/routes/search_v1.py', 'r', encoding='utf-8').read()

old = '''        # Enrich results with full chunk text and drive_url from DB'''
new = '''        # Deduplicate by filename - keep highest scoring result per file
        seen_files = {}
        deduped = []
        for r in merged_results:
            fname = r.get("filename", "") or r.get("doc_name", "")
            score = r.get("combined_score", 0) or r.get("semantic_score", 0)
            if fname not in seen_files or score > seen_files[fname]:
                seen_files[fname] = score
                deduped.append(r)
        merged_results = deduped

        # Enrich results with full chunk text and drive_url from DB'''

if old in content:
    content = content.replace(old, new)
    open('backend/app/routes/search_v1.py', 'w', encoding='utf-8').write(content)
    print('Done')
else:
    print('FAILED')
