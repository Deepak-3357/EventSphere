let supabaseClientPromise;
const eventSphereApiBase = (window.EVENTSPHERE_API_BASE_URL || "http://127.0.0.1:5000").replace(/\/$/, "");
function apiUrl(path) { return `${eventSphereApiBase}${path}`; }

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
  const data = await callApi("/api/auth/me", session);
  const role = data.profile.role;
  const destinations = {
    student: "/dashboard/student/",
    organizer: "/dashboard/organizer/",
    admin: "/dashboard/admin/",
  };
  window.location.href = destinations[role] || "/login/";
}
