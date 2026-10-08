const passMessage = document.querySelector("#passMessage");
const passCard = document.querySelector("#passCard");

(async () => {
  try {
    const registrationId = new URLSearchParams(window.location.search).get("registration_id");
    if (!registrationId) throw new Error("A registration is required.");
    const client = await getSupabaseClient();
    const session = (await client.auth.getSession()).data.session;
    if (!session) { window.location.href = "../../login/"; return; }
    const response = await fetch(apiUrl(`/api/registrations/${encodeURIComponent(registrationId)}/pass`), { headers: { Authorization: `Bearer ${session.access_token}` } });
    const body = await response.json();
    if (!response.ok) throw new Error(body.error?.message || "Event pass could not be loaded.");
    const pass = body.data;
    document.querySelector("#eventTitle").textContent = pass.event.title;
    document.querySelector("#eventDetails").textContent = `${pass.event.event_date} · ${pass.event.start_time}–${pass.event.end_time} · ${pass.event.venue.name}, ${pass.event.venue.location}`;
    document.querySelector("#studentDetails").textContent = `${pass.student.name} · ${pass.student.department || ""} · Year ${pass.student.year || ""}`;
    document.querySelector("#attendanceStatus").textContent = pass.attendance.status;
    await QRCode.toCanvas(document.querySelector("#qrCode"), pass.qr_payload, { width: 260, margin: 2 });
    passMessage.textContent = "Valid for this registration only.";
    passCard.classList.remove("d-none");
  } catch (error) { passMessage.className = "small text-danger mt-3"; passMessage.textContent = error.message; }
})();
