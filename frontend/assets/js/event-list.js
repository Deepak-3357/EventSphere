const listElement = document.querySelector("#eventList");
const listMessage = document.querySelector("#eventMessage");

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>'"]/g, (character) => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;"}[character]));
}

fetch(apiUrl("/api/events?limit=100"))
  .then((response) => response.json().then((body) => ({ response, body })))
  .then(({ response, body }) => {
    if (!response.ok) throw new Error(body.error?.message || "Events could not be loaded.");
    listMessage.textContent = `${body.pagination.total} published event${body.pagination.total === 1 ? "" : "s"}`;
    listElement.innerHTML = body.data.map((event) => `
      <div class="col-md-6 col-lg-4">
        <article class="card h-100 border-0 shadow-sm"><div class="card-body">
          <span class="badge text-bg-primary mb-3">${escapeHtml(event.category.name)}</span>
          <h2 class="h5">${escapeHtml(event.title)}</h2>
          <p class="small text-secondary">${escapeHtml(event.event_date)} · ${escapeHtml(event.venue.name)}</p>
          <p class="text-secondary">${escapeHtml(event.description)}</p>
          <a class="btn btn-outline-primary btn-sm" href="detail.html?id=${encodeURIComponent(event.id)}">View details</a>
        </div></article>
      </div>`).join("");
  })
  .catch((error) => { listMessage.className = "small text-danger"; listMessage.textContent = error.message; });
