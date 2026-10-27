"""Public category lookup endpoints."""

from flask import Blueprint, current_app
from psycopg import DatabaseError

from app.services import event_service
from app.utils.responses import error, success


catalog_bp = Blueprint("catalog", __name__)


@catalog_bp.get("/categories")
def categories():
    try:
        response, status = success(event_service.list_categories())
        response.headers["Cache-Control"] = "public, max-age=30, stale-while-revalidate=60"
        return response, status
    except DatabaseError:
        current_app.logger.exception("Public category lookup failed")
        return error("DATABASE_ERROR", "The category request could not be completed.", 500)
