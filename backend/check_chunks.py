from app.database import SessionLocal
from app.models import Document, Chunk

db = SessionLocal()
docs = db.query(Document).all()
print(f'Total docs: {len(docs)}')
for doc in docs:
    chunks = db.query(Chunk).filter(Chunk.document_id == doc.id).all()
    text_len = len(doc.extracted_text or '')
    print(f'{doc.original_filename[:40]} | chunks: {len(chunks)} | text: {text_len} chars')
db.close()
