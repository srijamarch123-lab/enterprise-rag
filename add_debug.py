from pathlib import Path

path = Path("backend/app/routes/search_v1.py")
text = path.read_text(encoding="utf-8")

old = '''        top_score = merged_results[0].get("combined_score", 0) if merged_results else 0
        has_answer = top_score >= CONFIDENCE_THRESHOLD'''

new = '''        top_score = merged_results[0].get("combined_score", 0) if merged_results else 0
        has_answer = top_score >= CONFIDENCE_THRESHOLD

        logger.warning(f"RAG DEBUG | top_score={top_score} threshold={CONFIDENCE_THRESHOLD} has_answer={has_answer}")
        logger.warning(f"RAG DEBUG | retrieved_chunks={len(merged_results)}")
'''

if old not in text:
    print("Pattern not found")
else:
    text = text.replace(old, new, 1)
    path.write_text(text, encoding="utf-8")
    print("Done")
