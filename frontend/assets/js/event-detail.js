const detailElement = document.querySelector("#eventDetail");
const eventId = new URLSearchParams(window.location.search).get("id");

function detailEscape(value) {
  return String(value ?? "").replace(/[&<>'"]/g, (character) => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;"}[character]));
}

async function loadEvent() {
  if (!eventId) throw new Error("An event ID is required.");
  let session = null;
  let client = null;
  try {
    client = await getSupabaseClient();
    session = (await client.auth.getSession()).data.session;
  } catch (_) {
    // Public event details remain available if Auth configuration is unavailable.
  }
  const headers = session ? { Authorization: `Bearer ${session.access_token}` } : {};
  const response = await fetch(apiUrl(`/api/events/${encodeURIComponent(eventId)}`), { headers });
  const body = await response.json();
  if (!response.ok) throw new Error(body.error?.message || "Event could not be loaded.");
  const event = body.data;
  const open = event.status === "published" && event.available_seats > 0 && new Date(event.registration_deadline) > new Date();
  detailElement.innerHTML = `<div class="card border-0 shadow-sm"><div class="card-body p-4 p-lg-5">
    <span class="badge text-bg-primary mb-3">${detailEscape(event.category.name)}</span>
    <h1 class="h2">${detailEscape(event.title)}</h1>
    <p class="text-secondary">${detailEscape(event.description)}</p>
    <div class="row g-3 small mb-4"><div class="col-md-6"><strong>Date:</strong> ${detailEscape(event.event_date)} ${detailEscape(event.start_time)}–${detailEscape(event.end_time)}</div><div class="col-md-6"><strong>Venue:</strong> ${detailEscape(event.venue.name)}</div><div class="col-md-6"><strong>Seats:</strong> ${event.available_seats} available of ${event.capacity}</div><div class="col-md-6"><strong>Deadline:</strong> ${detailEscape(event.registration_deadline)}</div></div>
    <div id="registrationState" class="mb-3"></div>
    <button class="btn btn-primary" id="registerButton" ${open ? "" : "disabled"}>Register</button>
    <p class="small text-secondary mt-3 mb-0">${open ? "Registration Open" : event.available_seats === 0 ? "Event Full" : "Registration Closed"}</p>
  </div></div>`;
  const state = document.querySelector("#registrationState");
  const button = document.querySelector("#registerButton");
  if (!session) {
    button.textContent = "Sign in to register";
    button.disabled = false;
    button.onclick = () => { window.location.href = "../login/"; };
    return;
  }
  if (event.is_registered) {
    state.innerHTML = '<span class="badge text-bg-success">Registered ✓</span>';
    button.textContent = "Cancel registration";
    button.className = "btn btn-outline-danger";
    button.disabled = false;
    button.onclick = () => updateRegistration("DELETE", session, button, state);
  } else {
    button.onclick = () => updateRegistration("POST", session, button, state);
  }
}

async function updateRegistration(method, session, button, state) {
  button.disabled = true;
  button.textContent = "Please wait…";
  const response = await fetch(apiUrl(`/api/events/${encodeURIComponent(eventId)}/register`), { method, headers: { Authorization: `Bearer ${session.access_token}` } });
  const body = await response.json();
  if (!response.ok) {
    state.innerHTML = `<span class="text-danger">${detailEscape(body.error?.message || "Registration could not be completed.")}</span>`;
    button.disabled = false;
    button.textContent = method === "POST" ? "Register" : "Cancel registration";
    return;
  }
  state.innerHTML = `<span class="badge text-bg-${method === "POST" ? "success" : "secondary"}">${method === "POST" ? "Registered ✓" : "Registration Cancelled"}</span>`;
  button.textContent = method === "POST" ? "Cancel registration" : "Register again";
  button.className = method === "POST" ? "btn btn-outline-danger" : "btn btn-primary";
  button.disabled = false;
  button.onclick = () => updateRegistration(method === "POST" ? "DELETE" : "POST", session, button, state);
}

loadEvent().catch((error) => { detailElement.innerHTML = `<div class="alert alert-danger">${detailEscape(error.message)}</div>`; });
