"""
Chunking engine using LangChain RecursiveCharacterTextSplitter + tiktoken.
Chunk size: 800 tokens, overlap: 150 tokens.
"""
import tiktoken
from langchain_text_splitters import RecursiveCharacterTextSplitter
from sqlalchemy.orm import Session

from app.models import Chunk, Document, DocumentStatus
from app.config.settings import get_settings

settings = get_settings()
_enc = tiktoken.get_encoding("cl100k_base")


def _token_len(text: str) -> int:
    return len(_enc.encode(text))


# Child Splitter (based on settings)
_child_splitter = RecursiveCharacterTextSplitter(
    chunk_size=settings.chunk_size,
    chunk_overlap=settings.chunk_overlap,
    length_function=_token_len,
    separators=["\n\n", "\n", ". ", " ", ""],
)

# Parent Splitter (larger context, e.g., 2x child size)
_parent_splitter = RecursiveCharacterTextSplitter(
    chunk_size=settings.chunk_size * 2,
    chunk_overlap=settings.chunk_overlap * 2,
    length_function=_token_len,
    separators=["\n\n", "\n", ". ", " ", ""],
)


def _chunk_spreadsheet(document: Document, db: Session) -> list[Chunk]:
    import csv
    from pathlib import Path
    
    file_path = Path(document.file_path)
    if not file_path.is_absolute():
        backend_dir = Path(__file__).parent.parent.parent.resolve()
        file_path = (backend_dir / file_path).resolve()
        
    ext = document.file_type.lower().lstrip(".")
    sheets_data: dict[str, list[list[str]]] = {}
    
    if ext == "csv":
        try:
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                reader = csv.reader(f)
                rows = [row for row in reader if row]
                if rows:
                    sheets_data["CSV"] = rows
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"Failed to read CSV for structured chunking: {e}")
    elif ext in ["xlsx", "xls"]:
        try:
            from app.services.extractor import read_xlsx_file
            sheets_data = read_xlsx_file(file_path)
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"Failed to read Excel for structured chunking: {e}")
            
    if not sheets_data:
        return []

    chunks = []
    chunk_index = 0
    
    for sheet_name, rows in sheets_data.items():
        if len(rows) < 1:
            continue
        headers = [f"{h}".strip() for h in rows[0]]
        headers_str = " | ".join(headers)
        
        group_size = 15
        data_rows = rows[1:]
        
        if not data_rows:
            c_text = f"Sheet: {sheet_name}\n| {headers_str} |"
            chunk = Chunk(
                document_id=document.id,
                chunk_index=chunk_index,
                text=c_text,
                parent_text=c_text,
                token_count=_token_len(c_text),
            )
            db.add(chunk)
            chunks.append(chunk)
            chunk_index += 1
            continue
        
        for i in range(0, len(data_rows), group_size):
            group = data_rows[i:i+group_size]
            
            lines = [
                f"Sheet: {sheet_name}",
                f"| {headers_str} |",
                f"| {' | '.join(['---' for _ in headers])} |"
            ]
            for row in group:
                row_cells = [f"{c}".replace("\n", " ").strip() for c in row]
                if len(row_cells) < len(headers):
                    row_cells += [""] * (len(headers) - len(row_cells))
                lines.append(f"| {' | '.join(row_cells[:len(headers)])} |")
                
            c_text = "\n".join(lines)
            
            parent_group_start = max(0, i - group_size)
            parent_group_end = min(len(data_rows), i + group_size * 2)
            parent_group = data_rows[parent_group_start:parent_group_end]
            
            parent_lines = [
                f"Sheet: {sheet_name}",
                f"| {headers_str} |",
                f"| {' | '.join(['---' for _ in headers])} |"
            ]
            for row in parent_group:
                row_cells = [f"{c}".replace("\n", " ").strip() for c in row]
                if len(row_cells) < len(headers):
                    row_cells += [""] * (len(headers) - len(row_cells))
                parent_lines.append(f"| {' | '.join(row_cells[:len(headers)])} |")
                
            p_text = "\n".join(parent_lines)
            
            chunk = Chunk(
                document_id=document.id,
                chunk_index=chunk_index,
                text=c_text,
                parent_text=p_text,
                token_count=_token_len(c_text),
            )
            db.add(chunk)
            chunks.append(chunk)
            chunk_index += 1
            
    return chunks


def chunk_document(document: Document, db: Session) -> list[Chunk]:
    """
    Split document extracted_text into hierarchical parent-child chunks, persist to DB, return chunks.
    """
    if not document.extracted_text and not document.file_type.lower().lstrip(".") in ["xlsx", "xls", "csv"]:
        raise ValueError(f"Document {document.id} has no extracted text.")

    # Delete any existing chunks for this document
    db.query(Chunk).filter(Chunk.document_id == document.id).delete()

    # If it is a spreadsheet, run structured chunking
    if document.file_type.lower().lstrip(".") in ["xlsx", "xls", "csv"]:
        chunks = _chunk_spreadsheet(document, db)
        if chunks:
            document.status = DocumentStatus.chunked
            db.commit()
            return chunks

    # Split into parent chunks
    parent_texts = _parent_splitter.split_text(document.extracted_text or "")

    chunks = []
    chunk_index = 0
    for p_text in parent_texts:
        # Split each parent chunk into smaller child chunks
        child_texts = _child_splitter.split_text(p_text)

        for c_text in child_texts:
            chunk = Chunk(
                document_id=document.id,
                chunk_index=chunk_index,
                text=c_text,
                parent_text=p_text,
                token_count=_token_len(c_text),
            )
            db.add(chunk)
            chunks.append(chunk)
            chunk_index += 1

    document.status = DocumentStatus.chunked
    db.commit()
    return chunks


def chunk_all_documents(db: Session) -> dict:
    """Chunk all documents with status=extracted."""
    docs = (
        db.query(Document)
        .filter(Document.status == DocumentStatus.extracted)
        .all()
    )
    results = {"processed": 0, "failed": 0, "errors": {}}
    for doc in docs:
        try:
            chunk_document(doc, db)
            results["processed"] += 1
        except Exception as e:
            doc.status = DocumentStatus.failed
            db.commit()
            results["failed"] += 1
            results["errors"][doc.id] = str(e)
    return results
