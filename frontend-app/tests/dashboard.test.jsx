import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { DashboardPage } from "../src/pages/DashboardPage.jsx";

vi.mock("../src/auth/AuthProvider.jsx", () => ({ useAuth: vi.fn() }));
vi.mock("../src/api/client.js", () => ({ requestJson: vi.fn() }));
import { useAuth } from "../src/auth/AuthProvider.jsx";
import { requestJson } from "../src/api/client.js";

describe("role dashboards", () => {
  beforeEach(() => { vi.clearAllMocks(); useAuth.mockReturnValue({ session: { access_token: "session" }, profile: { role: "student", full_name: "Student" }, loading: false, signOut: vi.fn() }); });

  it("loads real student dashboard aggregates and registrations", async () => {
    requestJson.mockResolvedValue({ data: { stats: { registrations: 2, upcoming_events: 1, checked_in: 0, unread_notifications: 1 }, upcoming_events: [{ registration_id: "r1", title: "Campus Hack Day", event_date: "2026-10-20", attendance_status: "not_checked_in" }], recent_registrations: [], recent_notifications: [] } });
    render(<MemoryRouter><DashboardPage role="student" /></MemoryRouter>);
    expect(await screen.findByText("Campus Hack Day")).toBeInTheDocument();
    expect(requestJson).toHaveBeenCalledWith("/api/dashboard/student", expect.any(Object));
  });

  it("shows an actionable error when the role dashboard request fails", async () => {
    requestJson.mockRejectedValue(new Error("Dashboard unavailable"));
    render(<MemoryRouter><DashboardPage role="student" /></MemoryRouter>);
    expect(await screen.findByRole("alert")).toHaveTextContent("Dashboard unavailable");
    await waitFor(() => expect(screen.getByRole("button", { name: "Try again" })).toBeInTheDocument());
  });

  it("does not allow a student to render an organizer dashboard", () => {
    render(<MemoryRouter><DashboardPage role="organizer" /></MemoryRouter>);
    expect(screen.getByText(/dashboard access restricted/i)).toBeInTheDocument();
    expect(requestJson).not.toHaveBeenCalled();
  });
});
