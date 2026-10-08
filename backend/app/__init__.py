"""EventSphere Flask application factory."""

import os

from flask import Flask, request

from config import DevelopmentConfig, ProductionConfig


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
    from app.routes.attendance import attendance_bp
    from app.routes.dashboard import dashboard_bp
    from app.routes.od_letters import od_letters_bp

    app.register_blueprint(health_bp, url_prefix="/api")
    app.register_blueprint(auth_bp, url_prefix="/api/auth")
    app.register_blueprint(catalog_bp, url_prefix="/api")
    app.register_blueprint(events_bp, url_prefix="/api/events")
    app.register_blueprint(public_bp, url_prefix="/api")
    app.register_blueprint(registrations_bp, url_prefix="/api")
    app.register_blueprint(notifications_bp, url_prefix="/api")
    app.register_blueprint(attendance_bp, url_prefix="/api")
    app.register_blueprint(dashboard_bp, url_prefix="/api")
    app.register_blueprint(od_letters_bp, url_prefix="/api")

    @app.after_request
    def add_cors_headers(response):
        allowed_origin = app.config.get("FRONTEND_ORIGIN")
        if request.headers.get("Origin") == allowed_origin:
            response.headers["Access-Control-Allow-Origin"] = allowed_origin
            response.headers["Vary"] = "Origin"
            response.headers["Access-Control-Allow-Headers"] = "Authorization, Content-Type"
            response.headers["Access-Control-Allow-Methods"] = "GET, POST, PATCH, DELETE, OPTIONS"
        return response

    return app

