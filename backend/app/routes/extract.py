import io
from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/api", tags=["extract"])

def extract_txt(content: bytes) -> str:
    return content.decode("utf-8", errors="ignore")

def extract_pdf(content: bytes) -> str:
    try:
        import fitz
        doc = fitz.open(stream=content, filetype="pdf")
        return "\n".join(page.get_text() for page in doc)
    except Exception as e:
        raise HTTPException(500, f"PDF extraction failed: {e}")

def extract_docx(content: bytes) -> str:
    try:
        import docx
        doc = docx.Document(io.BytesIO(content))
        return "\n".join(p.text for p in doc.paragraphs if p.text.strip())
    except Exception as e:
        raise HTTPException(500, f"DOCX extraction failed: {e}")

@router.post("/extract-text")
async def extract_text(file: UploadFile = File(...)):
    content = await file.read()
    name = (file.filename or "").lower()
    if name.endswith(".txt"):
        text = extract_txt(content)
    elif name.endswith(".pdf"):
        text = extract_pdf(content)
    elif name.endswith(".docx"):
        text = extract_docx(content)
    else:
        raise HTTPException(400, "Unsupported file type. Use PDF, TXT, or DOCX.")
    if not text.strip():
        raise HTTPException(400, "Could not extract any text from this file.")
    trimmed = text.strip()[:8000]
    return JSONResponse({"text": trimmed, "filename": file.filename, "chars": len(trimmed)})
