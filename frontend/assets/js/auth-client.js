let supabaseClientPromise;
const localEventSphereApiBase = "http://127.0.0.1:5000";
const productionEventSphereApiBase = "https://eventspherebackend-azkp.onrender.com";
const localDevelopmentHosts = new Set(["", "localhost", "127.0.0.1"]);
const defaultEventSphereApiBase = localDevelopmentHosts.has(window.location.hostname)
  ? localEventSphereApiBase
  : productionEventSphereApiBase;
const eventSphereApiBase = (window.EVENTSPHERE_API_BASE_URL || defaultEventSphereApiBase).replace(/\/$/, "");
const eventSphereReturnToKey = "eventsphere.returnTo";
const eventSphereRoleHomePaths = { student: "/student/", organizer: "/organizer/", admin: "/admin/" };
function apiUrl(path) { return `${eventSphereApiBase}${path}`; }

function roleHomePath(role) { return eventSphereRoleHomePaths[role] || "/"; }
function dashboardPath(role) { return roleHomePath(role); }
function currentRelativePath() { return `${window.location.pathname}${window.location.search}${window.location.hash}`; }
function isPublicEntryPage() { return ["/", "/index.html", "/login/", "/login/index.html", "/register/", "/register/index.html"].includes(window.location.pathname); }
function homeLinks() {
  return [...document.querySelectorAll("a")].filter((link) => {
    const label = link.textContent.trim().replace(/^←\s*/, "");
    return link.hasAttribute("data-home-link") || label === "EventSphere" || label === "Home" || label === "Dashboard" || /dashboard$/i.test(label);
  });
}
function saveReturnTo(requiredRole) {
  try { sessionStorage.setItem(eventSphereReturnToKey, JSON.stringify({ path: currentRelativePath(), role: requiredRole || null })); } catch (_) { /* Session storage may be unavailable. */ }
}
function consumeAuthorizedReturnTo(role) {
  try {
    const raw = sessionStorage.getItem(eventSphereReturnToKey);
    sessionStorage.removeItem(eventSphereReturnToKey);
    if (!raw) return null;
    const pending = JSON.parse(raw);
    if (!pending || typeof pending.path !== "string" || !pending.path.startsWith("/") || pending.path.startsWith("//")) return null;
    const allowedRoles = Array.isArray(pending.role) ? pending.role : pending.role ? [pending.role] : [];
    if (allowedRoles.length && !allowedRoles.includes(role)) return null;
    return pending.path;
  } catch (_) { return null; }
}
let cachedProfilePromise = null;
let cachedProfileToken = null;

async function verifiedProfile(session) {
  if (!session || !session.access_token) throw new Error("Authenticated session is required.");
  if (cachedProfileToken === session.access_token && cachedProfilePromise) {
    return cachedProfilePromise;
  }
  cachedProfileToken = session.access_token;
  cachedProfilePromise = (async () => {
    const data = await callApi("/api/auth/me", session);
    if (!data.profile?.role) throw new Error("Authenticated role is unavailable.");
    return data.profile;
  })().catch((err) => {
    cachedProfilePromise = null;
    cachedProfileToken = null;
    throw err;
  });
  return cachedProfilePromise;
}
async function wireRoleAwareNavigation() {
  try {
    const client = await getSupabaseClient();
    const session = (await client.auth.getSession()).data.session;
    if (!session) return;
    const profile = await verifiedProfile(session);
    const destination = roleHomePath(profile.role);
    homeLinks().forEach((link) => { link.href = destination; });
    if (isPublicEntryPage()) window.location.replace(consumeAuthorizedReturnTo(profile.role) || destination);
  } catch (_) {
    // Public navigation remains available when auth is unavailable or expired.
  }
}
document.addEventListener("DOMContentLoaded", () => { wireRoleAwareNavigation(); });

async function getSupabaseClient() {
  if (!supabaseClientPromise) {
    supabaseClientPromise = fetch(apiUrl("/api/config"))
      .then((response) => {
        if (!response.ok) throw new Error("Auth configuration unavailable");
        return response.json();
      })
      .then((config) => {
        if (!config.supabaseUrl || !config.supabasePublishableKey) {
          throw new Error("Auth configuration is incomplete");
        }
        return window.supabase.createClient(config.supabaseUrl, config.supabasePublishableKey);
      });
  }
  return supabaseClientPromise;
}

async function callApi(path, session) {
  const response = await fetch(apiUrl(path), {
    headers: { Authorization: `Bearer ${session.access_token}` },
  });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(body.error || "The request could not be completed.");
  return body;
}

function friendlyAuthError(error) {
  const message = (error?.message || "").toLowerCase();
  if (message.includes("invalid login credentials")) return "The email or password is incorrect.";
  if (message.includes("already registered")) return "An account with this email already exists.";
  if (message.includes("password")) return "Please choose a stronger password and try again.";
  if (message.includes("email")) return "Please enter a valid email address.";
  return "Authentication could not be completed. Please try again.";
}

async function redirectByRole(session) {
  const profile = await verifiedProfile(session);
  window.location.replace(consumeAuthorizedReturnTo(profile.role) || roleHomePath(profile.role));
}

async function signOutAndRedirect() {
  try {
    const client = await getSupabaseClient();
    await client.auth.signOut();
  } finally {
    try { sessionStorage.removeItem(eventSphereReturnToKey); } catch (_) { /* Ignore unavailable storage. */ }
    window.location.replace("/");
  }
}
