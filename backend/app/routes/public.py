"""Small public configuration endpoint for the browser Auth client."""

from flask import Blueprint, current_app, jsonify


public_bp = Blueprint("public", __name__)


@public_bp.get("/config")
def public_config():
    """Expose only values intended for the public Supabase browser client."""

    return jsonify(
        {
            "supabaseUrl": current_app.config.get("SUPABASE_URL", ""),
            "supabasePublishableKey": current_app.config.get("SUPABASE_ANON_KEY", ""),
        }
    )
