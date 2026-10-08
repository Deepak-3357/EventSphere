"""Small PostgreSQL connection layer for future API modules."""

from contextlib import contextmanager

import psycopg
from flask import current_app, has_app_context

from config import DevelopmentConfig


def connection_kwargs(config=None):
    """Return psycopg keyword arguments without constructing an unsafe URL."""

    if config is None:
        config = current_app.config if has_app_context() else DevelopmentConfig
    get_value = config.get if hasattr(config, "get") else lambda key: getattr(config, key)
    required = {
        "SUPABASE_DB_HOST": get_value("SUPABASE_DB_HOST"),
        "SUPABASE_DB_PASSWORD": get_value("SUPABASE_DB_PASSWORD"),
    }
    missing = [name for name, value in required.items() if not value]
    if missing:
        raise RuntimeError(f"Missing database configuration: {', '.join(missing)}")

    return {
        "host": get_value("SUPABASE_DB_HOST"),
        "port": get_value("SUPABASE_DB_PORT"),
        "dbname": get_value("SUPABASE_DB_NAME"),
        "user": get_value("SUPABASE_DB_USER"),
        "password": get_value("SUPABASE_DB_PASSWORD"),
        "sslmode": get_value("DATABASE_SSLMODE"),
    }


@contextmanager
def get_connection(config=None):
    """Yield a transaction-scoped database connection."""

    with psycopg.connect(**connection_kwargs(config)) as connection:
        yield connection

