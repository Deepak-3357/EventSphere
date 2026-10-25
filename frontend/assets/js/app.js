const featuredEvents = document.querySelector("#featuredEvents");
const categoryGrid = document.querySelector("#categoryGrid");
const eventFeedback = document.querySelector("#eventFeedback");
const navToggle = document.querySelector("#mainNavToggle");
const mainNav = document.querySelector("#mainNav");

const fallbackImage = "assets/img/event-fallback.svg";

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>'"]/g, (character) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;" }[character]));
}

function formatDate(value) {
  if (!value) return "Date to be announced";
  return new Intl.DateTimeFormat(undefined, { month: "short", day: "numeric", year: "numeric" }).format(new Date(`${value}T00:00:00`));
}

function formatTime(value) {
  if (!value) return "Time to be announced";
  return new Intl.DateTimeFormat(undefined, { hour: "numeric", minute: "2-digit" }).format(new Date(`1970-01-01T${value}`));
}

function withTimeout(promise, milliseconds = 10000) {
  return Promise.race([promise, new Promise((_, reject) => setTimeout(() => reject(new Error("The request timed out.")), milliseconds))]);
}

function showEventMessage(message, tone = "muted") {
  if (!eventFeedback) return;
  eventFeedback.className = `section-feedback section-feedback--${tone}`;
  eventFeedback.innerHTML = `<span>${escapeHtml(message)}</span>${tone === "error" ? '<button class="btn btn-sm btn-outline-primary" id="retryEvents" type="button">Try again</button>' : ""}`;
  document.querySelector("#retryEvents")?.addEventListener("click", loadHomepageData, { once: true });
}

function eventCard(event) {
  const image = escapeHtml(event.image_url || fallbackImage);
  const seats = Number.isFinite(event.available_seats) ? `${event.available_seats} seats left` : "Open registration";
  const description = (event.description || "Discover the details and make this campus experience yours.").trim();
  return `<article class="event-card"><a class="event-card__image" href="events/detail.html?id=${encodeURIComponent(event.id)}"><img src="${image}" alt="${escapeHtml(event.title)}" width="640" height="360" loading="lazy" onerror="this.onerror=null;this.src='${fallbackImage}'"></a><div class="event-card__body"><div class="event-card__meta"><span>${escapeHtml(event.category?.name || "Campus event")}</span><span>${escapeHtml(formatDate(event.event_date))}</span></div><h3><a href="events/detail.html?id=${encodeURIComponent(event.id)}">${escapeHtml(event.title)}</a></h3><p class="event-card__venue">${escapeHtml(event.venue?.name || "Campus venue")} · ${escapeHtml(event.venue?.location || "")}</p><p class="event-card__description">${escapeHtml(description)}</p><div class="event-card__footer"><span class="availability"><span class="availability__dot" aria-hidden="true"></span>${escapeHtml(seats)}</span><a class="text-link text-link--small" href="events/detail.html?id=${encodeURIComponent(event.id)}">View details <span aria-hidden="true">→</span></a></div></div></article>`;
}

function categoryCard(category) {
  const initial = escapeHtml((category.name || "E").trim().charAt(0).toUpperCase());
  return `<a class="category-card" href="events/?category=${encodeURIComponent(category.name)}"><span class="category-card__icon" aria-hidden="true">${initial}</span><span><strong>${escapeHtml(category.name)}</strong><small>${escapeHtml(category.description || "Explore events in this category")}</small></span><span class="category-card__arrow" aria-hidden="true">↗</span></a>`;
}

async function loadEvents() {
  const response = await withTimeout(fetch(apiUrl("/api/events?status=published&limit=6")));
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(body.error?.message || "Published events could not be loaded.");
  const today = new Date().toISOString().slice(0, 10);
  const events = (body.data || []).sort((left, right) => {
    const leftUpcoming = left.event_date >= today;
    const rightUpcoming = right.event_date >= today;
    if (leftUpcoming !== rightUpcoming) return leftUpcoming ? -1 : 1;
    return `${left.event_date}${left.start_time || ""}`.localeCompare(`${right.event_date}${right.start_time || ""}`);
  });
  if (!events.length) {
    featuredEvents.innerHTML = '<div class="empty-state"><span class="empty-state__icon" aria-hidden="true">✦</span><h3>New experiences are on the way.</h3><p>Published campus events will appear here as soon as organizers share them.</p><a class="btn btn-outline-primary" href="events/">Browse the catalog</a></div>';
    showEventMessage("No published events are available right now.");
    return;
  }
  featuredEvents.innerHTML = events.slice(0, 3).map(eventCard).join("");
  showEventMessage(`${body.pagination?.total || events.length} published event${(body.pagination?.total || events.length) === 1 ? "" : "s"} in the catalog.`);
}

async function loadCategories() {
  const response = await withTimeout(fetch(apiUrl("/api/categories")));
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(body.error?.message || "Categories could not be loaded.");
  const categories = body.data || [];
  categoryGrid.innerHTML = categories.length ? categories.slice(0, 6).map(categoryCard).join("") : '<p class="text-secondary">Categories will appear here as events are published.</p>';
}

async function loadHomepageData() {
  featuredEvents?.setAttribute("aria-busy", "true");
  showEventMessage("Loading published events…");
  try {
    await loadEvents();
  } catch (error) {
    if (featuredEvents) featuredEvents.innerHTML = '<div class="empty-state empty-state--error"><span class="empty-state__icon" aria-hidden="true">!</span><h3>Events are taking a moment.</h3><p>We could not reach the event catalog. Please try again.</p><button class="btn btn-primary" id="retryEventsInline" type="button">Retry</button></div>';
    document.querySelector("#retryEventsInline")?.addEventListener("click", loadHomepageData, { once: true });
    showEventMessage(error.message, "error");
  } finally {
    featuredEvents?.removeAttribute("aria-busy");
  }
  try {
    await loadCategories();
  } catch (_) {
    if (categoryGrid) categoryGrid.innerHTML = '<p class="text-secondary">Explore all available events in the catalog.</p>';
  }
}

async function updateAuthActions() {
  const signIn = document.querySelector(".nav-signin");
  const getStarted = document.querySelector("#authNav .btn-primary");
  if (!signIn || typeof getSupabaseClient !== "function") return;
  try {
    const client = await getSupabaseClient();
    const session = (await client.auth.getSession()).data.session;
    if (!session) return;
    const profile = await verifiedProfile(session);
    signIn.textContent = "Dashboard";
    signIn.href = roleHomePath(profile.role);
    if (getStarted) getStarted.classList.add("d-none");
  } catch (_) {
    // Guests can use the static navigation even when Auth is unavailable.
  }
}

navToggle?.addEventListener("click", () => {
  const open = mainNav.classList.toggle("is-open");
  navToggle.setAttribute("aria-expanded", String(open));
});
document.querySelectorAll("#mainNav a").forEach((link) => link.addEventListener("click", () => {
  mainNav?.classList.remove("is-open");
  navToggle?.setAttribute("aria-expanded", "false");
}));

loadHomepageData();
updateAuthActions();
