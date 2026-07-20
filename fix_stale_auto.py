content = open('backend/app/services/process_all.py', 'r', encoding='utf-8').read()

cleanup_func = '''

def cleanup_stale_qdrant_points(db):
    """Remove Qdrant points whose chunk_id no longer exists in DB."""
    try:
        from app.services.embedder import _get_qdrant
        from app.config.settings import get_settings
        from app.models import Chunk
        client = _get_qdrant()
        settings = get_settings()
        pts, _ = client.scroll(collection_name=settings.qdrant_collection_name, limit=1000, with_payload=True)
        stale = [p.id for p in pts if p.payload and p.payload.get("chunk_id") and not db.query(Chunk).filter(Chunk.id == p.payload.get("chunk_id")).first()]
        if stale:
            client.delete(collection_name=settings.qdrant_collection_name, points_selector=stale)
            print(f"Cleaned {len(stale)} stale Qdrant points")
    except Exception as e:
        print(f"Stale cleanup failed: {e}")
'''

if 'cleanup_stale_qdrant_points' not in content:
    content = content.rstrip() + cleanup_func
    open('backend/app/services/process_all.py', 'w', encoding='utf-8').write(content)
    print('Cleanup function added')
else:
    print('Already exists')
