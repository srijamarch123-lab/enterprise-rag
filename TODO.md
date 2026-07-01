Step 1: Update backend search_v1.py to include doc attribution fields (doc_name, doc_id, path) and per-result confidence_score; align confidence threshold logic.
Step 2: Update frontend SearchPage.tsx UI to render confidence + source badges and updated no-answer message.
Step 3: Update backend/test_search.py to strengthen integration/security/performance tests to cover full pipeline and enforce RBAC for semantic+keyword contributions.
Step 4: Run backend test script and validate response/UI expectations.
