(async () => {
  const badge = document.querySelector("#notificationBadge");
  if (!badge || typeof getSupabaseClient !== "function") return;
  try {
    const client = await getSupabaseClient();
    const session = (await client.auth.getSession()).data.session;
    if (!session) return;
    const response = await fetch(apiUrl("/api/notifications/unread-count"), { headers: { Authorization: `Bearer ${session.access_token}` } });
    const body = await response.json();
    if (response.ok) { badge.textContent = body.data.unread_count; badge.classList.toggle("d-none", body.data.unread_count === 0); }
  } catch (_) { /* The public navigation remains usable if Auth is unavailable. */ }
})();
