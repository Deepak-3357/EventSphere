import { describe, expect, it } from "vitest";
import { safeStudentReturnTo } from "../src/auth/auth-client.js";

describe("student OAuth redirect safety", () => {
  it("allows only same-origin student destinations", () => {
    expect(safeStudentReturnTo("/student/od-letters/")).toBe("/student/od-letters/");
    expect(safeStudentReturnTo("/events/detail.html?id=abc")).toBe("/events/detail.html?id=abc");
    expect(safeStudentReturnTo("https://evil.example/steal")).toBeNull();
    expect(safeStudentReturnTo("//evil.example/steal")).toBeNull();
    expect(safeStudentReturnTo("/admin/")).toBeNull();
  });
});
