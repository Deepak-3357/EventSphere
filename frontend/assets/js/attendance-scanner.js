const scannerMessage = document.querySelector("#scannerMessage");
const eventSelect = document.querySelector("#eventSelect");
const summary = document.querySelector("#attendanceSummary");
const attendeeList = document.querySelector("#attendeeList");
let qrScanner;
let checkInInProgress = false;

function scannerRole() { return window.location.pathname.includes("/admin/") ? "admin" : "organizer"; }
function showScannerMessage(message, danger = false) { scannerMessage.className = `small mt-3 ${danger ? "text-danger" : "text-success"}`; scannerMessage.textContent = message; }
function normalizeDecodedPayload(decodedText) {
  let candidate = String(decodedText || "").trim();
  if (!candidate) throw new Error("The scanned QR code is empty.");
  try {
    let document = JSON.parse(candidate);
    if (typeof document === "string") {
      candidate = document.trim();
      document = JSON.parse(candidate);
    }
    if (!document || Array.isArray(document) || document.type !== "eventsphere_attendance"
      || typeof document.registration_id !== "string" || typeof document.token !== "string") {
      throw new Error("invalid attendance payload");
    }
  } catch (_) {
    throw new Error("The scanned QR code is not a valid EventSphere attendance pass.");
  }
  return candidate;
}
async function fetchWithTimeout(url, options, timeoutMs = 15000) {
  const controller = new AbortController();
  const timeoutId = window.setTimeout(() => controller.abort(), timeoutMs);
  try {
    return await fetch(url, { ...options, signal: controller.signal });
  } finally {
    window.clearTimeout(timeoutId);
  }
}
function renderAttendance(data) {
  const s = data.summary;
  summary.textContent = `Registered: ${s.registered} · Checked in: ${s.checked_in} · Absent: ${s.absent} · Attendance: ${s.attendance_percentage}%`;
  attendeeList.replaceChildren();
  data.attendees.forEach((attendee) => {
    const row = document.createElement("li"); row.className = "list-group-item d-flex justify-content-between";
    const name = document.createElement("span"); name.textContent = `${attendee.student.name} (${attendee.student.email})`; const status = document.createElement("strong"); status.textContent = attendee.attendance_status;
    row.append(name, status); attendeeList.append(row);
  });
}
async function loadAttendance(session) {
  if (!eventSelect.value) return;
  const response = await fetch(apiUrl(`/api/events/${eventSelect.value}/attendance`), { headers: { Authorization: `Bearer ${session.access_token}` } });
  const body = await response.json(); if (!response.ok) throw new Error(body.error?.message || "Attendance could not be loaded."); renderAttendance(body.data);
}
(async () => {
  try {
    const client = await getSupabaseClient(); const session = (await client.auth.getSession()).data.session;
    if (!session) { redirectToLogin(scannerRole()); return; }
    const events = await fetch(apiUrl("/api/events?limit=100"), { headers: { Authorization: `Bearer ${session.access_token}` } });
    const body = await events.json(); if (!events.ok) throw new Error(body.error?.message || "Events could not be loaded.");
    body.data.forEach((event) => { const option = document.createElement("option"); option.value = event.id; option.textContent = `${event.title} — ${event.event_date}`; eventSelect.append(option); });
    eventSelect.addEventListener("change", () => loadAttendance(session).catch((error) => showScannerMessage(error.message, true)));
    document.querySelector("#startScanner").addEventListener("click", async () => {
      if (qrScanner) return;
      qrScanner = new Html5Qrcode("reader"); showScannerMessage("Camera active. Point it at a student event pass.");
      await qrScanner.start({ facingMode: "environment" }, { fps: 10, qrbox: { width: 250, height: 250 } }, async (decodedText) => {
        if (checkInInProgress) return;
        checkInInProgress = true;
        showScannerMessage("QR detected. Verifying attendance…");
        try {
          const qrPayload = normalizeDecodedPayload(decodedText);
          const response = await fetchWithTimeout(apiUrl("/api/attendance/check-in"), { method: "POST", headers: { "Content-Type": "application/json", Authorization: `Bearer ${session.access_token}` }, body: JSON.stringify({ qr_payload: qrPayload }) });
          const result = await response.json().catch(() => ({}));
          const attendance = result.data;
          if (!response.ok || result.success !== true || !attendance?.attendance_id || attendance.status !== "present") {
            throw new Error(result.error?.message || `Attendance could not be recorded (HTTP ${response.status}).`);
          }
          showScannerMessage("Check-in recorded.");
          try {
            await loadAttendance(session);
          } catch (error) {
            showScannerMessage(`Check-in recorded, but the attendance list could not be refreshed: ${error.message}`, true);
          }
        } catch (error) {
          const message = error.name === "AbortError"
            ? "Attendance verification timed out. Check the connection and try again."
            : (error.message || "Attendance could not be recorded. Please try again.");
          showScannerMessage(message, true);
        } finally {
          checkInInProgress = false;
        }
      });
    });
    document.querySelector("#stopScanner").addEventListener("click", async () => { if (qrScanner) { await qrScanner.stop(); qrScanner.clear(); qrScanner = null; showScannerMessage("Scanner stopped."); } });
  } catch (error) { showScannerMessage(error.message, true); }
})();
