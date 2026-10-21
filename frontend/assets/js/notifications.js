const notificationMessage = document.querySelector("#notificationMessage");
const notificationList = document.querySelector("#notificationList");
const unreadCountElement = document.querySelector("#unreadCount");
const markAllButton = document.querySelector("#markAllButton");

function notificationEscape(value) {
  return String(value ?? "").replace(/[&<>'"]/g, (character) => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;"}[character]));
}

function renderNotifications(items) {
  if (!items.length) {
    notificationList.innerHTML = '<div class="alert alert-light border">You have no notifications.</div>';
    return;
  }
  notificationList.innerHTML = items.map((item) => `<div class="list-group-item ${item.is_read ? "" : "bg-primary-subtle"}"><div class="d-flex justify-content-between gap-3"><div><span class="badge text-bg-secondary">${notificationEscape(item.type)}</span><h2 class="h6 mt-2 mb-1">${notificationEscape(item.title)}</h2><p class="mb-1">${notificationEscape(item.message)}</p><small class="text-secondary">${new Date(item.created_at).toLocaleString()}</small></div>${item.is_read ? "" : `<button class="btn btn-sm btn-outline-primary align-self-start" data-notification-id="${notificationEscape(item.id)}">Mark read</button>`}</div></div>`).join("");
  notificationList.querySelectorAll("button[data-notification-id]").forEach((button) => button.addEventListener("click", async () => {
    button.disabled = true;
    const response = await fetch(apiUrl(`/api/notifications/${button.dataset.notificationId}/read`), { method: "PATCH", headers: { Authorization: `Bearer ${windowNotificationSession.access_token}` } });
    if (response.ok) loadNotifications(); else button.disabled = false;
  }));
}

let windowNotificationSession;
async function loadNotifications() {
  const [response, unreadResponse] = await Promise.all([
    fetch(apiUrl("/api/notifications?limit=100"), { headers: { Authorization: `Bearer ${windowNotificationSession.access_token}` } }),
    fetch(apiUrl("/api/notifications/unread-count"), { headers: { Authorization: `Bearer ${windowNotificationSession.access_token}` } })
  ]);
  const body = await response.json();
  if (!response.ok) throw new Error(body.error?.message || "Notifications could not be loaded.");
  renderNotifications(body.data);
  const unreadBody = await unreadResponse.json().catch(() => ({}));
  const unread = unreadResponse.ok ? (unreadBody.data?.unread_count ?? 0) : 0;
  unreadCountElement.textContent = unread;
  markAllButton.disabled = unread === 0;
  notificationMessage.textContent = `${body.pagination?.total ?? body.data.length} notification${body.pagination?.total === 1 ? "" : "s"}`;
}

(async () => {
  try {
    const client = await getSupabaseClient();
    windowNotificationSession = (await client.auth.getSession()).data.session;
    if (!windowNotificationSession) { redirectToLogin(); return; }
    await loadNotifications();
  } catch (error) { notificationMessage.className = "small text-danger"; notificationMessage.textContent = error.message; }
})();

markAllButton.addEventListener("click", async () => {
  markAllButton.disabled = true;
  await fetch(apiUrl("/api/notifications/read-all"), { method: "PATCH", headers: { Authorization: `Bearer ${windowNotificationSession.access_token}` } });
  await loadNotifications();
});
