import { useState } from "react";
import { signInWithGoogle } from "../auth/auth-client.js";

function GoogleMark() {
  return <svg aria-hidden="true" viewBox="0 0 24 24" className="h-5 w-5"><path fill="#4285F4" d="M21.35 12.23c0-.71-.06-1.4-.18-2.05H12v3.88h5.24a4.48 4.48 0 0 1-1.94 2.94v2.45h3.14c1.84-1.7 2.91-4.2 2.91-7.22Z" /><path fill="#34A853" d="M12 21.6c2.63 0 4.84-.87 6.45-2.35l-3.14-2.45c-.87.58-1.98.93-3.31.93-2.54 0-4.69-1.72-5.46-4.03H3.3v2.53A9.74 9.74 0 0 0 12 21.6Z" /><path fill="#FBBC05" d="M6.54 13.7A5.85 5.85 0 0 1 6.23 12c0-.59.1-1.17.31-1.7V7.77H3.3A9.73 9.73 0 0 0 2.27 12c0 1.57.38 3.05 1.03 4.23l3.24-2.53Z" /><path fill="#EA4335" d="M12 6.27c1.43 0 2.71.49 3.72 1.45l2.79-2.79C16.84 3.35 14.63 2.4 12 2.4a9.74 9.74 0 0 0-8.7 5.37l3.24 2.53C7.31 7.99 9.46 6.27 12 6.27Z" /></svg>;
}

export function GoogleButton({ returnTo = "/student/", onError }) {
  const [busy, setBusy] = useState(false);
  async function handleClick() {
    if (busy) return;
    setBusy(true);
    try { await signInWithGoogle(returnTo); } catch (error) { setBusy(false); onError?.(error); }
  }
  return <button type="button" onClick={handleClick} disabled={busy} className="inline-flex w-full items-center justify-center gap-3 rounded-xl border border-line bg-white px-4 py-3 font-bold text-ink transition hover:border-electric hover:bg-blue-50 disabled:cursor-wait disabled:opacity-60 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-electric" aria-busy={busy}>{busy ? <span className="h-5 w-5 animate-spin rounded-full border-2 border-slate-300 border-t-electric" aria-hidden="true" /> : <GoogleMark />}<span>{busy ? "Connecting to Google…" : "Continue with Google"}</span></button>;
}
