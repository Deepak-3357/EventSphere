"""Consistent JSON response helpers for REST endpoints."""

from flask import jsonify


def success(data, status=200, pagination=None):
    body = {"success": True, "data": data}
    if pagination is not None:
        body["pagination"] = pagination
    return jsonify(body), status


def error(code, message, status, details=None):
    return jsonify(
        {
            "success": False,
            "error": {"code": code, "message": message, "details": details or {}},
        }
    ), status
