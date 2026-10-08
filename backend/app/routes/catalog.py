"""Public category and venue lookup endpoints."""

from flask import Blueprint
from psycopg import DatabaseError

from app.services import event_service
from app.utils.responses import error, success


catalog_bp = Blueprint("catalog", __name__)


@catalog_bp.get("/categories")
def categories():
    try:
        return success(event_service.list_categories())
    except DatabaseError:
        return error("DATABASE_ERROR", "The category request could not be completed.", 500)


@catalog_bp.get("/venues")
def venues():
    try:
        return success(event_service.list_venues())
    except DatabaseError:
        return error("DATABASE_ERROR", "The venue request could not be completed.", 500)
