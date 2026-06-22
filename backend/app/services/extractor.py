import re
from pathlib import Path


def extract_text(file_path: str, file_type: str) -> tuple[str, int | None]:
    path = Path(file_path)
    ext = file_type.lower().lstrip(".")

    if ext == "pdf":
        return _extract_pdf(path)
    elif ext == "docx":
        return _extract_docx(path)
    elif ext == "pptx":
        return _extract_pptx(path)
    elif ext == "txt":
        return _extract_txt(path)
    else:
        raise ValueError(f"Unsupported file type: {ext}")


def _extract_pdf(path: Path) -> tuple[str, int]:
    import fitz

    doc = fitz.open(str(path))
    pages = []
    for page in doc:
        text = page.get_text()
        # If a page has no text, try extracting from blocks
        if not text.strip():
            blocks = page.get_text("blocks")
            text = "\n".join(b[4] for b in blocks if b[4].strip())
        pages.append(text)

    full_text = "\n".join(pages)
    page_count = len(doc)
    doc.close()
    return _clean(full_text), page_count


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