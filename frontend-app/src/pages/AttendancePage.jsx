import { AlertCircle, Camera, CheckCircle2, KeyRound, LoaderCircle, RefreshCw, ScanLine, StopCircle } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { requestJson } from "../api/client.js";
import { useAuth } from "../auth/AuthProvider.jsx";
import { roleHomePath } from "../auth/rolePolicy.js";
import { SiteHeader } from "../components/SiteHeader.jsx";

function authOptions(session, options = {}) {
  return { ...options, headers: { ...(options.headers || {}), Authorization: `Bearer ${session.access_token}` } };
}

function normalizeQr(value) {
  let candidate = String(value || "").trim();
  try {
    let payload = JSON.parse(candidate);
    if (typeof payload === "string") { candidate = payload.trim(); payload = JSON.parse(candidate); }
    if (!payload || Array.isArray(payload) || payload.type !== "eventsphere_attendance" || typeof payload.registration_id !== "string" || typeof payload.token !== "string") throw new Error();
    return candidate;
  } catch { throw new Error("The scanned QR code is not a valid EventSphere attendance pass."); }
}

export function AttendancePage() {
  const { session, profile, loading: authLoading } = useAuth();
  const [events, setEvents] = useState([]);
  const [eventId, setEventId] = useState("");
  const [summary, setSummary] = useState(null);
  const [mode, setMode] = useState("scan");
  const [code, setCode] = useState("");
  const [message, setMessage] = useState({ text: "", error: false, success: false });
  const [busy, setBusy] = useState(false);
  const scannerRef = useRef(null);
  const readerId = "eventsphere-react-reader";

  const refresh = useCallback(async () => {
    if (!session || !eventId) return;
    const body = await requestJson(`/api/events/${eventId}/attendance`, authOptions(session));
    setSummary(body.data);
  }, [eventId, session]);

  useEffect(() => {
    if (!session || !profile || !["organizer", "admin"].includes(profile.role)) return;
    requestJson("/api/events?limit=100", authOptions(session)).then((body) => setEvents(body.data || [])).catch((error) => setMessage({ text: error.message, error: true, success: false }));
  }, [profile, session]);

  useEffect(() => { refresh().catch((error) => setMessage({ text: error.message, error: true, success: false })); }, [refresh]);

  useEffect(() => () => { scannerRef.current?.stop().catch(() => {}); }, []);

  const record = useCallback(async (payload) => {
    if (!session || !eventId || busy) return;
    setBusy(true); setMessage({ text: "Verifying attendance…", error: false, success: false });
    try {
      const body = await requestJson("/api/attendance/check-in", authOptions(session, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ qr_payload: payload }) }));
      if (body.success !== true || body.data?.status !== "present" || !body.data?.attendance_id) throw new Error("The backend did not confirm attendance.");
      setMessage({ text: `Attendance marked for ${body.data.student_name || "the attendee"} at ${body.data.event_title || "this event"}.`, error: false, success: true });
      try { await refresh(); } catch (error) { setMessage({ text: `Attendance marked, but the summary could not refresh: ${error.message}`, error: true, success: true }); }
    } catch (error) { setMessage({ text: error.message || "Attendance could not be recorded. Please try again.", error: true, success: false }); }
    finally { setBusy(false); }
  }, [busy, eventId, refresh, session]);

  async function startScanner() {
    if (!eventId || busy || scannerRef.current) return setMessage({ text: "Select an event before starting the scanner.", error: true, success: false });
    const { Html5Qrcode } = await import("html5-qrcode");
    const scanner = new Html5Qrcode(readerId); scannerRef.current = scanner;
    setMessage({ text: "Camera active. Point it at a student event pass.", error: false, success: false });
    try { await scanner.start({ facingMode: "environment" }, { fps: 10, qrbox: { width: 250, height: 250 } }, async (value) => { if (busy) return; try { await record(normalizeQr(value)); } catch (error) { setMessage({ text: error.message, error: true, success: false }); } }); }
    catch (error) { scannerRef.current = null; setMessage({ text: error.message || "The camera could not be started.", error: true, success: false }); }
  }

  async function stopScanner() { if (scannerRef.current) { await scannerRef.current.stop().catch(() => {}); scannerRef.current.clear(); scannerRef.current = null; setMessage({ text: "Scanner stopped.", error: false, success: false }); } }

  async function submitCode(event) {
    event.preventDefault();
    if (!/^\d{6}$/.test(code)) return setMessage({ text: "Enter exactly six digits, including any leading zeroes.", error: true, success: false });
    if (!session || !eventId || busy) return;
    setBusy(true); setMessage({ text: "Verifying attendance…", error: false, success: false });
    try {
      const body = await requestJson("/api/attendance/manual-check-in", authOptions(session, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ event_id: eventId, code }) }));
      if (body.success !== true || body.data?.status !== "present" || !body.data?.attendance_id) throw new Error("The backend did not confirm attendance.");
      setCode(""); setMessage({ text: `Attendance marked for ${body.data.student_name || "the attendee"} at ${body.data.event_title || "this event"}.`, error: false, success: true });
      try { await refresh(); } catch (error) { setMessage({ text: `Attendance marked, but the summary could not refresh: ${error.message}`, error: true, success: true }); }
    } catch (error) { setMessage({ text: error.message || "Attendance could not be recorded. Please try again.", error: true, success: false }); }
    finally { setBusy(false); }
  }

  if (authLoading) return <div className="grid min-h-screen place-items-center bg-mist"><LoaderCircle className="animate-spin text-electric" /></div>;
  if (!session || !profile || !["organizer", "admin"].includes(profile.role)) return <main className="mx-auto max-w-2xl px-6 py-24 text-center"><AlertCircle className="mx-auto text-red-600" /><h1 className="mt-4 text-2xl font-black text-ink">Attendance access is restricted</h1><a className="mt-5 inline-block font-bold text-electric" href={roleHomePath(profile?.role)}>Return to dashboard</a></main>;

  return <div className="min-h-screen bg-mist"><SiteHeader /><main className="mx-auto max-w-6xl px-6 py-12"><div className="mb-8"><p className="text-sm font-bold uppercase tracking-[0.18em] text-electric">Organizer tools</p><h1 className="mt-2 text-4xl font-black text-ink">Mark attendance</h1><p className="mt-3 text-slate-500">Confirm attendance with a signed QR pass or a student’s event-specific code.</p></div><section className="rounded-3xl border border-line bg-white p-6 shadow-soft"><label className="text-sm font-bold text-ink" htmlFor="attendance-event">Event</label><select id="attendance-event" className="mt-2 w-full rounded-xl border border-line bg-white px-4 py-3 text-ink outline-none focus:border-electric focus:ring-2 focus:ring-electric/20" value={eventId} onChange={(event) => setEventId(event.target.value)}><option value="">Select an event</option>{events.map((event) => <option key={event.id} value={event.id}>{event.title} — {event.event_date}</option>)}</select><div className="mt-6 flex gap-2 border-b border-line" role="tablist" aria-label="Attendance method"><button role="tab" aria-selected={mode === "scan"} className={`inline-flex items-center gap-2 border-b-2 px-4 py-3 text-sm font-bold ${mode === "scan" ? "border-electric text-electric" : "border-transparent text-slate-500"}`} onClick={() => setMode("scan")}><ScanLine size={17} />Scan QR</button><button role="tab" aria-selected={mode === "code"} className={`inline-flex items-center gap-2 border-b-2 px-4 py-3 text-sm font-bold ${mode === "code" ? "border-electric text-electric" : "border-transparent text-slate-500"}`} onClick={() => setMode("code")}><KeyRound size={17} />Enter code</button></div>{mode === "scan" ? <div className="pt-6"><div id={readerId} className="mx-auto min-h-10 max-w-md overflow-hidden rounded-2xl bg-ink" /><div className="mt-4 flex gap-3"><button className="inline-flex items-center gap-2 rounded-full bg-electric px-5 py-3 font-bold text-white disabled:opacity-50" onClick={startScanner} disabled={!eventId || busy}><Camera size={18} />Start scanner</button><button className="inline-flex items-center gap-2 rounded-full border border-line px-5 py-3 font-bold text-ink" onClick={stopScanner}><StopCircle size={18} />Stop</button></div></div> : <form className="max-w-md pt-6" onSubmit={submitCode}><label className="text-sm font-bold text-ink" htmlFor="attendance-code">Six-digit code</label><input id="attendance-code" className="mt-2 w-full rounded-xl border border-line px-4 py-3 font-mono text-2xl tracking-[0.35em] outline-none focus:border-electric focus:ring-2 focus:ring-electric/20" inputMode="numeric" pattern="[0-9]{6}" maxLength={6} value={code} onChange={(event) => setCode(event.target.value.replace(/\D/g, "").slice(0, 6))} placeholder="004281" aria-describedby="code-help" /><p id="code-help" className="mt-2 text-sm text-slate-500">Leading zeroes are valid. The code only works for the selected event.</p><button className="mt-5 inline-flex items-center gap-2 rounded-full bg-electric px-5 py-3 font-bold text-white disabled:opacity-50" disabled={!eventId || busy} type="submit">{busy ? <LoaderCircle className="animate-spin" size={18} /> : <KeyRound size={18} />}Verify code</button></form>}{message.text && <div className={`mt-6 flex items-start gap-3 rounded-2xl p-4 text-sm ${message.error && !message.success ? "bg-red-50 text-red-800" : "bg-emerald-50 text-emerald-800"}`} role="status">{message.success && !message.error ? <CheckCircle2 size={18} /> : <AlertCircle size={18} />}<span>{message.text}</span></div>}</section>{summary && <section className="mt-6 rounded-3xl border border-line bg-white p-6 shadow-soft"><div className="flex items-center justify-between"><h2 className="text-xl font-black text-ink">Attendance summary</h2><button className="rounded-full p-2 text-slate-500 hover:bg-mist" onClick={() => refresh().catch((error) => setMessage({ text: error.message, error: true, success: false }))} aria-label="Refresh attendance summary"><RefreshCw size={18} /></button></div><p className="mt-3 text-slate-600">Registered: {summary.summary.registered} · Checked in: {summary.summary.checked_in} · Absent: {summary.summary.absent} · Attendance: {summary.summary.attendance_percentage}%</p></section>}</main></div>;
}
