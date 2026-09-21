import { useEffect, useMemo, useRef, useState } from "react";
import { IconSearch, IconClose, IconCheck, IconAlert } from "./icons";

/**
 * Seletor de ate 5 candidatos a acompanhar.
 *
 * Deputado federal de SP tem 1429 candidatos: um <select> e inviavel, entao a
 * escolha e por busca (nome, numero ou partido). A lista e virtualizada de
 * forma simples — so as primeiras LIMITE_RENDER linhas sao montadas, senao o
 * navegador monta 1429 nos de uma vez a cada tecla digitada.
 */
const LIMITE_RENDER = 60;

function normalizar(t) {
  return (t || "")
    .toLowerCase()
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "");
}

export function SeletorCandidatos({
  aberto, aoFechar, candidatos, selecionados, maximo, aoConfirmar, salvando, erro,
}) {
  const [busca, setBusca] = useState("");
  const [escolha, setEscolha] = useState(selecionados);
  const buscaRef = useRef(null);
  const dialogoRef = useRef(null);

  useEffect(() => { if (aberto) { setEscolha(selecionados); setBusca(""); } }, [aberto, selecionados]);

  // Foco vai para a busca ao abrir; Esc fecha. Sem isso o modal e uma
  // armadilha para quem navega por teclado.
  useEffect(() => {
    if (!aberto) return;
    buscaRef.current?.focus();
    const onKey = (e) => { if (e.key === "Escape") aoFechar(); };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [aberto, aoFechar]);

  const filtrados = useMemo(() => {
    const q = normalizar(busca);
    if (!q) return candidatos;
    return candidatos.filter(
      (c) =>
        normalizar(c.nm).includes(q) ||
        normalizar(c.cc).includes(q) ||
        String(c.n || "").includes(q)
    );
  }, [candidatos, busca]);

  if (!aberto) return null;

  const cheio = escolha.length >= maximo;

  function alternar(sqcand) {
    setEscolha((atual) =>
      atual.includes(sqcand)
        ? atual.filter((s) => s !== sqcand)
        : atual.length >= maximo
          ? atual
          : [...atual, sqcand]
    );
  }

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center sm:items-center">
      {/* Scrim: escurece o suficiente para isolar o dialogo. */}
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={aoFechar} aria-hidden="true" />

      <div
        ref={dialogoRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="seletor-titulo"
        className="relative flex max-h-[88vh] w-full max-w-lg animate-slideUp flex-col overflow-hidden rounded-t-2xl border border-line bg-surface shadow-2xl sm:rounded-2xl"
      >
        <header className="flex items-start justify-between gap-3 border-b border-line px-5 py-4">
          <div>
            <h2 id="seletor-titulo" className="text-lg font-semibold text-muted">
              Escolher candidatos
            </h2>
            <p className="mt-0.5 text-sm text-subtle">
              Até {maximo} por corrida · {candidatos.length.toLocaleString("pt-BR")} disponíveis
            </p>
          </div>
          <button
            onClick={aoFechar}
            aria-label="Fechar seletor"
            className="-m-2 flex h-11 w-11 items-center justify-center rounded-lg text-subtle transition-colors duration-150 hover:bg-elevated hover:text-muted"
          >
            <IconClose className="h-5 w-5" />
          </button>
        </header>

        <div className="border-b border-line px-5 py-3">
          <div className="relative">
            <IconSearch className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-faint" />
            <input
              ref={buscaRef}
              type="search"
              value={busca}
              onChange={(e) => setBusca(e.target.value)}
              placeholder="Nome, número ou partido"
              aria-label="Buscar candidato por nome, número ou partido"
              className="h-11 w-full rounded-lg border border-line bg-bg pl-9 pr-3 text-base text-muted placeholder:text-faint focus:border-primaryLit focus:outline-none"
            />
          </div>
          <p className="mt-2 flex items-center justify-between text-xs text-faint">
            <span>{filtrados.length.toLocaleString("pt-BR")} resultado(s)</span>
            <span className={cheio ? "font-medium text-accent" : ""}>
              {escolha.length} de {maximo} escolhidos
            </span>
          </p>
        </div>

        <ul className="flex-1 overflow-y-auto overscroll-contain px-2 py-2">
          {filtrados.length === 0 && (
            <li className="px-3 py-10 text-center text-sm text-subtle">
              Nenhum candidato corresponde a “{busca}”.
            </li>
          )}
          {filtrados.slice(0, LIMITE_RENDER).map((c) => {
            const marcado = escolha.includes(c.sqcand);
            const bloqueado = cheio && !marcado;
            return (
              <li key={c.sqcand}>
                <button
                  onClick={() => alternar(c.sqcand)}
                  disabled={bloqueado}
                  aria-pressed={marcado}
                  className={`flex min-h-[44px] w-full items-center gap-3 rounded-lg px-3 py-2 text-left transition-colors duration-150 ${
                    marcado ? "bg-primary/20" : bloqueado ? "opacity-40" : "hover:bg-elevated"
                  } ${bloqueado ? "cursor-not-allowed" : "cursor-pointer"}`}
                >
                  <span
                    className={`flex h-5 w-5 shrink-0 items-center justify-center rounded border ${
                      marcado ? "border-primaryLit bg-primaryLit text-bg" : "border-line"
                    }`}
                    aria-hidden="true"
                  >
                    {marcado && <IconCheck className="h-3.5 w-3.5" strokeWidth={3} />}
                  </span>
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-sm font-medium text-muted">{c.nm}</span>
                    <span className="block truncate text-xs text-faint">{c.cc}</span>
                  </span>
                  <span className="num shrink-0 font-mono text-sm text-subtle">{c.n}</span>
                </button>
              </li>
            );
          })}
          {filtrados.length > LIMITE_RENDER && (
            <li className="px-3 py-3 text-center text-xs text-faint">
              Mostrando {LIMITE_RENDER} de {filtrados.length.toLocaleString("pt-BR")} — refine a busca.
            </li>
          )}
        </ul>

        <footer className="border-t border-line px-5 py-4">
          {erro && (
            <p role="alert" className="mb-3 flex items-start gap-2 text-sm text-accent">
              <IconAlert className="mt-0.5 h-4 w-4 shrink-0" />
              {erro}
            </p>
          )}
          <div className="flex gap-3">
            <button
              onClick={aoFechar}
              className="h-11 flex-1 cursor-pointer rounded-lg border border-line text-sm font-medium text-subtle transition-colors duration-150 hover:bg-elevated hover:text-muted"
            >
              Cancelar
            </button>
            <button
              onClick={() => aoConfirmar(escolha)}
              disabled={salvando}
              className="h-11 flex-1 cursor-pointer rounded-lg bg-primary text-sm font-semibold text-white transition-colors duration-150 hover:bg-primaryLit disabled:cursor-wait disabled:opacity-60"
            >
              {salvando ? "Salvando…" : "Acompanhar"}
            </button>
          </div>
        </footer>
      </div>
    </div>
  );
}
