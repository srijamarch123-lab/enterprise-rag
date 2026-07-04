from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from app.database import init_db
from app.routes.upload import router as upload_router
from app.routes.chunks import router as chunks_router
from app.routes.embeddings import router as embeddings_router
from app.routes.auth import router as auth_router
from app.routes.admin import router as admin_router

from app.routes.drive import router as drive_router
from app.routes.search import router as search_router
from app.routes.process_all import router as process_all_router
from app.routes.chat_sessions import router as chat_sessions_router


app = FastAPI(

    title="Enterprise RAG API",
    description="Document ingestion, chunking, embedding, and semantic search",
    version="1.0.0",
)

# ─── CORS ────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    expose_headers=["Set-Cookie"],

    allow_methods=["*"],

    allow_headers=["*"],
)

# ─── Routers ─────────────────────────────────────────────────────────────────
app.include_router(upload_router)
app.include_router(chunks_router)
app.include_router(embeddings_router)
app.include_router(auth_router)
app.include_router(admin_router)
app.include_router(drive_router)
app.include_router(search_router)
app.include_router(process_all_router)
app.include_router(chat_sessions_router)


# ─── Static files (optional, for serving frontend build) ─────────────────────
static_dir = Path("static")
if static_dir.exists():
    app.mount("/static", StaticFiles(directory="static"), name="static")


# ─── Startup ─────────────────────────────────────────────────────────────────
@app.on_event("startup")
def on_startup():
    init_db()
    Path("uploads").mkdir(exist_ok=True)


@app.get("/health")
def health():
    return {"status": "ok", "service": "Enterprise RAG API"}


@app.get("/")
def root():
    return {"message": "Enterprise RAG API — see /docs for Swagger UI"}
