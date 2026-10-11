import { createClient } from "@supabase/supabase-js";
import { apiUrl, requestJson } from "../api/client.js";
import { roleHomePath } from "./rolePolicy.js";

let clientPromise;
export const oauthReturnKey = "eventsphere.oauthReturnTo";

const allowedStudentReturnPrefixes = ["/student/", "/events/", "/notifications/"];

export function safeStudentReturnTo(value) {
  if (typeof value !== "string" || !value.startsWith("/") || value.startsWith("//") || value.includes("\\")) return null;
  if (value === "/student/" || allowedStudentReturnPrefixes.some((prefix) => value.startsWith(prefix))) return value;
  return null;
}

export function rememberOAuthReturnTo(value) {
  const safePath = safeStudentReturnTo(value) || "/student/";
  try { sessionStorage.setItem(oauthReturnKey, safePath); } catch (_) { /* Storage may be unavailable. */ }
  return safePath;
}

export function consumeOAuthReturnTo() {
  try {
    const value = sessionStorage.getItem(oauthReturnKey);
    sessionStorage.removeItem(oauthReturnKey);
    return safeStudentReturnTo(value) || "/student/";
  } catch (_) { return "/student/"; }
}

export function getSupabaseClient() {
  if (!clientPromise) {
    clientPromise = fetch(apiUrl("/api/config"))
      .then((response) => {
        if (!response.ok) throw new Error("Auth configuration unavailable");
        return response.json();
      })
      .then((config) => {
        if (!config.supabaseUrl || !config.supabasePublishableKey) throw new Error("Auth configuration is incomplete");
        return createClient(config.supabaseUrl, config.supabasePublishableKey);
      });
  }
  return clientPromise;
}

export async function getVerifiedIdentity() {
  const client = await getSupabaseClient();
  const { data } = await client.auth.getSession();
  if (!data.session) return { session: null, profile: null };
  const body = await requestJson("/api/auth/me", { headers: { Authorization: `Bearer ${data.session.access_token}` } });
  return { session: data.session, profile: body.profile || null };
}

export async function signInWithGoogle(returnTo = "/student/") {
  rememberOAuthReturnTo(returnTo);
  const client = await getSupabaseClient();
  const { error } = await client.auth.signInWithOAuth({
    provider: "google",
    options: { redirectTo: `${window.location.origin}/auth/callback/` },
  });
  if (error) {
    try { sessionStorage.removeItem(oauthReturnKey); } catch (_) { /* Ignore unavailable storage. */ }
    throw error;
  }
}

export async function signOut() {
  const client = await getSupabaseClient();
  await client.auth.signOut();
  try { sessionStorage.removeItem(oauthReturnKey); } catch (_) { /* Ignore unavailable storage. */ }
}

export async function redirectByVerifiedRole(session) {
  const body = await requestJson("/api/auth/me", { headers: { Authorization: `Bearer ${session.access_token}` } });
  if (!body.profile?.role) throw new Error("Your verified EventSphere profile is unavailable.");
  const destination = body.profile.role === "student" ? consumeOAuthReturnTo() : roleHomePath(body.profile.role);
  window.location.replace(destination);
}
