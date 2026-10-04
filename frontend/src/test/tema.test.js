import { describe, it, expect, beforeEach, vi } from "vitest";
import { lerTema, aplicarTema, temaAtual } from "../lib/tema";

// O localStorage do jsdom nesta versao nao expoe clear(); um stub em memoria
// basta para o contrato (getItem/setItem) que o modulo usa.
const memoria = new Map();
vi.stubGlobal("localStorage", {
  getItem: (k) => (memoria.has(k) ? memoria.get(k) : null),
  setItem: (k, v) => memoria.set(k, String(v)),
  removeItem: (k) => memoria.delete(k),
});

beforeEach(() => {
  memoria.clear();
  document.documentElement.className = "";
});

describe("tema", () => {
  it("padrao e escuro", () => {
    expect(lerTema("")).toBe("dark");
  });

  it("a URL vence o que esta salvo — abre o telao direto no tema pedido", () => {
    localStorage.setItem("megatron-tema", "dark");
    expect(lerTema("?tema=light")).toBe("light");
  });

  it("aplicar grava a escolha e marca o <html>", () => {
    aplicarTema("light");
    expect(temaAtual()).toBe("light");
    expect(lerTema("")).toBe("light");
    aplicarTema("dark");
    expect(temaAtual()).toBe("dark");
  });
});
