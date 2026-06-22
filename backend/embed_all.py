from app.database import SessionLocal
from app.services.embedder import embed_all_documents, get_qdrant_stats
db = SessionLocal()
result = embed_all_documents(db)
print('Embedding result:', result)
print('Qdrant stats:', get_qdrant_stats())