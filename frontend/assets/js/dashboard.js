const dashboardMessage = document.querySelector("#dashboardMessage");
const role = window.location.pathname.includes("/student/") ? "student" : window.location.pathname.includes("/organizer/") ? "organizer" : "admin";
const apiBase = `${eventSphereApiBase}/api`;
function text(id, value) { const node = document.querySelector(`#${id}`); if (node) node.textContent = value ?? "—"; }
function badge(value) { const node = document.createElement("span"); node.className = "badge text-bg-secondary"; node.textContent = value || "—"; return node; }
function listMessage(list, message) { const node = document.createElement("li"); node.className = "list-group-item text-secondary"; node.textContent = message; list.append(node); }
function renderStudent(data) {
  text("statUpcoming", data.stats.upcoming_events); text("statRegistrations", data.stats.registrations); text("statCheckedIn", `${data.stats.checked_in}/${data.stats.registrations}`); text("statNotifications", data.stats.unread_notifications);
  const events = document.querySelector("#upcomingEvents"); events.replaceChildren();
  if (!data.upcoming_events.length) listMessage(events, "No upcoming registered events.");
  data.upcoming_events.forEach((event) => { const li = document.createElement("li"); li.className = "list-group-item d-flex justify-content-between align-items-center gap-2"; const label = document.createElement("span"); label.textContent = `${event.title} · ${event.event_date} · ${event.venue_name}`; li.append(label, badge(event.attendance_status)); events.append(li); });
  const notifications = document.querySelector("#recentNotifications"); notifications.replaceChildren();
  if (!data.recent_notifications.length) listMessage(notifications, "No recent notifications.");
  data.recent_notifications.forEach((item) => { const li = document.createElement("li"); li.className = "list-group-item"; li.textContent = `${item.title}: ${item.message}`; notifications.append(li); });
}
function renderOrganizer(data) {
  text("statEvents", data.stats.total_events); text("statRegistrations", data.stats.total_registrations); text("statCheckedIn", data.stats.total_checked_in); text("statUpcoming", data.stats.upcoming_events);
  const rows = document.querySelector("#eventRows"); rows.replaceChildren(); if (!data.events.length) { listMessage(rows, "No events yet."); return; }
  data.events.forEach((event) => { const row = document.createElement("tr"); [event.title, event.status, `${event.registrations}/${event.capacity}`, event.checked_in].forEach((value) => { const cell = document.createElement("td"); cell.textContent = value; row.append(cell); }); rows.append(row); });
  if (window.Chart) new Chart(document.querySelector("#analyticsChart"), { type: "doughnut", data: { labels: data.analytics.status_distribution.map((x) => x.status), datasets: [{ data: data.analytics.status_distribution.map((x) => x.count), backgroundColor: ["#315efb", "#ffc107", "#6c757d", "#dc3545", "#198754"] }] }, options: { responsive: true } });
}
function renderAdmin(data) {
  Object.entries(data.stats).forEach(([key, value]) => text(`stat${key.replace(/(^|_)(\w)/g, (_, a, b) => b.toUpperCase())}`, value));
  if (window.Chart) new Chart(document.querySelector("#analyticsChart"), { type: "bar", data: { labels: data.analytics.events_by_category.map((x) => x.name), datasets: [{ label: "Events", data: data.analytics.events_by_category.map((x) => x.count), backgroundColor: "#315efb" }] }, options: { responsive: true, scales: { y: { beginAtZero: true } } } });
}
(async () => {
  try {
    const client = await getSupabaseClient(); const session = (await client.auth.getSession()).data.session;
    if (!session) { window.location.href = "../../login/"; return; }
    const profileResponse = await fetch(`${apiBase}/auth/me`, { headers: { Authorization: `Bearer ${session.access_token}` } }); const profileBody = await profileResponse.json();
    if (!profileResponse.ok || profileBody.profile.role !== role) throw new Error("This dashboard is not available for your role.");
    text("welcomeName", profileBody.profile.full_name); text("profileName", profileBody.profile.full_name); text("profileRole", role);
    const response = await fetch(`${apiBase}/dashboard/${role}`, { headers: { Authorization: `Bearer ${session.access_token}` } }); const body = await response.json(); if (!response.ok) throw new Error(body.error?.message || "Unable to load dashboard data.");
    if (role === "student") renderStudent(body.data); else if (role === "organizer") renderOrganizer(body.data); else renderAdmin(body.data);
    const unread = await fetch(`${apiBase}/notifications/unread-count`, { headers: { Authorization: `Bearer ${session.access_token}` } }); if (unread.ok) text("notificationCount", (await unread.json()).data.unread_count);
    document.querySelector("#logoutButton").addEventListener("click", async () => { await client.auth.signOut(); window.location.href = "../../login/"; }); dashboardMessage.classList.add("d-none");
  } catch (error) { dashboardMessage.className = "alert alert-danger"; dashboardMessage.textContent = error.message; }
})();
