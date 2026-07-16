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
    allowed_extensions: str = "pdf,docx,pptx,txt"
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
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    import secrets
    settings = Settings()
    if not settings.jwt_secret_key or settings.jwt_secret_key == "change-me":
        settings.jwt_secret_key = secrets.token_hex(32)
    return settings
