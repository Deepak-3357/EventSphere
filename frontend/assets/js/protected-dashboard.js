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
      redirectToLogin(roleForPage);
      return;
    }
    const identity = await callApi("/api/auth/me", data.session);
    if (identity.profile.role !== roleForPage) {
      window.location.replace(roleHomePath(identity.profile.role));
      return;
    }
    profileElement.textContent = `Signed in as ${identity.profile.full_name} (${identity.profile.role}).`;
  } catch (error) {
    redirectToLogin(roleForPage);
  }
})();

document.querySelector("#logoutButton")?.addEventListener("click", signOutAndRedirect);
