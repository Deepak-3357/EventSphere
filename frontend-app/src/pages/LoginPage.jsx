import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { AuthNotice, AuthShell } from "../components/AuthShell.jsx";
import { GoogleButton } from "../components/GoogleButton.jsx";
import { getSupabaseClient, redirectByVerifiedRole, rememberOAuthReturnTo, safeStudentReturnTo } from "../auth/auth-client.js";

function friendlyError(error) {
  const message = (error?.message || "").toLowerCase();
  if (message.includes("invalid login credentials")) return "The email or password is incorrect.";
  if (message.includes("provider") || message.includes("google")) return "Google sign-in is not available yet. Please use email and password or contact support.";
  if (message.includes("network") || message.includes("fetch")) return "The authentication service is unavailable. Check your connection and try again.";
  return error?.message || "Sign-in could not be completed. Please try again.";
}

export function LoginPage() {
  const [params] = useSearchParams();
  const returnTo = safeStudentReturnTo(params.get("returnTo")) || "/student/";
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function submit(event) {
    event.preventDefault(); if (busy) return; setBusy(true); setError("");
    const form = event.currentTarget; const email = form.elements.namedItem("email").value.trim(); const password = form.elements.namedItem("password").value;
    try { rememberOAuthReturnTo(returnTo); const client = await getSupabaseClient(); const { data, error: signInError } = await client.auth.signInWithPassword({ email, password }); if (signInError) throw signInError; await redirectByVerifiedRole(data.session); } catch (exception) { setError(friendlyError(exception)); setBusy(false); }
  }
  return <AuthShell title="Welcome back" subtitle="Sign in to discover events, manage your registrations, and access your student pass." footer={<>New to EventSphere? <Link className="font-bold text-electric" to={`/register/?returnTo=${encodeURIComponent(returnTo)}`}>Create a student account</Link>.</>}><div className="rounded-2xl border border-blue-100 bg-blue-50 p-4 text-sm text-blue-900">Google sign-in is available for student accounts only. Organizers and administrators should use their authorized email/password account.</div><div className="mt-6"><GoogleButton returnTo={returnTo} onError={(exception) => setError(friendlyError(exception))} /></div><div className="my-6 flex items-center gap-3 text-xs font-bold uppercase tracking-[0.16em] text-slate-400"><span className="h-px flex-1 bg-line" />or<span className="h-px flex-1 bg-line" /></div><form onSubmit={submit} className="space-y-4"><div><label className="text-sm font-bold text-ink" htmlFor="login-email">Email</label><input id="login-email" name="email" type="email" autoComplete="email" required className="mt-2 w-full rounded-xl border border-line px-4 py-3 outline-none focus:border-electric focus:ring-2 focus:ring-electric/20" /></div><div><label className="text-sm font-bold text-ink" htmlFor="login-password">Password</label><input id="login-password" name="password" type="password" autoComplete="current-password" required className="mt-2 w-full rounded-xl border border-line px-4 py-3 outline-none focus:border-electric focus:ring-2 focus:ring-electric/20" /></div><AuthNotice error={error} /><button className="w-full rounded-xl bg-ink px-4 py-3 font-bold text-white transition hover:bg-electric disabled:opacity-60" disabled={busy} type="submit">{busy ? "Signing in…" : "Sign in with email"}</button></form></AuthShell>;
}
