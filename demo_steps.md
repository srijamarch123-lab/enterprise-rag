<!-- # enterprise-rag demo steps

## Setup
1. Start backend (uvicorn) and frontend (vite).
2. Use login page to create/login users.

## Auth + RBAC demo (cookie JWT)
1. Login as **employee**.
2. Verify employee cannot access admin endpoints:
   - Call `GET /api/admin/users` → expect **403**.
3. Login as **admin**.
4. Verify admin access:
   - `GET /api/admin/users` works.
   - `PUT /api/admin/users/role` changes a user’s role.
   - `POST /api/admin/users/{id}/force-logout` invalidates that user’s cookie token (token_version bump).

## Auth security verification notes
- Tokens are expected in **HttpOnly cookies** (not localStorage).
- XSS cannot read the cookies (still protected by HttpOnly).
- Forced logout invalidates by token_version mismatch.

## Ingestion/search demo limitation (OCR availability)
- In this environment, **system Tesseract binary is not installed**, so OCR fallback cannot extract text from OCR-needed PDFs.
- For demo search: use **.txt** or **.docx** files so native extraction works.

## Search demo with supported inputs
1. Upload `.txt` or `.docx` (manager role required for upload).
2. Wait until document status becomes extracted/chunked/embedded.
3. Use `POST /api/search/search` with a query.
4. Verify results include chunk payloads restricted by role visibility policy.

## Multiple simultaneous login test
1. Open two browser profiles/windows.
2. Login as the same user in both.
3. Verify both can call `/api/auth/me` successfully.
4. Trigger `force-logout` from admin for that user.
5. Verify both sessions become unauthorized (cookie no longer validates).
 -->
