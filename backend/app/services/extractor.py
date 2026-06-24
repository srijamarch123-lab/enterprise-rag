import re
from pathlib import Path


def extract_text(file_path: str, file_type: str) -> tuple[str, int | None]:
    path = Path(file_path)
    ext = file_type.lower().lstrip(".")

    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")


    if ext == "pdf":
        return _extract_pdf(path)
    if ext == "docx":
        return _extract_docx(path)
    if ext == "pptx":
        return _extract_pptx(path)
    if ext == "txt":
        return _extract_txt(path)

    raise ValueError(f"Unsupported file type: {ext}")



def _extract_pdf(path: Path) -> tuple[str, int]:
    import fitz

    doc = fitz.open(str(path))
    pages: list[str] = []

    # Try native text first for every page
    for page in doc:
        text = page.get_text()

        if not text.strip():
            blocks = page.get_text("blocks")
            text = "\n".join(b[4] for b in blocks if b[4].strip())

        # OCR fallback requires system tesseract. If it isn't installed, skip.
        if not text.strip():
            text = _ocr_pdf_page_fallback(path, page.number)

        # Skip pages that remain empty after OCR
        if text and text.strip():
            pages.append(text)


    full_text = "\n".join(pages)
    page_count = len(doc)
    doc.close()
    cleaned = _clean(full_text)
    if not cleaned:
        raise ValueError("PDF extraction produced empty text (native+OCR)")
    return cleaned, page_count



def _ocr_pdf_page_fallback(path: Path, page_number_zero_based: int) -> str:
    """Return OCR text for a single PDF page, or empty string if OCR isn't possible."""
    try:
        import pytesseract

        # If tesseract isn't on PATH, this will raise.
        pytesseract.get_tesseract_version()
    except Exception:
        return ""

    try:
        from pdf2image import convert_from_path

        # Higher DPI + single-page range
        images = convert_from_path(
            str(path),
            first_page=page_number_zero_based + 1,
            last_page=page_number_zero_based + 1,
            dpi=300,
        )
        if not images:
            return ""

        img = images[0]

        # Basic preprocessing before OCR
        try:
            from PIL import Image, ImageOps

            gray = img.convert("L")
            # simple contrast stretch
            gray = ImageOps.autocontrast(gray)
            img = gray
        except Exception:
            pass

        return pytesseract.image_to_string(img).strip()
    except Exception:
        return ""


def _extract_docx(path: Path) -> tuple[str, None]:
    from docx import Document

    doc = Document(str(path))
    text = "\n".join(para.text for para in doc.paragraphs)
    return _clean(text), None


def _extract_pptx(path: Path) -> tuple[str, int]:
    from pptx import Presentation

    prs = Presentation(str(path))
    slides = []
    for slide in prs.slides:
        slide_text = []
        for shape in slide.shapes:
            if hasattr(shape, "text"):
                slide_text.append(shape.text)
        slides.append("\n".join(slide_text))
    return _clean("\n\n".join(slides)), len(prs.slides)


def _extract_txt(path: Path) -> tuple[str, None]:
    text = path.read_text(encoding="utf-8", errors="replace")
    return _clean(text), None


def _clean(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"^\s*\d+\s*$", "", text, flags=re.MULTILINE)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()

