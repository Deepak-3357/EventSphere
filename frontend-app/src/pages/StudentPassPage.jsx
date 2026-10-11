import { CheckCircle2, KeyRound, LoaderCircle } from "lucide-react";
import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { requestJson } from "../api/client.js";
import { useAuth } from "../auth/AuthProvider.jsx";
import { SiteHeader } from "../components/SiteHeader.jsx";

export function StudentPassPage() {
  const { session, loading: authLoading } = useAuth();
  const [params] = useSearchParams();
  const [state, setState] = useState({ loading: true, pass: null, error: "" });
  useEffect(() => {
    if (authLoading) return;
    const registrationId = params.get("registration_id");
    if (!session) return setState({ loading: false, pass: null, error: "Please sign in to view this event pass." });
    if (!registrationId) return setState({ loading: false, pass: null, error: "A registration is required." });
    requestJson(`/api/registrations/${encodeURIComponent(registrationId)}/pass`, { headers: { Authorization: `Bearer ${session.access_token}` } }).then((body) => setState({ loading: false, pass: body.data, error: "" })).catch((error) => setState({ loading: false, pass: null, error: error.message }));
  }, [authLoading, params, session]);
  return <div className="min-h-screen bg-mist"><SiteHeader /><main className="mx-auto max-w-4xl px-6 py-12">{state.loading && <div className="grid place-items-center py-24"><LoaderCircle className="animate-spin text-electric" /></div>}{state.error && <div className="rounded-2xl bg-red-50 p-5 text-red-800" role="alert">{state.error}</div>}{state.pass && <article className="rounded-3xl border border-line bg-white p-6 shadow-soft md:p-10"><p className="text-sm font-bold uppercase tracking-[0.18em] text-electric">Event pass</p><h1 className="mt-2 text-4xl font-black text-ink">{state.pass.event.title}</h1><p className="mt-3 text-slate-500">{state.pass.event.event_date} · {state.pass.event.start_time}–{state.pass.event.end_time} · {state.pass.event.venue.name}</p><div className="mt-8 grid gap-8 md:grid-cols-[280px_1fr] md:items-center"><img className="h-[280px] w-[280px] rounded-2xl border border-line p-2" src={state.pass.qr_image} alt="Signed EventSphere attendance QR code" /><div><div className="rounded-2xl bg-blue-50 p-5"><p className="flex items-center gap-2 text-sm font-bold text-electric"><KeyRound size={17} /> Six-digit attendance code</p><p className="mt-3 font-mono text-4xl font-black tracking-[0.3em] text-ink">{state.pass.attendance_code}</p><p className="mt-3 text-sm text-slate-600">Show this code or the signed QR pass to the organizer.</p></div><p className="mt-5 flex items-center gap-2 text-sm font-bold text-emerald-700"><CheckCircle2 size={17} /> Pass status: {state.pass.attendance.status}</p></div></div></article>}</main></div>;
}
