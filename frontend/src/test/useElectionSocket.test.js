import { renderHook, act } from "@testing-library/react";
import { vi, describe, it, expect, beforeEach, afterEach } from "vitest";
import { useElectionSocket } from "../hooks/useElectionSocket";

let mockWs;

class MockWebSocket {
  constructor(url) {
    this.url = url;
    this.readyState = 0;
    mockWs = this;
  }
  close() {}
}

beforeEach(() => {
  vi.stubGlobal("WebSocket", MockWebSocket);
  vi.useFakeTimers();
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

describe("useElectionSocket", () => {
  it("inicia desconectado", () => {
    const { result } = renderHook(() => useElectionSocket("sp", "governador"));
    expect(result.current.connected).toBe(false);
    expect(result.current.data).toBeNull();
  });

  it("marca conectado ao onopen", () => {
    const { result } = renderHook(() => useElectionSocket("sp", "governador"));
    act(() => { mockWs.onopen(); });
    expect(result.current.connected).toBe(true);
  });

  it("parseia mensagem JSON recebida", () => {
    const { result } = renderHook(() => useElectionSocket("sp", "governador"));
    act(() => { mockWs.onopen(); });
    act(() => { mockWs.onmessage({ data: JSON.stringify({ pst: "50%" }) }); });
    expect(result.current.data).toEqual({ pst: "50%" });
  });

  it("marca desconectado ao onclose", () => {
    const { result } = renderHook(() => useElectionSocket("sp", "governador"));
    act(() => { mockWs.onopen(); });
    act(() => { mockWs.onclose(); });
    expect(result.current.connected).toBe(false);
  });
});
