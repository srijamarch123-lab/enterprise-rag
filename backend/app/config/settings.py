from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # Database
    database_url: str = "sqlite:///./rag_demo.db"

    # OpenAI
    openai_api_key: str = ""
    groq_api_key: str = ""

    # Qdrant
    qdrant_url: str = ""
    qdrant_api_key: str = ""
    qdrant_collection_name: str = "enterprise_rag"

    # JWT
    jwt_secret_key: str = "change-me"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 60
    jwt_refresh_token_expire_days: int = 7

    # Google Drive
    google_credentials_path: str = "credentials.json"

    # App
    upload_dir: str = "uploads"
    max_upload_size_mb: int = 50
    allowed_extensions: str = "pdf,docx,pptx,txt,png,jpg,jpeg,csv,xlsx,xls,md"
    cors_allowed_origins: str = "http://localhost:5173,http://localhost:3000,https://enterprise-rag-frontend-ez1k.onrender.com"

    # Embedding
    embedding_model: str = "text-embedding-3-small"
    chunk_size: int = 800
    chunk_overlap: int = 150

    # OCR (Windows requires system dependencies installed)
    ocr_enabled: bool = True
    # If native page text has fewer than this many non-whitespace characters, we try OCR.
    ocr_min_chars_per_page: int = 50

    # Azure Cognitive Services (OCR Failover)
    azure_cognitive_key: str = ""
    azure_cognitive_endpoint: str = ""

    # Rate Limiting
    rate_limit_chat: str = "10 per minute"
    rate_limit_upload: str = "5 per minute"

    @property
    def allowed_extensions_list(self) -> list[str]:
        return [ext.strip() for ext in self.allowed_extensions.split(",")]

    class Config:
        import os
        from pathlib import Path
        
        env_file = ".env"
        if not os.path.exists(env_file):
            fallback = Path(__file__).parent.parent.parent / ".env"
            if fallback.exists():
                env_file = str(fallback)
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    import secrets
    import os
    settings = Settings()
    
    # Fallback to DB_URL if DATABASE_URL is not set or is set to default SQLite
    db_url = os.environ.get("DB_URL")
    if db_url and (settings.database_url == "sqlite:///./rag_demo.db" or not settings.database_url):
        settings.database_url = db_url

    if not settings.jwt_secret_key or settings.jwt_secret_key == "change-me":
        settings.jwt_secret_key = secrets.token_hex(32)
        
    # Resolve relative SQLite database, google credentials, and upload paths to backend directory
    from pathlib import Path
    backend_dir = Path(__file__).parent.parent.parent.resolve()

    if settings.database_url.startswith("sqlite:///"):
        path_str = settings.database_url[10:]
        db_path = Path(path_str)
        if not db_path.is_absolute():
            settings.database_url = f"sqlite:///{ (backend_dir / db_path).resolve() }"

    creds_path = Path(settings.google_credentials_path)
    if not creds_path.is_absolute():
        settings.google_credentials_path = str((backend_dir / creds_path).resolve())

    upload_path = Path(settings.upload_dir)
    if not upload_path.is_absolute():
        settings.upload_dir = str((backend_dir / upload_path).resolve())

    return settings

