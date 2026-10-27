const registrationMessage = document.querySelector("#registrationMessage");
const registrationList = document.querySelector("#registrationList");

function registrationEscape(value) {
  return String(value ?? "").replace(/[&<>'"]/g, (character) => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;"}[character]));
}

(async () => {
  try {
    const client = await getSupabaseClient();
    const session = (await client.auth.getSession()).data.session;
    if (!session) { redirectToLogin("student"); return; }
    const response = await fetch(apiUrl("/api/my-registrations"), { headers: { Authorization: `Bearer ${session.access_token}` } });
    const body = await response.json();
    if (!response.ok) throw new Error(body.error?.message || "Registrations could not be loaded.");
    registrationMessage.textContent = `${body.data.length} registration${body.data.length === 1 ? "" : "s"}`;
    registrationList.innerHTML = body.data.map((registration) => `<div class="col-lg-6"><article class="card border-0 shadow-sm"><div class="card-body"><span class="badge text-bg-${registration.status === "registered" ? "success" : "secondary"}">${registrationEscape(registration.status)}</span><h2 class="h5 mt-2">${registrationEscape(registration.event.title)}</h2><p class="small text-secondary mb-2">${registrationEscape(registration.event.event_date)}</p><p class="small text-secondary mb-3">Registered: ${registrationEscape(registration.registered_at)}</p>${registration.status === "registered" ? `<a class="btn btn-primary btn-sm me-2" href="../event-pass/?registration_id=${encodeURIComponent(registration.registration_id)}">View event pass</a><a class="btn btn-outline-primary btn-sm me-2" href="../od-letters/?registration_id=${encodeURIComponent(registration.registration_id)}">Generate OD letter</a><button class="btn btn-outline-danger btn-sm" data-event-id="${registrationEscape(registration.event.id)}">Cancel registration</button>` : ""}</div></article></div>`).join("");
    registrationList.querySelectorAll("button[data-event-id]").forEach((button) => button.addEventListener("click", async () => {
      button.disabled = true;
      const cancel = await fetch(apiUrl(`/api/events/${button.dataset.eventId}/register`), { method: "DELETE", headers: { Authorization: `Bearer ${session.access_token}` } });
      if (cancel.ok) window.location.reload(); else { button.disabled = false; registrationMessage.textContent = "Cancellation could not be completed."; }
    }));
  } catch (error) { registrationMessage.className = "small text-danger mt-3"; registrationMessage.textContent = error.message; }
})();
