"""
Configuration management for environment variables
Loads all configuration from environment variables as specified in .env.example
"""
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional
from pathlib import Path
import os


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""
    
    # Supabase Configuration
    SUPABASE_URL: str
    SUPABASE_ANON_KEY: str
    SUPABASE_SERVICE_ROLE_KEY: str
    SUPABASE_PROJECT_ID: str
    SUPABASE_STORAGE_BUCKET: str = "invoice_files"
    
    # Microsoft Graph API Configuration
    GRAPH_TENANT_ID: str
    GRAPH_CLIENT_ID: str
    GRAPH_CLIENT_SECRET: str
    INVOICE_MAIL_ADDRESS: str
    
    # Cloud Run Configuration
    PORT: int = 8080
    HOST: str = "0.0.0.0"
    
    # Worker Settings
    MAX_EMAILS_PER_RUN: int = 5
    POLL_INTERVAL_MINUTES: int = 90
    ENABLE_BACKGROUND_POLLING: bool = False  # Set to False for Cloud Run with Cloud Scheduler
    
    # PDF Processing Settings
    MAX_PDF_SIZE_MB: int = 10
    SUPPORTED_EXTENSIONS: str = ".pdf"
    
    # Validation Settings
    PRICE_TOLERANCE_PERCENT: float = 5.0
    
    # OpenAI Configuration
    # Accept both OPENAI_API_KEY and OPEN_API_KEY (typo variant in .env)
    OPENAI_API_KEY: Optional[str] = None
    
    model_config = SettingsConfigDict(
        # Find .env file relative to this config.py file location
        # Check both backend/.env and project root .env
        env_file=[
            str(Path(__file__).parent.parent / ".env"),  # backend/.env (preferred)
            str(Path(__file__).parent.parent.parent / ".env"),  # project root .env (fallback)
        ],
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",  # Ignore extra fields like OPEN_API_KEY
    )
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Handle OPEN_API_KEY typo - check environment if OPENAI_API_KEY is None
        if self.OPENAI_API_KEY is None:
            self.OPENAI_API_KEY = os.getenv("OPEN_API_KEY") or os.getenv("OPENAI_API_KEY")


# Global settings instance
settings = Settings()

