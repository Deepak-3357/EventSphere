import { describe, expect, it, vi, beforeEach } from "vitest";
import { apiBase, getCatalog, localApiBase, productionApiBase, resolveApiBase } from "../src/api/client.js";

describe("API client", () => {
  beforeEach(() => vi.restoreAllMocks());

  it("has explicit local and production API fallbacks", () => {
    expect(localApiBase).toBe("http://127.0.0.1:5000");
    expect(productionApiBase).toBe("https://eventspherebackend-azkp.onrender.com");
    expect(resolveApiBase("127.0.0.1")).toBe(localApiBase);
    expect(resolveApiBase("eventsphere-395t.onrender.com")).toBe(productionApiBase);
    expect(apiBase).toBe(localApiBase);
  });

  it("loads event, category, and venue response contracts", async () => {
    vi.stubGlobal("fetch", vi.fn((url) => Promise.resolve({ ok: true, json: async () => url.endsWith("/api/events?limit=100") ? { success: true, data: [{ id: "event-1" }], pagination: { total: 1 } } : { success: true, data: [{ id: "lookup-1" }] } })));
    await expect(getCatalog()).resolves.toEqual({ events: [{ id: "event-1" }], categories: [{ id: "lookup-1" }], venues: [{ id: "lookup-1" }], pagination: { total: 1 } });
  });

  it("turns non-2xx API responses into errors", async () => {
    vi.stubGlobal("fetch", vi.fn(() => Promise.resolve({ ok: false, status: 503, json: async () => ({ success: false, error: { message: "Unavailable" } }) })));
    await expect(getCatalog()).rejects.toThrow("Unavailable");
  });
});
