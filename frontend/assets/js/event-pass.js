const passMessage = document.querySelector("#passMessage");
const passCard = document.querySelector("#passCard");

(async () => {
  try {
    const registrationId = new URLSearchParams(window.location.search).get("registration_id");
    if (!registrationId) throw new Error("A registration is required.");
    const client = await getSupabaseClient();
    const session = (await client.auth.getSession()).data.session;
    if (!session) { redirectToLogin("student"); return; }
    const response = await fetch(apiUrl(`/api/registrations/${encodeURIComponent(registrationId)}/pass`), { headers: { Authorization: `Bearer ${session.access_token}` } });
    const body = await response.json();
    if (!response.ok) throw new Error(body.error?.message || "Event pass could not be loaded.");
    const pass = body.data;
    if (!pass || typeof pass !== "object" || !pass.event || !pass.student || !pass.attendance) {
      throw new Error("The event pass data is incomplete. Please refresh and try again.");
    }
    if (typeof pass.qr_payload !== "string" || !pass.qr_payload.trim()) {
      throw new Error("This event pass does not contain a valid signed QR payload.");
    }
    if (typeof pass.qr_image !== "string" || !pass.qr_image.startsWith("data:image/png;base64,")) {
      throw new Error("The event pass QR code is unavailable. Please refresh and try again.");
    }
    document.querySelector("#eventTitle").textContent = pass.event.title;
    document.querySelector("#eventDetails").textContent = `${pass.event.event_date} · ${pass.event.start_time}–${pass.event.end_time} · ${pass.event.venue.name}, ${pass.event.venue.location}`;
    document.querySelector("#studentDetails").textContent = `${pass.student.name} · ${pass.student.department || ""} · Year ${pass.student.year || ""}`;
    document.querySelector("#attendanceStatus").textContent = pass.attendance.status;
    const qrCode = document.querySelector("#qrCode");
    const qrReady = new Promise((resolve, reject) => {
      qrCode.onload = resolve;
      qrCode.onerror = () => reject(new Error("The event pass QR code could not be displayed."));
    });
    qrCode.src = pass.qr_image;
    await qrReady;
    passMessage.textContent = "Valid for this registration only.";
    passCard.classList.remove("d-none");
  } catch (error) { passMessage.className = "small text-danger mt-3"; passMessage.textContent = error.message; }
})();
