import os
import re
from pathlib import Path

# Configure pytesseract to use explicit Tesseract path on Windows
_TESSERACT_PATH = os.environ.get("TESSERACT_CMD")
if not _TESSERACT_PATH:
    if os.name == "nt":
        _TESSERACT_PATH = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
    else:
        _TESSERACT_PATH = "tesseract"


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
    # Import pdfplumber dynamically to extract text and tables from PDFs
    import pdfplumber
    from app.config.settings import get_settings
    from app.services.ocr_service import extract_text_cloud_ocr

    settings = get_settings()
    pages: list[str] = []
    page_count = 0

    with pdfplumber.open(str(path)) as pdf:
        page_count = len(pdf.pages)
        for i, page in enumerate(pdf.pages):
            text = page.extract_text() or ""
            
            try:
                tables = page.extract_tables()
                if tables:
                    for table in tables:
                        if not table:
                            continue
                        table_str = "\n".join([" | ".join([str(cell or "").replace("\n", " ").strip() for cell in row]) for row in table])
                        text += f"\n\n[Table extracted from Page {i+1}]:\n{table_str}\n"
            except Exception:
                pass

            if text and text.strip():
                pages.append(text)

    full_text = "\n".join(pages)
    total_chars = len(full_text.strip())

    if settings.ocr_enabled and (total_chars < settings.ocr_min_chars_per_page * page_count):
        # Try cloud OCR first
        cloud_text = extract_text_cloud_ocr(str(path))
        if cloud_text and cloud_text.strip():
            full_text = cloud_text
        else:
            # Fallback to local page-by-page OCR
            from concurrent.futures import ThreadPoolExecutor

            def ocr_page(page_num):
                txt, err = _ocr_pdf_page_fallback(path, page_num)
                return page_num, txt, err

            ocr_results = [None] * page_count
            errors = []

            with ThreadPoolExecutor(max_workers=min(4, page_count or 1)) as executor:
                futures = [executor.submit(ocr_page, p) for p in range(page_count)]
                for fut in futures:
                    try:
                        p_num, txt, err = fut.result()
                        if err:
                            errors.append(err)
                        ocr_results[p_num] = txt
                    except Exception as e:
                        errors.append(str(e))

            if errors:
                raise RuntimeError(f"OCR failed: {errors[0]}")

            ocr_pages = [t for t in ocr_results if t and t.strip()]
            if ocr_pages:
                full_text = "\n".join(ocr_pages)

    cleaned = _clean(full_text)
    if not cleaned:
        raise ValueError("PDF extraction produced empty text (native+OCR)")
    return cleaned, page_count


def _ocr_pdf_page_fallback(path: Path, page_number_zero_based: int) -> tuple[str, str | None]:
    """Return (ocr_text, ocr_error).

    - ocr_error is set when system OCR prerequisites are missing (tesseract / poppler).
    - If OCR fails for other reasons, returns ("", None).
    """

    # 1) Check tesseract availability using explicit path
    import pytesseract

    # Set the Tesseract path for pytesseract
    pytesseract.pytesseract.tesseract_cmd = _TESSERACT_PATH
    try:
        version = pytesseract.get_tesseract_version()
        if not version:
            raise RuntimeError("No version")
    except Exception:
        return "", (
            f"OCR failed: Tesseract not found at {_TESSERACT_PATH}. "
            "Please install Tesseract OCR."
        )

    # 2) Convert PDF page using fitz (PyMuPDF) which does not require Poppler
    try:
        import fitz
        from PIL import Image, ImageOps
        import io

        doc = fitz.open(str(path))
        page = doc[page_number_zero_based]
        pix = page.get_pixmap(dpi=300)
        img_data = pix.tobytes("png")
        doc.close()

        img = Image.open(io.BytesIO(img_data))

        # Basic preprocessing before OCR
        try:
            gray = img.convert("L")
            gray = ImageOps.autocontrast(gray)
            img = gray
        except Exception:
            pass

        return pytesseract.image_to_string(img).strip(), None
    except Exception as e:
        return "", f"OCR page conversion failed: {e}"


def _extract_docx(path: Path) -> tuple[str, None]:
    from docx import Document

    with open(path, "rb") as f:
        doc = Document(f)
    text = "\n".join(para.text for para in doc.paragraphs)
    return _clean(text), None


def _extract_pptx(path: Path) -> tuple[str, int]:
    from pptx import Presentation

    with open(path, "rb") as f:
        prs = Presentation(f)
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

