import io
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from fastapi.responses import JSONResponse
from app.services.auth import get_current_user

router = APIRouter(prefix="/api", tags=["extract"])

@router.post("/extract-text")
async def extract_text(
    file: UploadFile = File(...),
    current_user=Depends(get_current_user)
):
    content = await file.read()
    name = (file.filename or "").lower()

    try:
        if name.endswith(".txt") or name.endswith(".md") or name.endswith(".csv"):
            text = content.decode("utf-8", errors="ignore")
        elif name.endswith(".pdf"):
            import fitz
            doc = fitz.open(stream=content, filetype="pdf")
            text = "\n".join(page.get_text() for page in doc)
        elif name.endswith(".docx"):
            import docx
            doc = docx.Document(io.BytesIO(content))
            text = "\n".join(p.text for p in doc.paragraphs if p.text.strip())
        elif name.endswith(".pptx"):
            from pptx import Presentation
            prs = Presentation(io.BytesIO(content))
            text = "\n".join(shape.text for slide in prs.slides for shape in slide.shapes if hasattr(shape, "text") and shape.text.strip())
        elif name.endswith(".xlsx"):
            import openpyxl
            wb = openpyxl.load_workbook(io.BytesIO(content), read_only=True, data_only=True)
            rows = []
            for sheet in wb.sheetnames:
                ws = wb[sheet]
                for row in ws.iter_rows(values_only=True):
                    row_text = " | ".join(str(c) for c in row if c is not None)
                    if row_text.strip():
                        rows.append(row_text)
            text = "\n".join(rows)
        else:
            raise HTTPException(400, f"Unsupported file type. Use PDF, DOCX, PPTX, XLSX, or TXT.")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Extraction failed: {e}")

    if not text or not text.strip():
        raise HTTPException(400, "Could not extract any text from this file.")

    trimmed = text.strip()[:10000]
    return JSONResponse({"text": trimmed, "filename": file.filename, "chars": len(trimmed)})
