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


_splitter = RecursiveCharacterTextSplitter(
    chunk_size=settings.chunk_size,
    chunk_overlap=settings.chunk_overlap,
    length_function=_token_len,
    separators=["\n\n", "\n", ". ", " ", ""],
)


def chunk_document(document: Document, db: Session) -> list[Chunk]:
    """
    Split document extracted_text into chunks, persist to DB, return chunks.
    """
    if not document.extracted_text:
        raise ValueError(f"Document {document.id} has no extracted text.")

    # Delete any existing chunks for this document
    db.query(Chunk).filter(Chunk.document_id == document.id).delete()

    texts = _splitter.split_text(document.extracted_text)
    chunks = []
    for idx, text in enumerate(texts):
        chunk = Chunk(
            document_id=document.id,
            chunk_index=idx,
            text=text,
            token_count=_token_len(text),
        )
        db.add(chunk)
        chunks.append(chunk)

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
