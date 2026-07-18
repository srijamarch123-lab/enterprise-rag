from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from app.services.limiter import limiter
from fastapi.responses import RedirectResponse

from app.config.settings import get_settings
from app.database import init_db
from app.routes.upload import router as upload_router
from app.routes.chunks import router as chunks_router
from app.routes.embeddings import router as embeddings_router
from app.routes.auth import router as auth_router
from app.routes.admin import router as admin_router

from app.routes.drive import router as drive_router
from app.routes.search import router as search_router
from app.routes.process_all import router as process_all_router
from app.routes.extract import router as extract_router
from app.routes.chat_sessions import router as chat_sessions_router
from app.routes.feedback import router as feedback_router

settings = get_settings()

app = FastAPI(
    title="Enterprise RAG API",
    description="Document ingestion, chunking, embedding, and semantic search",
    version="1.0.0",
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
import logging

logger = logging.getLogger(__name__)

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    if isinstance(exc, HTTPException):
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail},
        )
    logger.error(f"Global exception caught on path {request.url.path}: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "An unexpected error occurred. Please contact the administrator."},
    )

# ─── CORS ────────────────────────────────────────────────────────────────────
cors_origins = [origin.strip() for origin in settings.cors_allowed_origins.split(",") if origin.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_origin_regex=r"https://.*(\.onrender\.com|\.up\.railway\.app)",
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
app.include_router(extract_router)
app.include_router(chat_sessions_router)
app.include_router(feedback_router)



# ─── Static files (optional, for serving frontend build) ─────────────────────
static_dir = Path("static")
if static_dir.exists():
    app.mount("/static", StaticFiles(directory="static"), name="static")


# ─── Startup ─────────────────────────────────────────────────────────────────
@app.on_event("startup")
def on_startup():
    init_db()
    Path(settings.upload_dir).mkdir(parents=True, exist_ok=True)
    from app.startup import create_default_admin
    create_default_admin()
    try:
        from app.services.embedder import _get_qdrant, ensure_collection
        ensure_collection(_get_qdrant())
    except Exception as exc:
        import logging
        logging.getLogger(__name__).warning("Qdrant auto-provisioning skipped/failed: %s", exc)


@app.get("/health")
def health():
    return {"status": "ok", "service": "Enterprise RAG API"}


@app.get("/")
def root():
    # Redirect base URL to Swagger UI so Render's root endpoint shows the UI
    return RedirectResponse(url="/docs", status_code=302)

