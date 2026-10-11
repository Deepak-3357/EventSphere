import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { SiteHeader } from "../src/components/SiteHeader.jsx";

vi.mock("../src/auth/AuthProvider.jsx", () => ({ useAuth: vi.fn() }));
import { useAuth } from "../src/auth/AuthProvider.jsx";

describe("role-aware homepage navigation", () => {
  it.each([["student", "/student/"], ["organizer", "/organizer/"], ["admin", "/admin/"]])("routes %s users to their verified dashboard", (role, path) => {
    useAuth.mockReturnValue({ profile: { role }, loading: false });
    render(<MemoryRouter><SiteHeader /></MemoryRouter>);
    expect(screen.getByRole("link", { name: /EventSphere home/i })).toHaveAttribute("href", path);
    expect(screen.getByRole("link", { name: /Dashboard/i })).toHaveAttribute("href", path);
  });

  it("keeps public navigation for signed-out visitors", () => {
    useAuth.mockReturnValue({ profile: null, loading: false });
    render(<MemoryRouter><SiteHeader /></MemoryRouter>);
    expect(screen.getByRole("link", { name: /EventSphere home/i })).toHaveAttribute("href", "/");
    expect(screen.getByRole("link", { name: /Sign in/i })).toHaveAttribute("href", "/login/");
  });
});
