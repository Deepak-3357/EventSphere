export const localApiBase = "http://127.0.0.1:5000";
export const productionApiBase = "https://eventspherebackend-azkp.onrender.com";

export function resolveApiBase(hostname = typeof window !== "undefined" ? window.location.hostname : "") {
  return ["", "localhost", "127.0.0.1"].includes(hostname) ? localApiBase : productionApiBase;
}

export const apiBase = (import.meta.env.VITE_API_BASE_URL || resolveApiBase()).replace(/\/$/, "");

export function apiUrl(path) {
  return `${apiBase}${path}`;
}

export async function requestJson(path, options = {}) {
  const response = await fetch(apiUrl(path), {
    ...options,
    headers: { Accept: "application/json", ...(options.headers || {}) },
  });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    const message = body?.error?.message || "The request could not be completed.";
    const error = new Error(message);
    error.status = response.status;
    error.code = body?.error?.code;
    throw error;
  }
  return body;
}

export async function getCatalog() {
  const [events, categories, venues] = await Promise.all([
    requestJson("/api/events?limit=100"),
    requestJson("/api/categories"),
    requestJson("/api/venues"),
  ]);
  return {
    events: Array.isArray(events.data) ? events.data : [],
    categories: Array.isArray(categories.data) ? categories.data : [],
    venues: Array.isArray(venues.data) ? venues.data : [],
    pagination: events.pagination || null,
  };
}
