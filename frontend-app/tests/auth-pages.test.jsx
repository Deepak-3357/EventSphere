import { describe, expect, it, vi, beforeEach } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { LoginPage } from "../src/pages/LoginPage.jsx";
import { RegisterPage } from "../src/pages/RegisterPage.jsx";

vi.mock("../src/auth/auth-client.js", () => ({
  getSupabaseClient: vi.fn(),
  redirectByVerifiedRole: vi.fn(),
  rememberOAuthReturnTo: vi.fn(),
  safeStudentReturnTo: (value) => value?.startsWith("/student/") ? value : null,
  signInWithGoogle: vi.fn(() => Promise.resolve()),
}));

import { getSupabaseClient, redirectByVerifiedRole, signInWithGoogle } from "../src/auth/auth-client.js";

describe("student authentication pages", () => {
  beforeEach(() => { vi.clearAllMocks(); });

  it("shows Google sign-in only in the student login experience", async () => {
    render(<MemoryRouter><LoginPage /></MemoryRouter>);
    expect(screen.getByRole("button", { name: "Continue with Google" })).toBeInTheDocument();
    expect(screen.getByText(/student accounts only/i)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Continue with Google" }));
    await waitFor(() => expect(signInWithGoogle).toHaveBeenCalledWith("/student/"));
  });

  it("keeps email/password login available", async () => {
    const signInWithPassword = vi.fn().mockResolvedValue({ data: { session: { access_token: "access-token" } }, error: null });
    getSupabaseClient.mockResolvedValue({ auth: { signInWithPassword } });
    render(<MemoryRouter><LoginPage /></MemoryRouter>);
    fireEvent.change(screen.getByLabelText("Email"), { target: { value: "student@example.com" } });
    fireEvent.change(screen.getByLabelText("Password"), { target: { value: "password123" } });
    fireEvent.submit(screen.getByRole("button", { name: "Sign in with email" }).closest("form"));
    await waitFor(() => expect(signInWithPassword).toHaveBeenCalled());
    expect(redirectByVerifiedRole).toHaveBeenCalled();
  });

  it("does not send a client-selected role during student registration", async () => {
    const signUp = vi.fn().mockResolvedValue({ data: { session: null }, error: null });
    getSupabaseClient.mockResolvedValue({ auth: { signUp } });
    render(<MemoryRouter><RegisterPage /></MemoryRouter>);
    fireEvent.change(screen.getByLabelText("Full name"), { target: { value: "Student User" } });
    fireEvent.change(screen.getByLabelText("Email"), { target: { value: "student@example.com" } });
    fireEvent.change(screen.getByLabelText("Department"), { target: { value: "Computing" } });
    fireEvent.change(screen.getByLabelText("Year"), { target: { value: "2" } });
    fireEvent.change(screen.getByLabelText("Password"), { target: { value: "password123" } });
    fireEvent.change(screen.getByLabelText("Confirm password"), { target: { value: "password123" } });
    fireEvent.submit(screen.getByRole("button", { name: "Create student account" }).closest("form"));
    await waitFor(() => expect(signUp).toHaveBeenCalled());
    expect(signUp.mock.calls[0][0].options.data).not.toHaveProperty("role");
  });
});
