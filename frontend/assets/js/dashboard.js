const dashboardMessage = document.querySelector("#dashboardMessage");
const role = window.location.pathname.includes("/student/") ? "student" : window.location.pathname.includes("/organizer/") ? "organizer" : "admin";
if (role === "organizer") {
  const nav = document.querySelector(".dashboard-sidebar .nav");
  if (nav) {
    const link = document.createElement("a");
    link.className = "nav-link";
    link.href = "../../organizer/events/";
    link.textContent = "Manage Events";
    nav.insertBefore(link, nav.children[1] || null);
  }
}
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
async function setupMasterAdmin(session, profile) {
  if (role !== "admin" || profile.is_master_admin !== true) return;
  const main = document.querySelector("main");
  if (!main) return;
  const section = document.createElement("section");
  section.className = "card border-0 shadow-sm mt-4";
  section.innerHTML = `<div class="card-body"><div class="d-flex justify-content-between align-items-center flex-wrap gap-2"><div><h2 class="h5 mb-1">Master Admin · User management</h2><p class="small text-secondary mb-0">Create organizer and ordinary admin accounts. Student accounts remain public-registration only.</p></div><span class="badge text-bg-dark">Single Master Admin</span></div><div id="adminUserMessage" class="small mt-3" role="status"></div><div class="row g-2 mt-2"><div class="col-md-6"><label class="visually-hidden" for="adminUserSearch">Search users</label><input id="adminUserSearch" class="form-control" placeholder="Search by name or email"></div><div class="col-md-3"><label class="visually-hidden" for="adminUserRole">Filter role</label><select id="adminUserRole" class="form-select"><option value="">All roles</option><option value="student">Students</option><option value="organizer">Organizers</option><option value="admin">Admins</option></select></div></div><div class="table-responsive mt-3"><table class="table table-sm align-middle"><thead><tr><th>Name</th><th>Email</th><th>Role</th><th>Master</th></tr></thead><tbody id="adminUserRows"></tbody></table></div><hr><h3 class="h6">Create privileged account</h3><form id="privilegedUserForm" class="row g-2"><div class="col-md-3"><label class="visually-hidden" for="newUserName">Full name</label><input id="newUserName" class="form-control" placeholder="Full name" required></div><div class="col-md-3"><label class="visually-hidden" for="newUserEmail">Email</label><input id="newUserEmail" class="form-control" type="email" placeholder="Email" required></div><div class="col-md-2"><label class="visually-hidden" for="newUserRole">Role</label><select id="newUserRole" class="form-select"><option value="organizer">Organizer</option><option value="admin">Ordinary Admin</option></select></div><div class="col-md-2"><label class="visually-hidden" for="newUserPassword">Initial password</label><input id="newUserPassword" class="form-control" type="password" minlength="6" placeholder="Initial password" required></div><div class="col-md-2"><button class="btn btn-dark w-100" type="submit">Create account</button></div></form></div>`;
  main.append(section);
  const message = section.querySelector("#adminUserMessage"); const rows = section.querySelector("#adminUserRows");
  const loadUsers = async () => { const query = new URLSearchParams({ search: section.querySelector("#adminUserSearch").value, role: section.querySelector("#adminUserRole").value }); const response = await fetch(`${apiBase}/admin/users?${query}`, { headers: { Authorization: `Bearer ${session.access_token}` } }); const body = await response.json(); if (!response.ok) throw new Error(body.error?.message || "Users could not be loaded."); rows.replaceChildren(); body.data.forEach((user) => { const row = document.createElement("tr"); [user.full_name, user.email, user.role, user.is_master_admin ? "Yes" : "No"].forEach((value) => { const cell = document.createElement("td"); cell.textContent = value; row.append(cell); }); rows.append(row); }); if (!body.data.length) { const row = document.createElement("tr"); const cell = document.createElement("td"); cell.colSpan = 4; cell.className = "text-secondary"; cell.textContent = "No matching users."; row.append(cell); rows.append(row); } };
  section.querySelector("#adminUserSearch").addEventListener("input", () => loadUsers().catch((error) => { message.textContent = error.message; })); section.querySelector("#adminUserRole").addEventListener("change", () => loadUsers().catch((error) => { message.textContent = error.message; }));
  section.querySelector("#privilegedUserForm").addEventListener("submit", async (event) => { event.preventDefault(); const button = event.target.querySelector("button"); button.disabled = true; try { const response = await fetch(`${apiBase}/admin/users`, { method: "POST", headers: { "Content-Type": "application/json", Authorization: `Bearer ${session.access_token}` }, body: JSON.stringify({ full_name: section.querySelector("#newUserName").value, email: section.querySelector("#newUserEmail").value, role: section.querySelector("#newUserRole").value, password: section.querySelector("#newUserPassword").value }) }); const body = await response.json(); if (!response.ok) throw new Error(body.error?.message || "Account could not be created."); message.className = "small text-success mt-3"; message.textContent = "Account created and role verified."; event.target.reset(); await loadUsers(); } catch (error) { message.className = "small text-danger mt-3"; message.textContent = error.message; } finally { button.disabled = false; } });
  try { await loadUsers(); } catch (error) { message.className = "small text-danger mt-3"; message.textContent = error.message; }
}
(async () => {
  try {
    const client = await getSupabaseClient(); const session = (await client.auth.getSession()).data.session;
    if (!session) { redirectToLogin(role); return; }
    const profile = await verifiedProfile(session); const profileBody = { profile };
    if (profileBody.profile.role !== role) { window.location.replace(roleHomePath(profileBody.profile.role)); return; }
    text("welcomeName", profile.full_name); text("profileName", profile.full_name); text("profileRole", role);
    await setupMasterAdmin(session, profile);
    const [response, unread] = await Promise.all([
      fetch(`${apiBase}/dashboard/${role}`, { headers: { Authorization: `Bearer ${session.access_token}` } }),
      fetch(`${apiBase}/notifications/unread-count`, { headers: { Authorization: `Bearer ${session.access_token}` } })
    ]);
    const body = await response.json(); if (!response.ok) throw new Error(body.error?.message || "Unable to load dashboard data.");
    if (role === "student") renderStudent(body.data); else if (role === "organizer") renderOrganizer(body.data); else renderAdmin(body.data);
    if (unread.ok) {
      const unreadBody = await unread.json().catch(() => ({}));
      text("notificationCount", unreadBody.data?.unread_count ?? "0");
    }
    document.querySelector("#logoutButton").addEventListener("click", signOutAndRedirect); dashboardMessage.classList.add("d-none");
  } catch (error) { dashboardMessage.className = "alert alert-danger"; dashboardMessage.textContent = error.message; }
})();
