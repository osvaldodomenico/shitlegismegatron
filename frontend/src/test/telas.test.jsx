import { describe, it, expect, vi } from "vitest";
import { render } from "@testing-library/react";

// Smoke de renderizacao das tres telas: pega ReferenceError/TypeError de
// render que o build nao pega (import esquecido virou pagina em branco em
// producao em 04/10 19:40).
vi.stubGlobal("WebSocket", class { constructor() { setTimeout(() => this.onopen && this.onopen(), 0); } close() {} send() {} });
vi.stubGlobal("fetch", vi.fn(async () => ({ ok: true, status: 200, json: async () => ({ corridas: [], sqcands: [], candidatos: [] }) })));

import App from "../App";
import { Painel } from "../Painel";
import { Dashboard } from "../Dashboard";

describe("telas renderizam sem erro de runtime", () => {
  it("/", () => { expect(() => render(<App />)).not.toThrow(); });
  it("/painel", () => { expect(() => render(<Painel />)).not.toThrow(); });
  it("/apuracaogeral", () => { expect(() => render(<Painel perfil="geral" editavel />)).not.toThrow(); });
  it("/dashboard", () => { expect(() => render(<Dashboard />)).not.toThrow(); });
});
