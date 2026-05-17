import { useState, useEffect, useRef, useCallback } from "react";

const WS_URL = typeof import.meta !== "undefined" && import.meta.env
  ? (import.meta.env.VITE_WS_URL || "ws://localhost:8000")
  : "ws://localhost:8000";

const BACKOFF_DELAYS = [2000, 4000, 8000, 16000, 30000];

export function useElectionSocket(uf, cargo) {
  const [data, setData] = useState(null);
  const [connected, setConnected] = useState(false);
  const wsRef = useRef(null);
  const retryRef = useRef(0);
  const timerRef = useRef(null);

  const connect = useCallback(() => {
    const ws = new WebSocket(`${WS_URL}/ws/${uf}/${cargo}`);
    wsRef.current = ws;

    ws.onopen = () => {
      setConnected(true);
      retryRef.current = 0;
    };

    ws.onmessage = (e) => {
      try { setData(JSON.parse(e.data)); } catch { /* ignora JSON inválido */ }
    };

    ws.onclose = () => {
      setConnected(false);
      const delay = BACKOFF_DELAYS[Math.min(retryRef.current, BACKOFF_DELAYS.length - 1)];
      retryRef.current += 1;
      timerRef.current = setTimeout(connect, delay);
    };

    ws.onerror = () => ws.close();
  }, [uf, cargo]);

  useEffect(() => {
    connect();
    return () => {
      clearTimeout(timerRef.current);
      wsRef.current?.close();
    };
  }, [connect]);

  return { data, connected };
}
