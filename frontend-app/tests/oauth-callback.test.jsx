import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { OAuthCallbackPage } from "../src/pages/OAuthCallbackPage.jsx";

const { getVerifiedIdentity, signOut, consumeOAuthReturnTo } = vi.hoisted(() => ({
  getVerifiedIdentity: vi.fn(),
  signOut: vi.fn(),
  consumeOAuthReturnTo: vi.fn(() => "/student/"),
}));

vi.mock("../src/auth/auth-client.js", () => ({
  getVerifiedIdentity,
  signOut,
  consumeOAuthReturnTo,
}));

describe("Google OAuth callback", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    window.history.replaceState({}, "", "/auth/callback/");
  });

  it("signs out a privileged account instead of entering the student flow", async () => {
    getVerifiedIdentity.mockResolvedValue({ session: { access_token: "token" }, profile: { role: "admin" } });
    signOut.mockResolvedValue(undefined);
    render(<MemoryRouter><OAuthCallbackPage /></MemoryRouter>);

    expect(await screen.findByRole("alert")).toHaveTextContent(/only available for student accounts/i);
    await waitFor(() => expect(signOut).toHaveBeenCalledTimes(1));
    expect(consumeOAuthReturnTo).not.toHaveBeenCalled();
  });

  it("reports a missing verified session", async () => {
    getVerifiedIdentity.mockResolvedValue({ session: null, profile: null });
    render(<MemoryRouter><OAuthCallbackPage /></MemoryRouter>);

    expect(await screen.findByRole("alert")).toHaveTextContent(/no authenticated session/i);
  });
});
