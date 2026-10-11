import { describe, expect, it, vi, beforeEach } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { AttendancePage } from "../src/pages/AttendancePage.jsx";

vi.mock("../src/api/client.js", () => ({ requestJson: vi.fn() }));
vi.mock("../src/auth/AuthProvider.jsx", () => ({ useAuth: vi.fn() }));
vi.mock("html5-qrcode", () => ({ Html5Qrcode: vi.fn() }));

import { requestJson } from "../src/api/client.js";
import { useAuth } from "../src/auth/AuthProvider.jsx";

const session = { access_token: "test-token" };
const event = { id: "event-1", title: "Campus Hack Day", event_date: "2026-10-20" };
const attendance = { summary: { registered: 1, checked_in: 0, absent: 1, attendance_percentage: 0 }, attendees: [] };

describe("React attendance page", () => {
  beforeEach(() => { vi.clearAllMocks(); useAuth.mockReturnValue({ session, profile: { role: "organizer" }, loading: false }); requestJson.mockImplementation((path) => path.startsWith("/api/events?") ? Promise.resolve({ data: [event] }) : Promise.resolve({ data: attendance, success: true })); });

  it("preserves leading zeros and submits the manual code", async () => {
    render(<MemoryRouter><AttendancePage /></MemoryRouter>);
    await waitFor(() => expect(screen.getByLabelText("Event")).toBeInTheDocument());
    fireEvent.change(screen.getByLabelText("Event"), { target: { value: "event-1" } });
    fireEvent.click(screen.getByRole("tab", { name: /Enter code/i }));
    const input = screen.getByLabelText("Six-digit code");
    fireEvent.change(input, { target: { value: "004281" } });
    expect(input).toHaveValue("004281");
    fireEvent.submit(screen.getByLabelText("Six-digit code").closest("form"));
    await waitFor(() => expect(requestJson).toHaveBeenCalledWith("/api/attendance/manual-check-in", expect.objectContaining({ body: JSON.stringify({ event_id: "event-1", code: "004281" }) })));
  });

  it("rejects wrong-length input before calling the API", async () => {
    render(<MemoryRouter><AttendancePage /></MemoryRouter>);
    await waitFor(() => expect(screen.getByLabelText("Event")).toBeInTheDocument());
    fireEvent.change(screen.getByLabelText("Event"), { target: { value: "event-1" } });
    fireEvent.click(screen.getByRole("tab", { name: /Enter code/i }));
    fireEvent.change(screen.getByLabelText("Six-digit code"), { target: { value: "12" } });
    fireEvent.submit(screen.getByLabelText("Six-digit code").closest("form"));
    expect(await screen.findByText(/exactly six digits/i)).toBeInTheDocument();
    expect(requestJson).not.toHaveBeenCalledWith("/api/attendance/manual-check-in", expect.anything());
  });
});
