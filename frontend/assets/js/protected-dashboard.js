const roleForPage = window.location.pathname.includes("/organizer/")
  ? "organizer"
  : window.location.pathname.includes("/admin/")
    ? "admin"
    : "student";

(async () => {
  const profileElement = document.querySelector("#profile");
  try {
    const client = await getSupabaseClient();
    const { data, error } = await client.auth.getSession();
    if (error || !data.session) {
      window.location.href = "/login/";
      return;
    }
    const identity = await callApi("/api/auth/me", data.session);
    if (identity.profile.role !== roleForPage) {
      profileElement.className = "alert alert-warning mt-4 mb-0";
      profileElement.textContent = "You are not authorized to view this dashboard.";
      return;
    }
    profileElement.textContent = `Signed in as ${identity.profile.full_name} (${identity.profile.role}).`;
  } catch (error) {
    window.location.href = "/login/";
  }
})();

document.querySelector("#logoutButton")?.addEventListener("click", async () => {
  const client = await getSupabaseClient();
  await client.auth.signOut();
  window.location.href = "/login/";
});
