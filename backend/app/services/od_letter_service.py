"""OD letter metadata, signed verification, and server-side PDF generation."""

import base64
import hashlib
import hmac
import io
import json
from datetime import datetime
from uuid import UUID, uuid4

import qrcode
from flask import current_app
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from app.db import get_connection


class ODLetterError(Exception):
    def __init__(self, code, message, status=409):
        super().__init__(message)
        self.code, self.message, self.status = code, message, status


def _id(value, field):
    try:
        return str(UUID(str(value)))
    except (TypeError, ValueError, AttributeError):
        raise ODLetterError("INVALID_ID", f"{field} must be a valid UUID", 422)


def _secret():
    value = current_app.config.get("OD_VERIFICATION_SECRET", "")
    if not value:
        raise ODLetterError("CONFIGURATION_ERROR", "OD verification is not configured", 500)
    return value.encode("utf-8")


def _token(letter_id):
    letter_id = str(letter_id)
    signature = hmac.new(_secret(), letter_id.encode(), hashlib.sha256).hexdigest()
    raw = json.dumps({"letter_id": letter_id, "signature": signature}, separators=(",", ":")).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def verify_token(raw_token, letter_id):
    if not isinstance(raw_token, str) or len(raw_token) > 2048:
        return False
    try:
        padded = raw_token + "=" * (-len(raw_token) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded.encode()).decode())
        supplied_id = _id(payload.get("letter_id"), "letter_id")
        signature = payload.get("signature", "")
    except (ValueError, TypeError, KeyError, json.JSONDecodeError):
        return False
    expected = hmac.new(_secret(), supplied_id.encode(), hashlib.sha256).hexdigest()
    return supplied_id == str(letter_id) and hmac.compare_digest(signature, expected)


def _serialize(row):
    return [value.isoformat() if hasattr(value, "isoformat") else str(value) if isinstance(value, UUID) else value for value in row]


def _letter_data(cursor, letter_id):
    cursor.execute(
        """select l.id, l.registration_id, l.student_id, l.event_id, l.letter_number,
                  l.issued_at, l.status, p.full_name, p.email, p.department, p.year,
                  e.title, e.event_date, e.start_time, e.end_time, e.status,
                  v.name, v.location, op.full_name
           from od_letters l join profiles p on p.id = l.student_id
           join events e on e.id = l.event_id join venues v on v.id = e.venue_id
           join profiles op on op.id = e.organizer_id where l.id = %s""", (letter_id,))
    row = cursor.fetchone()
    if not row:
        return None
    values = _serialize(row)
    return {"id": values[0], "registration_id": values[1], "student_id": values[2], "event_id": values[3],
            "letter_number": values[4], "issued_at": values[5], "status": values[6],
            "student": {"name": values[7], "email": values[8], "department": values[9], "year": values[10]},
            "event": {"title": values[11], "event_date": values[12], "start_time": values[13], "end_time": values[14],
                      "status": values[15], "venue": {"name": values[16], "location": values[17]}, "organizer": values[18]},
            "verification_token": _token(values[0])}


def create_or_get(registration_id, student_id):
    registration_id, student_id = _id(registration_id, "registration_id"), _id(student_id, "student_id")
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """select r.status, r.student_id, e.id, e.status from registrations r join events e on e.id = r.event_id
                   where r.id = %s""", (registration_id,))
            registration = cursor.fetchone()
            if not registration or str(registration[1]) != student_id:
                raise ODLetterError("NOT_FOUND", "Registration not found", 404)
            if registration[0] != "registered" or registration[3] != "published":
                raise ODLetterError("OD_NOT_ELIGIBLE", "An active published-event registration is required", 409)
            cursor.execute("select id from od_letters where registration_id = %s", (registration_id,))
            existing = cursor.fetchone()
            if not existing:
                letter_number = f"OD-{uuid4().hex[:8].upper()}"
                cursor.execute("""insert into od_letters (registration_id, student_id, event_id, letter_number)
                                 values (%s, %s, %s, %s) returning id""", (registration_id, student_id, registration[2], letter_number))
                existing = cursor.fetchone()
            return _letter_data(cursor, existing[0])


