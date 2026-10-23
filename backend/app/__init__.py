"""EventSphere Flask application factory."""

import os
from urllib.parse import urlsplit

from flask import Flask, request

from config import DevelopmentConfig, ProductionConfig


PRODUCTION_FRONTEND_ORIGIN = "https://eventsphere-395t.onrender.com"


def _normalize_origin(value):
    """Return a canonical HTTP(S) origin, or None for unsafe configuration."""

    if not isinstance(value, str):
        return None
    value = value.strip()
    if not value or any(character in value for character in ("*", "\\", "\n", "\r", "\t")):
        return None
    try:
        parsed = urlsplit(value)
        if parsed.scheme.lower() not in {"http", "https"} or not parsed.netloc:
            return None
        if parsed.path not in {"", "/"} or parsed.query or parsed.fragment or parsed.username or parsed.password:
            return None
        hostname = parsed.hostname
        port = parsed.port
    except ValueError:
        return None
    if not hostname:
        return None
    scheme = parsed.scheme.lower()
    hostname = hostname.lower()
    if ":" in hostname and not hostname.startswith("["):
        hostname = f"[{hostname}]"
    if port is not None and not ((scheme == "http" and port == 80) or (scheme == "https" and port == 443)):
        hostname = f"{hostname}:{port}"
    return f"{scheme}://{hostname}"


def _allowed_origins(app):
    """Build the exact origin set; production is always retained."""

    configured = [app.config.get("FRONTEND_ORIGIN", "")]
    configured.extend(str(app.config.get("FRONTEND_ALLOWED_ORIGINS", "")).split(","))
    configured.append(PRODUCTION_FRONTEND_ORIGIN)
    return {_normalize_origin(origin) for origin in configured if _normalize_origin(origin)}


def create_app(config_class=None):
    """Create and configure the Flask application."""

    if config_class is None:
        config_class = ProductionConfig if os.getenv("FLASK_ENV", "development").lower() == "production" else DevelopmentConfig
    app = Flask(__name__)
    app.config.from_object(config_class)

    from app.routes.health import health_bp
    from app.routes.auth import auth_bp
    from app.routes.catalog import catalog_bp
    from app.routes.events import events_bp
    from app.routes.public import public_bp
    from app.routes.registrations import registrations_bp
    from app.routes.notifications import notifications_bp
    from app.routes.dashboard import dashboard_bp
    from app.routes.od_letters import od_letters_bp
    from app.routes.admin import admin_bp

    app.register_blueprint(health_bp, url_prefix="/api")
    app.register_blueprint(auth_bp, url_prefix="/api/auth")
    app.register_blueprint(catalog_bp, url_prefix="/api")
    app.register_blueprint(events_bp, url_prefix="/api/events")
    app.register_blueprint(public_bp, url_prefix="/api")
    app.register_blueprint(registrations_bp, url_prefix="/api")
    app.register_blueprint(notifications_bp, url_prefix="/api")
    app.register_blueprint(dashboard_bp, url_prefix="/api")
    app.register_blueprint(od_letters_bp, url_prefix="/api")
    app.register_blueprint(admin_bp, url_prefix="/api/admin")

    @app.after_request
    def add_cors_headers(response):
        request_origin = _normalize_origin(request.headers.get("Origin", ""))
        if request_origin in _allowed_origins(app):
            response.headers["Access-Control-Allow-Origin"] = request_origin
            response.headers["Vary"] = "Origin"
            response.headers["Access-Control-Allow-Headers"] = "Authorization, Content-Type"
            response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, PATCH, DELETE, OPTIONS"
        return response

    return app

