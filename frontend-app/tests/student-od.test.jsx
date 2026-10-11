import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { StudentODPage } from "../src/pages/StudentODPage.jsx";

vi.mock("../src/auth/AuthProvider.jsx", () => ({ useAuth: vi.fn() }));
vi.mock("../src/api/client.js", () => ({ apiUrl: (path) => `https://api.example${path}`, requestJson: vi.fn() }));
import { useAuth } from "../src/auth/AuthProvider.jsx";
import { requestJson } from "../src/api/client.js";

describe("student OD workflow", () => {
  beforeEach(() => { vi.clearAllMocks(); useAuth.mockReturnValue({ session: { access_token: "session" }, loading: false }); });

  it("lists active registrations and exposes a guarded generation action", async () => {
    requestJson.mockResolvedValue({ data: [{ registration_id: "registration-1", status: "registered", event: { title: "Campus Hack Day", event_date: "2026-10-20", venue: { name: "Innovation Hall" } } }] });
    render(<MemoryRouter><StudentODPage /></MemoryRouter>);
    expect(await screen.findByText("Campus Hack Day")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /generate and download/i })).toBeInTheDocument();
    expect(requestJson).toHaveBeenCalledWith("/api/registrations/my-registrations?status=registered", expect.any(Object));
  });

  it("shows backend failures instead of presenting fake records", async () => {
    requestJson.mockRejectedValue(new Error("Registrations unavailable"));
    render(<MemoryRouter><StudentODPage /></MemoryRouter>);
    expect(await screen.findByRole("alert")).toHaveTextContent("Registrations unavailable");
    expect(screen.queryByText("Generate and download")).not.toBeInTheDocument();
  });
});
