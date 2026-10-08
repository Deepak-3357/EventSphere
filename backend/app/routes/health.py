"""Health-check endpoint."""

from flask import Blueprint, jsonify


health_bp = Blueprint("health", __name__)


@health_bp.get("/health")
def health_check():
    """Return a lightweight liveness response for the API."""

    return jsonify({"status": "ok", "service": "EventSphere API"})

