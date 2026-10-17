const scannerMessage = document.querySelector("#scannerMessage");
const eventSelect = document.querySelector("#eventSelect");
const summary = document.querySelector("#attendanceSummary");
const attendeeList = document.querySelector("#attendeeList");
let qrScanner;
let checkInInProgress = false;
let lastScannedPayload = null;
let lastScannedAt = 0;

function scannerRole() { return window.location.pathname.includes("/admin/") ? "admin" : "organizer"; }
function showScannerMessage(message, danger = false) {
  scannerMessage.className = `scanner-message small mt-3 ${danger ? "text-danger" : "text-success"}`;
  scannerMessage.dataset.state = danger ? "error" : (message.toLowerCase().includes("verifying") ? "pending" : "success");
  scannerMessage.textContent = message;
}
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
let getAuthToken = () => "";
async function loadAttendance(session) {
  if (!eventSelect.value) return;
  const token = (await getAuthToken()) || session?.access_token;
  const response = await fetch(apiUrl(`/api/events/${eventSelect.value}/attendance`), { headers: { Authorization: `Bearer ${token}` } });
  if (response.status === 401) { redirectToLogin(scannerRole()); return; }
  const body = await response.json(); if (!response.ok) throw new Error(body.error?.message || "Attendance could not be loaded."); renderAttendance(body.data);
}
async function clearScanner() {
  const activeScanner = qrScanner;
  qrScanner = null;
  if (!activeScanner) return;
  try { await activeScanner.stop(); } catch (_) { /* The camera may already have stopped. */ }
  try { activeScanner.clear(); } catch (_) { /* The reader may already be empty. */ }
}
(async () => {
  try {
    const client = await getSupabaseClient(); const session = (await client.auth.getSession()).data.session;
    if (!session) { redirectToLogin(scannerRole()); return; }
    getAuthToken = async () => {
      try {
        const { data } = await client.auth.getSession();
        if (data?.session?.access_token) return data.session.access_token;
      } catch (_) {}
      return session?.access_token || "";
    };
    const events = await fetch(apiUrl("/api/events?limit=100"), { headers: { Authorization: `Bearer ${session.access_token}` } });
    if (events.status === 401) { redirectToLogin(scannerRole()); return; }
    const body = await events.json(); if (!events.ok) throw new Error(body.error?.message || "Events could not be loaded.");
    body.data.forEach((event) => { const option = document.createElement("option"); option.value = event.id; option.textContent = `${event.title} — ${event.event_date}`; eventSelect.append(option); });
    eventSelect.addEventListener("change", () => loadAttendance(session).catch((error) => showScannerMessage(error.message, true)));
    document.querySelector("#startScanner").addEventListener("click", async () => {
      if (qrScanner) return;
      if (!eventSelect.value) {
        showScannerMessage("Select an event before starting the scanner.", true);
        return;
      }
      const activeScanner = new Html5Qrcode("reader"); qrScanner = activeScanner;
      showScannerMessage("Camera active. Point it at a student event pass.");
      try { await activeScanner.start({ facingMode: "environment" }, { fps: 10, qrbox: { width: 250, height: 250 } }, async (decodedText) => {
        if (checkInInProgress) return;
        let qrPayload;
        try {
          qrPayload = normalizeDecodedPayload(decodedText);
        } catch (err) {
          showScannerMessage(err.message, true);
          return;
        }
        if (qrPayload === lastScannedPayload && Date.now() - lastScannedAt < 4000) {
          return;
        }
        lastScannedPayload = qrPayload;
        lastScannedAt = Date.now();
        checkInInProgress = true;
        showScannerMessage("QR detected. Verifying attendance…");
        try {
          const checkInUrl = eventSelect.value ? apiUrl(`/api/attendance/check-in?event_id=${encodeURIComponent(eventSelect.value)}`) : apiUrl("/api/attendance/check-in");
          const token = (await getAuthToken()) || session.access_token;
          const response = await fetchWithTimeout(checkInUrl, { method: "POST", headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` }, body: JSON.stringify({ qr_payload: qrPayload }) });
          if (response.status === 401) { redirectToLogin(scannerRole()); return; }
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
      }); } catch (error) {
        await clearScanner();
        let errorMsg = error?.message || "";
        if (error?.name === "NotAllowedError" || errorMsg.toLowerCase().includes("permission")) {
          errorMsg = "Camera access denied. Please grant camera permission in your browser.";
        } else if (error?.name === "NotFoundError" || errorMsg.toLowerCase().includes("not found")) {
          errorMsg = "No camera found on this device.";
        } else if (!errorMsg) {
          errorMsg = "The camera could not be started. Check camera permissions and try again.";
        }
        showScannerMessage(errorMsg, true);
      }
    });
    document.querySelector("#stopScanner").addEventListener("click", async () => { await clearScanner(); showScannerMessage("Scanner stopped."); });
    document.querySelector("#manualCodeForm").addEventListener("submit", async (event) => {
      event.preventDefault();
      if (checkInInProgress) return;
      const code = document.querySelector("#attendanceCode").value.trim();
      if (!eventSelect.value) { showScannerMessage("Select an event before verifying an attendance code.", true); return; }
      if (!/^\d{6}$/.test(code)) { showScannerMessage("Enter the six-digit attendance code from the event pass.", true); return; }
      checkInInProgress = true;
      showScannerMessage("Attendance code detected. Verifying attendance…");
      try {
        const token = (await getAuthToken()) || session.access_token;
        const response = await fetchWithTimeout(apiUrl("/api/attendance/manual-check-in"), { method: "POST", headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` }, body: JSON.stringify({ event_id: eventSelect.value, code }) });
        if (response.status === 401) { redirectToLogin(scannerRole()); return; }
        const result = await response.json().catch(() => ({}));
        const attendance = result.data;
        if (!response.ok || result.success !== true || !attendance?.attendance_id || attendance.status !== "present") throw new Error(result.error?.message || `Attendance could not be recorded (HTTP ${response.status}).`);
        document.querySelector("#attendanceCode").value = "";
        showScannerMessage("Check-in recorded.");
        try { await loadAttendance(session); } catch (error) { showScannerMessage(`Check-in recorded, but the attendance list could not be refreshed: ${error.message}`, true); }
      } catch (error) {
        const message = error.name === "AbortError" ? "Attendance verification timed out. Check the connection and try again." : (error.message || "Attendance could not be recorded. Please try again.");
        showScannerMessage(message, true);
      } finally { checkInInProgress = false; }
    });
  } catch (error) { showScannerMessage(error.message, true); }
})();
