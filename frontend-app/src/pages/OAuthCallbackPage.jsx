import { AlertTriangle, LoaderCircle } from "lucide-react";
import { useEffect, useState } from "react";
import { getVerifiedIdentity, consumeOAuthReturnTo, signOut } from "../auth/auth-client.js";
import { AuthShell } from "../components/AuthShell.jsx";

export function OAuthCallbackPage() {
  const [error, setError] = useState("");
  useEffect(() => {
    let active = true;
    const params = new URLSearchParams(window.location.search);
    const providerError = params.get("error_description") || params.get("error");
    if (providerError) { setError("Google sign-in was cancelled or could not be completed. Please try again."); return undefined; }
    getVerifiedIdentity().then(async ({ session, profile }) => {
      if (!active) return;
      if (!session) throw new Error("No authenticated session was returned by Google.");
      if (!profile) throw new Error("Your EventSphere student profile is not available yet. Please contact support.");
      if (profile.role !== "student") { await signOut(); throw new Error("Google sign-in is only available for student accounts. Use your authorized email/password login for this account."); }
      window.location.replace(consumeOAuthReturnTo());
    }).catch((exception) => active && setError(exception.message || "Google sign-in could not be completed."));
    return () => { active = false; };
  }, []);
  return <AuthShell title={error ? "Sign-in needs attention" : "Finishing sign-in"} subtitle={error ? "No changes were made to your account or role." : "Verifying your EventSphere student session securely."} footer={error ? "You can return to the student sign-in page and try again." : "Please wait a moment."}>{error ? <div className="rounded-2xl bg-red-50 p-5 text-red-800" role="alert"><AlertTriangle className="mb-3" />{error}<a className="mt-5 block font-bold text-electric" href="/login/">Return to student sign-in</a></div> : <div className="grid place-items-center rounded-2xl border border-line bg-white p-10"><LoaderCircle className="animate-spin text-electric" aria-label="Verifying session" /></div>}</AuthShell>;
}