def get_for_student(letter_id, student_id):
    letter_id, student_id = _id(letter_id, "letter_id"), _id(student_id, "student_id")
    with get_connection() as connection:
        with connection.cursor() as cursor:
            letter = _letter_data(cursor, letter_id)
            if not letter or letter["student_id"] != student_id:
                raise ODLetterError("NOT_FOUND", "OD letter not found", 404)
            return letter


def get_for_registration(registration_id, student_id):
    registration_id, student_id = _id(registration_id, "registration_id"), _id(student_id, "student_id")
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("select id from od_letters where registration_id = %s and student_id = %s", (registration_id, student_id))
            row = cursor.fetchone()
            if not row:
                raise ODLetterError("NOT_FOUND", "OD letter not found", 404)
            return _letter_data(cursor, row[0])


def verify_public(letter_id, raw_token):
    letter_id = _id(letter_id, "letter_id")
    if not verify_token(raw_token, letter_id):
        raise ODLetterError("INVALID_VERIFICATION", "OD verification token is invalid", 404)
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("""select l.letter_number, l.issued_at, l.status, r.status, e.title, e.event_date
                             from od_letters l join registrations r on r.id = l.registration_id
                             join events e on e.id = l.event_id where l.id = %s""", (letter_id,))
            row = cursor.fetchone()
            if not row:
                raise ODLetterError("INVALID_VERIFICATION", "OD letter could not be verified", 404)
            values = _serialize(row)
            valid = values[2] == "generated" and values[3] == "registered"
            return {"valid": valid, "letter_number": values[0], "issued_at": values[1],
                    "status": "VALID" if valid else "CANCELLED", "event": values[4], "event_date": values[5]}


def generate_pdf(letter):
    if letter["status"] != "generated":
        raise ODLetterError("OD_UNAVAILABLE", "This OD letter is no longer downloadable", 409)
    registration_id = letter["registration_id"]
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("select status from registrations where id = %s", (registration_id,))
            status = cursor.fetchone()
            if not status or status[0] != "registered":
                raise ODLetterError("OD_UNAVAILABLE", "OD letters are unavailable after registration cancellation", 409)
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    pdf.setTitle(f"{letter['letter_number']} - EventSphere OD Letter")
    pdf.setFont("Helvetica-Bold", 16); pdf.drawCentredString(width / 2, height - 60, "EVENTSPHERE")
    pdf.setFont("Helvetica", 10); pdf.drawCentredString(width / 2, height - 78, "Campus Event Management Portal")
    pdf.setFont("Helvetica-Bold", 18); pdf.drawCentredString(width / 2, height - 125, "ON-DUTY LETTER")
    pdf.setFont("Helvetica", 10); pdf.drawString(55, height - 160, f"OD Letter ID: {letter['letter_number']}")
    pdf.drawString(55, height - 178, f"Issued: {letter['issued_at'][:10]}")
    y = height - 225; pdf.setFont("Helvetica", 11)
    lines = [f"Student Name: {letter['student']['name']}", f"Department: {letter['student']['department'] or 'Not available'}",
             f"Year: {letter['student']['year'] or 'Not available'}", "", f"Event: {letter['event']['title']}",
             f"Date: {letter['event']['event_date']}", f"Time: {letter['event']['start_time']} - {letter['event']['end_time']}",
             f"Venue: {letter['event']['venue']['name']}, {letter['event']['venue']['location']}",
             f"Event Organizer: {letter['event']['organizer']}"]
    pdf.drawString(55, y, "This EventSphere-generated letter records the following event participation:"); y -= 28
    for line in lines:
        pdf.drawString(70, y, line); y -= 20
    pdf.line(55, 120, width - 55, 120); pdf.drawString(70, 95, "Student"); pdf.drawString(width - 180, 95, "Event Coordinator")
    qr = qrcode.make(f"{current_app.config.get('FRONTEND_ORIGIN', '').rstrip('/')}/verify/od/?letter_id={letter['id']}&token={letter['verification_token']}")
    qr_buffer = io.BytesIO(); qr.save(qr_buffer, format="PNG"); qr_buffer.seek(0)
    pdf.drawImage(ImageReader(qr_buffer), width - 170, 135, 105, 105)
    pdf.setFont("Helvetica", 8); pdf.drawString(width - 170, 125, "EventSphere verification QR")
    pdf.showPage(); pdf.save(); buffer.seek(0)
    return buffer
