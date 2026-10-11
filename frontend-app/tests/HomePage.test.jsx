import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { HomePage } from "../src/pages/HomePage.jsx";

vi.mock("../src/api/client.js", () => ({
  getCatalog: vi.fn(),
}));
vi.mock("../src/auth/AuthProvider.jsx", () => ({ useAuth: () => ({ profile: null, loading: false }) }));

import { getCatalog } from "../src/api/client.js";

function renderPage() { return render(<MemoryRouter><HomePage /></MemoryRouter>); }

describe("homepage", () => {
  beforeEach(() => vi.clearAllMocks());

  it("shows loading and then real event links", async () => {
    getCatalog.mockResolvedValue({ events: [{ id: "event-1", title: "Campus Hack Day", description: "Build together", event_date: "2026-10-20", start_time: "10:00:00", category: { name: "Technology" }, venue: { name: "Innovation Hall" }, available_seats: 20 }], categories: [], venues: [] });
    renderPage();
    expect(screen.getByTestId("loading-state")).toBeInTheDocument();
    expect(await screen.findByRole("link", { name: "View Campus Hack Day" })).toHaveAttribute("href", "/events/detail.html?id=event-1");
  });

  it("shows a useful API error and retry control", async () => {
    getCatalog.mockRejectedValue(new Error("The event request failed."));
    renderPage();
    expect(await screen.findByTestId("error-state")).toHaveTextContent("The event request failed.");
    expect(screen.getByRole("button", { name: "Try again" })).toBeInTheDocument();
  });

  it("shows an empty state when there are no published events", async () => {
    getCatalog.mockResolvedValue({ events: [], categories: [], venues: [] });
    renderPage();
    expect(await screen.findByTestId("empty-state")).toBeInTheDocument();
  });

  it("falls back when an event image fails", async () => {
    getCatalog.mockResolvedValue({ events: [{ id: "event-2", title: "Fallback event", image_url: "https://invalid.test/image.jpg", category: {}, venue: {} }], categories: [], venues: [] });
    renderPage();
    const image = await screen.findByAltText("");
    image.dispatchEvent(new Event("error"));
    await waitFor(() => expect(image.src).toContain("data:image/svg+xml"));
  });
});
