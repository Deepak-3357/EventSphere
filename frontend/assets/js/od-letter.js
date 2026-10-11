const odMessage = document.querySelector("#odMessage"); const odCard = document.querySelector("#odCard"); const apiRoot = apiUrl("/api");
function safePdfFilename(letterNumber) { return `${String(letterNumber || "eventsphere-od-letter").replace(/[^a-z0-9._-]+/gi, "_")}.pdf`; }
 (async () => {
  try {
    const registrationId = new URLSearchParams(location.search).get("registration_id");
    const client = await getSupabaseClient(); const session = (await client.auth.getSession()).data.session; if (!session) { redirectToLogin("student"); return; }
    const headers = { Authorization: `Bearer ${session.access_token}` };
    if (!registrationId) { const response = await fetch(`${apiRoot}/my-registrations?status=registered`, { headers }); const body = await response.json(); if (!response.ok) throw new Error(body.error?.message || "Registrations could not be loaded."); const list = document.querySelector("#odList"); list.replaceChildren(); if (!body.data.length) { odMessage.textContent = "No active registrations are eligible for an OD letter."; return; } odMessage.textContent = "Choose an active registration to generate an OD letter."; body.data.forEach((item) => { const link = document.createElement("a"); link.className = "list-group-item list-group-item-action"; link.href = `?registration_id=${encodeURIComponent(item.registration_id)}`; link.textContent = `${item.event.title} · ${item.event.event_date}`; list.append(link); }); return; }
    const registration = await fetch(`${apiRoot}/registrations/${encodeURIComponent(registrationId)}`, { headers }); const registrationBody = await registration.json(); if (!registration.ok) throw new Error(registrationBody.error?.message || "Registration could not be loaded.");
    document.querySelector("#odEvent").textContent = registrationBody.data.event.title; document.querySelector("#odMeta").textContent = `${registrationBody.data.event.event_date} · ${registrationBody.data.event.venue.name}`; odCard.classList.remove("d-none");
    const existing = await fetch(`${apiRoot}/registrations/${encodeURIComponent(registrationId)}/od-letter`, { headers });
    if (existing.ok) {
      const existingBody = await existing.json();
      setup(existingBody.data, session);
    }
    document.querySelector("#generateButton").addEventListener("click", async () => { const response = await fetch(`${apiRoot}/registrations/${encodeURIComponent(registrationId)}/od-letter`, { method: "POST", headers }); const body = await response.json(); if (!response.ok) throw new Error(body.error?.message || "OD letter could not be generated."); setup(body.data, session); });
  } catch (error) { odMessage.className = "alert alert-danger mt-3"; odMessage.textContent = error.message; }
  function setup(letter, authSession) {
    if (!letter) return;
    odMessage.className = "alert alert-success mt-3";
    odMessage.textContent = `Generated ${letter.letter_number}.`;
    document.querySelector("#generateButton").classList.add("d-none");
    const link = document.querySelector("#downloadButton");
    const url = `${apiRoot}/od-letters/${letter.id}/download`;
    link.href = url;
    link.download = safePdfFilename(letter.letter_number);
    link.classList.remove("d-none");
    link.onclick = async (event) => {
      event.preventDefault();
      link.setAttribute("aria-busy", "true");
      try {
        const response = await fetch(url, { headers: { Authorization: `Bearer ${authSession.access_token}` } });
        const contentType = (response.headers.get("content-type") || "").toLowerCase();
        if (!response.ok || !contentType.includes("application/pdf")) {
          const body = await response.json().catch(() => ({}));
          throw new Error(body.error?.message || `OD PDF could not be downloaded (HTTP ${response.status}).`);
        }
        const blob = await response.blob();
        const signature = await blob.slice(0, 5).text();
        if (signature !== "%PDF-") throw new Error("The server returned an invalid PDF file.");
        const objectUrl = URL.createObjectURL(blob);
        const anchor = document.createElement("a");
        anchor.href = objectUrl;
        anchor.download = safePdfFilename(letter.letter_number);
        document.body.append(anchor);
        anchor.click();
        anchor.remove();
        window.setTimeout(() => URL.revokeObjectURL(objectUrl), 1000);
      } catch (error) {
        odMessage.className = "alert alert-danger mt-3";
        odMessage.textContent = error.message;
      } finally {
        link.removeAttribute("aria-busy");
      }
    };
  }
})();
