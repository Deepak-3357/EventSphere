"""OD letter metadata, signed verification, and server-side PDF generation."""

import base64
import binascii
import hashlib
import hmac
import io
import json
from datetime import datetime
from uuid import UUID, uuid4

import qrcode
from flask import current_app
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase.pdfmetrics import stringWidth
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
    except (ODLetterError, binascii.Error, UnicodeDecodeError, ValueError, TypeError, KeyError, json.JSONDecodeError):
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
                  v.name, v.location, op.full_name, t.name,
                  coalesce((select jsonb_agg(jsonb_build_object('full_name', tm.full_name, 'email', tm.email) order by tm.position)
                            from team_members tm where tm.team_id = (select r.team_id from registrations r where r.id = l.registration_id)), '[]'::jsonb)
           from od_letters l join profiles p on p.id = l.student_id
           join events e on e.id = l.event_id join venues v on v.id = e.venue_id
           join profiles op on op.id = e.organizer_id
           left join teams t on t.id = (select r.team_id from registrations r where r.id = l.registration_id)
           where l.id = %s""", (letter_id,))
    row = cursor.fetchone()
    if not row:
        return None
    values = _serialize(row)
    return {"id": values[0], "registration_id": values[1], "student_id": values[2], "event_id": values[3],
            "letter_number": values[4], "issued_at": values[5], "status": values[6],
            "student": {"name": values[7], "email": values[8], "department": values[9], "year": values[10]},
            "event": {"title": values[11], "event_date": values[12], "start_time": values[13], "end_time": values[14],
                      "status": values[15], "venue": {"name": values[16], "location": values[17]}, "organizer": values[18]},
            "team": {"name": values[19], "members": values[20] or []} if values[19] else None,
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
    margin = 54
    navy = colors.HexColor("#10233f")
    blue = colors.HexColor("#315efb")
    slate = colors.HexColor("#526176")
    line = colors.HexColor("#d8e0ec")

    def value(source, key, fallback="Not available"):
        result = source.get(key) if isinstance(source, dict) else None
        return str(result) if result not in (None, "") else fallback

    def wrap(text, font="Helvetica", size=10, max_width=width - (margin * 2)):
        words = str(text).split()
        lines, current = [], ""
        for word in words or [""]:
            candidate = f"{current} {word}".strip()
            if current and stringWidth(candidate, font, size) > max_width:
                lines.append(current)
                current = word
            else:
                current = candidate
        if current or not lines:
            lines.append(current)
        return lines

    def draw_wrapped(text, x, y, max_width, font="Helvetica", size=10, leading=14, color=colors.black):
        pdf.setFont(font, size); pdf.setFillColor(color)
        for part in wrap(text, font, size, max_width):
            pdf.drawString(x, y, part)
            y -= leading
        return y

    def draw_field(label, field_value, x, y, max_width):
        pdf.setFont("Helvetica-Bold", 9); pdf.setFillColor(slate); pdf.drawString(x, y, label.upper())
        return draw_wrapped(field_value, x, y - 14, max_width, "Helvetica", 10, 13, navy) - 7

    student = letter.get("student") or {}
    event = letter.get("event") or {}
    venue = event.get("venue") or {}
    issued = value(letter, "issued_at")[:10]
    event_date = value(event, "event_date")
    event_time = f"{value(event, 'start_time')} – {value(event, 'end_time')}"
    pdf.setTitle(f"{value(letter, 'letter_number')} - EventSphere OD Letter")
    pdf.setAuthor("EventSphere")
    pdf.setFillColor(navy); pdf.rect(0, height - 92, width, 92, fill=1, stroke=0)
    pdf.setFillColor(colors.white); pdf.setFont("Helvetica-Bold", 21); pdf.drawString(margin, height - 40, "EVENTSPHERE")
    pdf.setFont("Helvetica", 9); pdf.drawString(margin, height - 57, "Campus Event Management Portal")
    pdf.setFont("Helvetica-Bold", 18); pdf.setFillColor(navy); pdf.drawCentredString(width / 2, height - 132, "ON-DUTY PERMISSION LETTER")
    pdf.setStrokeColor(blue); pdf.setLineWidth(2); pdf.line(margin, height - 148, width - margin, height - 148)
    pdf.setFillColor(slate); pdf.setFont("Helvetica", 9); pdf.drawRightString(width - margin, height - 170, f"Reference: {value(letter, 'letter_number')}")
    pdf.drawRightString(width - margin, height - 184, f"Issued: {issued}")
    y = height - 218
    y = draw_wrapped("This EventSphere-generated request records the student's registered participation in the event below. It is not an institutional approval unless an authorized approval is recorded separately by the college.", margin, y, width - (margin * 2), "Helvetica", 10, 14, navy) - 14
    pdf.setFillColor(colors.HexColor("#f4f7fb")); pdf.roundRect(margin, y - 6, width - (margin * 2), 106, 8, fill=1, stroke=0)
    pdf.setFillColor(navy); pdf.setFont("Helvetica-Bold", 11); pdf.drawString(margin + 16, y - 28, "STUDENT DETAILS")
    left_y = y - 48
    left_y = draw_field("Student name", value(student, "name"), margin + 16, left_y, 215)
    left_y = draw_field("Department / programme", value(student, "department"), margin + 16, left_y, 215)
    draw_field("Year", value(student, "year"), margin + 270, y - 48, 215)
    draw_field("Email", value(student, "email"), margin + 270, y - 81, 215)
    y -= 132
    pdf.setFillColor(navy); pdf.setFont("Helvetica-Bold", 11); pdf.drawString(margin, y, "EVENT DETAILS")
    y -= 22
    y = draw_field("Event", value(event, "title"), margin, y, width - (margin * 2))
    y = draw_field("Date and time", f"{event_date} · {event_time}", margin, y, width - (margin * 2))
    y = draw_field("Venue", f"{value(venue, 'name')}, {value(venue, 'location')}", margin, y, width - (margin * 2))
    y = draw_field("Organizer", value(event, "organizer"), margin, y, width - (margin * 2))
    if letter.get("team"):
        team = letter["team"]
        members = ", ".join(value(member, "full_name") for member in team.get("members", []))
        y = draw_field("Team", value(team, "name"), margin, y, width - (margin * 2))
        y = draw_field("Team members", members, margin, y, width - (margin * 2))
    y -= 4
    pdf.setFillColor(colors.HexColor("#eef4ff")); pdf.roundRect(margin, y - 54, width - (margin * 2), 54, 8, fill=1, stroke=0)
    y = draw_wrapped("Request status: GENERATED · Please submit this document to the appropriate faculty or department authority for consideration.", margin + 14, y - 22, width - (margin * 2) - 28, "Helvetica-Bold", 9, 12, navy) - 14
    approval_y = 116
    pdf.setStrokeColor(line); pdf.setLineWidth(1); pdf.line(margin, approval_y + 54, width - margin, approval_y + 54)
    pdf.setFillColor(slate); pdf.setFont("Helvetica-Bold", 9); pdf.drawString(margin, approval_y + 36, "APPROVAL / ACKNOWLEDGEMENT")
    pdf.setFont("Helvetica", 8); pdf.drawString(margin, approval_y + 22, "Approval is pending unless recorded through an authorized workflow.")
    pdf.line(margin, approval_y, margin + 150, approval_y); pdf.line(width - margin - 150, approval_y, width - margin, approval_y)
    pdf.drawString(margin, approval_y - 14, "Student signature")
    pdf.drawString(width - margin - 150, approval_y - 14, "Faculty / department authority")
    qr = qrcode.make(f"{current_app.config.get('FRONTEND_ORIGIN', '').rstrip('/')}/verify/od/?letter_id={letter['id']}&token={letter['verification_token']}")
    qr_buffer = io.BytesIO(); qr.save(qr_buffer, format="PNG"); qr_buffer.seek(0)
    pdf.drawImage(ImageReader(qr_buffer), width - margin - 92, 18, 92, 92, preserveAspectRatio=True, mask="auto")
    pdf.setFillColor(slate); pdf.setFont("Helvetica", 7); pdf.drawRightString(width - margin, 10, "Scan to verify authenticity")
    pdf.setFillColor(slate); pdf.setFont("Helvetica", 7); pdf.drawString(margin, 18, f"EventSphere · {value(letter, 'letter_number')} · Generated document")
    pdf.showPage(); pdf.save(); buffer.seek(0)
    return buffer
