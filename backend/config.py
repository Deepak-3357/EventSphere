"""Application configuration loaded from environment variables."""

import os
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")


class Config:
    """Base configuration for the EventSphere API."""

    SUPABASE_URL = os.getenv("SUPABASE_URL", "")
    SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "")
    SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
    SUPABASE_DB_PASSWORD = os.getenv("SUPABASE_DB_PASSWORD", "")
    SUPABASE_DB_HOST = os.getenv("SUPABASE_DB_HOST", "")
    SUPABASE_DB_PORT = int(os.getenv("SUPABASE_DB_PORT", "5432"))
    SUPABASE_DB_NAME = os.getenv("SUPABASE_DB_NAME", "postgres")
    SUPABASE_DB_USER = os.getenv("SUPABASE_DB_USER", "postgres")
    DATABASE_SSLMODE = os.getenv("DATABASE_SSLMODE", "require")
    FRONTEND_ORIGIN = os.getenv("FRONTEND_ORIGIN", "http://127.0.0.1:5500")
    FRONTEND_ALLOWED_ORIGINS = os.getenv("FRONTEND_ALLOWED_ORIGINS", "")
    OD_VERIFICATION_SECRET = os.getenv("OD_VERIFICATION_SECRET", "")
    JSON_SORT_KEYS = False


class DevelopmentConfig(Config):
    DEBUG = os.getenv("FLASK_DEBUG", "1") == "1"


class ProductionConfig(Config):
    """Production-safe defaults; deployment must provide all secrets externally."""

    DEBUG = False
    TESTING = False

