import os
import re
from pathlib import Path

# Configure pytesseract to use explicit Tesseract path
_TESSERACT_PATH = os.environ.get("TESSERACT_CMD")
if not _TESSERACT_PATH:
    if os.name == "nt":
        _TESSERACT_PATH = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
    else:
        import shutil
        resolved = shutil.which("tesseract")
        if resolved:
            _TESSERACT_PATH = resolved
        elif os.path.exists("/usr/bin/tesseract"):
            _TESSERACT_PATH = "/usr/bin/tesseract"
        elif os.path.exists("/usr/local/bin/tesseract"):
            _TESSERACT_PATH = "/usr/local/bin/tesseract"
        else:
            _TESSERACT_PATH = "tesseract"


def extract_text(file_path: str, file_type: str) -> tuple[str, int | None]:
    path = Path(file_path)
    ext = file_type.lower().lstrip(".")

    if not path.is_absolute():
        backend_dir = Path(__file__).parent.parent.parent.resolve()
        path = (backend_dir / path).resolve()

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
    if ext in ["png", "jpg", "jpeg"]:
        return _extract_image(path)
    if ext == "csv":
        return _extract_csv(path)
    if ext in ["xlsx", "xls"]:
        return _extract_xlsx(path)
    if ext in ["md", "markdown"]:
        return _extract_markdown(path)

    raise ValueError(f"Unsupported file type: {ext}")


def _extract_pdf(path: Path) -> tuple[str, int]:
    # Import pdfplumber dynamically to extract text and tables from PDFs
    import pdfplumber
    from app.config.settings import get_settings
    from app.services.ocr_service import extract_text_cloud_ocr
    import logging

    logger = logging.getLogger(__name__)
    settings = get_settings()
    page_texts: list[str] = []
    page_count = 0
    pages_needing_ocr: list[int] = []

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

            page_texts.append(text)
            
            # Check if this specific page needs OCR
            if settings.ocr_enabled and len(text.strip()) < settings.ocr_min_chars_per_page:
                pages_needing_ocr.append(i)

    # If some pages need OCR
    if pages_needing_ocr:
        has_cloud_ocr = False
        key = os.environ.get("AZURE_COGNITIVE_KEY") or getattr(settings, "azure_cognitive_key", None)
        endpoint = os.environ.get("AZURE_COGNITIVE_ENDPOINT") or getattr(settings, "azure_cognitive_endpoint", None)
        if key and endpoint:
            has_cloud_ocr = True

        cloud_success = False
        if has_cloud_ocr:
            logger.info("Attempting Azure Cloud OCR for scanned pages...")
            cloud_text = extract_text_cloud_ocr(str(path))
            if cloud_text and cloud_text.strip():
                # Cloud OCR succeeded, it handles the entire document
                page_texts = [cloud_text]
                cloud_success = True

        if not cloud_success:
            # Fallback to local page-by-page OCR for ONLY the pages that need it
            from concurrent.futures import ThreadPoolExecutor
            logger.info(f"Attempting local Tesseract OCR for {len(pages_needing_ocr)} page(s)...")

            def ocr_page(page_num):
                txt, err = _ocr_pdf_page_fallback(path, page_num)
                return page_num, txt, err

            ocr_results = {}
            errors = []

            with ThreadPoolExecutor(max_workers=min(4, len(pages_needing_ocr) or 1)) as executor:
                futures = {executor.submit(ocr_page, p): p for p in pages_needing_ocr}
                for fut in futures:
                    p_num = futures[fut]
                    try:
                        _, txt, err = fut.result()
                        if err:
                            errors.append(err)
                        if txt and txt.strip():
                            ocr_results[p_num] = txt
                    except Exception as e:
                        errors.append(str(e))

            if errors:
                logger.warning(f"Local OCR encountered errors: {errors}")

            # Merge the OCR results back into page_texts
            for p_num, ocr_txt in ocr_results.items():
                if len(ocr_txt.strip()) > len(page_texts[p_num].strip()):
                    page_texts[p_num] = ocr_txt

    full_text = "\n".join(page_texts)
    cleaned = _clean(full_text)
    if not cleaned:
        if pages_needing_ocr and errors:
            raise ValueError(f"PDF extraction produced empty text. OCR Errors: {'; '.join(errors)}")
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


def _extract_image(path: Path) -> tuple[str, None]:
    import pytesseract
    from PIL import Image

    # Set the Tesseract path for pytesseract
    pytesseract.pytesseract.tesseract_cmd = _TESSERACT_PATH
    try:
        img = Image.open(str(path))
        text = pytesseract.image_to_string(img).strip()
        cleaned = _clean(text)
        if not cleaned:
            raise ValueError("Image OCR produced empty text")
        return cleaned, None
    except Exception as e:
        raise ValueError(f"Image extraction failed: {e}")


def _clean(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"^\s*\d+\s*$", "", text, flags=re.MULTILINE)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()


def _extract_csv(path: Path) -> tuple[str, None]:
    import csv
    rows = []
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        reader = csv.reader(f)
        for row in reader:
            if row:
                rows.append(" | ".join([cell.replace("\n", " ").strip() for cell in row]))
    return _clean("\n".join(rows)), None


def _extract_xlsx(path: Path) -> tuple[str, None]:
    import pandas as pd
    sheets_text = []
    xls = pd.read_excel(path, sheet_name=None)
    for sheet_name, df in xls.items():
        sheets_text.append(f"--- Sheet: {sheet_name} ---")
        df = df.fillna("")
        headers = " | ".join([str(col).strip() for col in df.columns])
        sheets_text.append(headers)
        sheets_text.append("-|-".join(["---" for _ in df.columns]))
        for _, row in df.iterrows():
            row_str = " | ".join([str(cell).replace("\n", " ").strip() for cell in row])
            sheets_text.append(row_str)
    return _clean("\n".join(sheets_text)), None


def _extract_markdown(path: Path) -> tuple[str, None]:
    text = path.read_text(encoding="utf-8", errors="replace")
    return _clean(text), None

