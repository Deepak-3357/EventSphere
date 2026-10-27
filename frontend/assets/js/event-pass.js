const passMessage = document.querySelector("#passMessage");
const passCard = document.querySelector("#passCard");
const retryPass = document.querySelector("#retryPass");
const passEndpoint = () => "/api/registrations/{registration_id}/pass";

function showPassError(message) {
  passMessage.className = "small text-danger mt-3";
  passMessage.textContent = message;
  retryPass.classList.remove("d-none");
}

function logPassFailure(status) {
  if (["", "localhost", "127.0.0.1"].includes(window.location.hostname)) {
    console.warn("Event pass request failed", { status, endpoint: passEndpoint() });
  }
}

function responseError(status) {
  if (status === 401) return "Your session has expired. Please sign in again.";
  if (status === 403) return "You are not authorized to view this event pass.";
  if (status === 404) return "This registration could not be found.";
  if (status === 409) return "This event pass is no longer available for the registration.";
  if (status >= 500) return "The event pass service is temporarily unavailable. Please try again.";
  return "Event pass could not be loaded. Please try again.";
}

retryPass.addEventListener("click", () => window.location.reload());

(async () => {
  try {
    const registrationId = new URLSearchParams(window.location.search).get("registration_id");
    if (!registrationId) throw new Error("A registration is required.");
    if (!/^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(registrationId)) throw new Error("The registration link is invalid.");
    const client = await getSupabaseClient();
    const session = (await client.auth.getSession()).data.session;
    if (!session) { redirectToLogin("student"); return; }
    const response = await fetch(apiUrl(`/api/registrations/${encodeURIComponent(registrationId)}/pass`), { headers: { Authorization: `Bearer ${session.access_token}` } });
    const body = await response.json().catch(() => ({}));
    if (!response.ok) { logPassFailure(response.status); throw new Error(responseError(response.status)); }
    if (body.success !== true) throw new Error("The event pass response was invalid. Please try again.");
    const pass = body.data;
    if (!pass || typeof pass !== "object" || !pass.event || !pass.student) {
      throw new Error("The event pass data is incomplete. Please refresh and try again.");
    }
    document.querySelector("#eventTitle").textContent = pass.event.title;
    document.querySelector("#eventDetails").textContent = `${pass.event.event_date} · ${pass.event.start_time}–${pass.event.end_time}`;
    document.querySelector("#studentDetails").textContent = `${pass.student.name} · ${pass.student.department || ""} · Year ${pass.student.year || ""}`;
    const participationType = document.querySelector("#participationType");
    if (participationType) {
      participationType.textContent = pass.participation_type === "team" ? "Team Registration" : "Individual Registration";
    }
    const teamDetails = document.querySelector("#teamDetails");
    if (teamDetails && pass.team && pass.team.name) {
      teamDetails.classList.remove("d-none");
      const memberNames = (pass.team.members || []).map(m => m.full_name).join(", ");
      teamDetails.textContent = `Team: ${pass.team.name}${memberNames ? ` (${memberNames})` : ""}`;
    }
    passMessage.textContent = "Valid registration for this event.";
    passCard.classList.remove("d-none");
  } catch (error) {
    if (error instanceof TypeError) {
      showPassError("The event pass service could not be reached. Check your connection and try again.");
    } else {
      showPassError(error.message || "Event pass could not be loaded. Please try again.");
    }
  }
})();
