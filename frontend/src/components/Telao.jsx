import { useEffect, useState } from "react";
import { IconBallot, IconTrophy, IconRepeat } from "./icons";
import { classificarSituacao, boletimFinal } from "../lib/tse";
import { BotaoTema } from "./BotaoTema";

/**
 * Pecas compartilhadas pelas telas de telao (/painel e /dashboard): marca,
 * relogio, estado da conexao e foto com fallback de iniciais.
 */

export const MARCA = "LEGIS MEGATRON";

export const fmtPct = (v, num) => num(v).toFixed(2).replace(".", ",");

export function Foto({ src, nome, tamanho = "h-20 w-20", texto = "text-xl" }) {
  const [falhou, setFalhou] = useState(false);
  const iniciais = (nome || "?").split(/\s+/).filter(Boolean).slice(0, 2).map((p) => p[0]).join("");
  if (!src || falhou) {
    return (
      <div className={`flex ${tamanho} shrink-0 items-center justify-center rounded-xl bg-elevated ${texto} font-semibold text-subtle`} aria-hidden="true">
        {iniciais}
      </div>
    );
  }
  return (
    <img src={src} alt="" onError={() => setFalhou(true)}
      className={`${tamanho} shrink-0 rounded-xl object-cover`} />
  );
}

const TAM = {
  xs: { selo: "px-1.5 py-0.5 text-[11px]", icone: "h-3.5 w-3.5" },
  sm: { selo: "px-2 py-0.5 text-sm", icone: "h-4 w-4" },
};

/**
 * Situacao publicada pelo TSE, com peso visual por tipo: eleito = verde com
 * trofeu; 2o turno = laranja com setas; suplente/nao eleito = neutro. Nada
 * enquanto o TSE nao preencher.
 */
export function Selo({ cand, tamanho = "sm" }) {
  const { tipo, texto } = classificarSituacao(cand);
  if (!tipo) return null;
  const t = TAM[tamanho] || TAM.sm;
  const base = `flex shrink-0 items-center gap-1 rounded font-bold uppercase tracking-wider ${t.selo}`;
  if (tipo === "eleito") {
    return <span className={`${base} bg-success/25 text-successLit`}><IconTrophy className={t.icone} />{texto}</span>;
  }
  if (tipo === "segundo_turno") {
    return <span className={`${base} bg-accent/15 text-accent`}><IconRepeat className={t.icone} />2º turno</span>;
  }
  return (
    <span className={`shrink-0 rounded bg-elevated font-medium ${t.selo} ${tipo === "nao_eleito" ? "text-faint" : "text-subtle"}`}>
      {texto}
    </span>
  );
}

/** Aviso de totalizacao final (`tf` = "s"). Nada antes disso. */
export function Final({ data, className = "text-xs" }) {
  if (!boletimFinal(data)) return null;
  return (
    <span className={`shrink-0 rounded bg-success/25 px-2 py-0.5 font-bold uppercase tracking-wider text-successLit ${className}`}>
      Totalização final
    </span>
  );
}

export function Relogio({ className = "text-3xl" }) {
  const [agora, setAgora] = useState(new Date());
  useEffect(() => {
    const t = setInterval(() => setAgora(new Date()), 1000);
    return () => clearInterval(t);
  }, []);
  return (
    <span className={`num font-mono font-semibold text-muted ${className}`}>
      {agora.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit", second: "2-digit" })}
    </span>
  );
}

export function AoVivo({ ok, className = "text-lg" }) {
  return (
    <span role="status" aria-live="polite"
      className={`flex items-center gap-2 rounded-full border px-4 py-2 font-medium ${className} ${
        ok ? "border-successLit/40 bg-success/20 text-successLit" : "border-line bg-elevated text-subtle"}`}>
      <span className={`h-3 w-3 rounded-full ${ok ? "bg-successLit animate-pulseSoft" : "bg-faint"}`} aria-hidden="true" />
      {ok ? "Ao vivo" : "Reconectando…"}
    </span>
  );
}

export function CabecalhoTelao({ aoVivo, relogio = "text-3xl", titulo = "text-2xl" }) {
  return (
    <header className="flex items-center justify-between border-b border-line px-10 py-4">
      <p className={`flex items-center gap-3 whitespace-nowrap font-semibold text-primaryLit ${titulo}`}>
        <IconBallot className="h-8 w-8 shrink-0" />
        {MARCA}
        {/* Em 1080 de largura (dashboard vertical) o subtitulo nao cabe ao lado do relogio e do botao de tema. */}
        <span className="ml-3 hidden text-lg font-normal text-faint 2xl:inline">Eleições 2026 · 1º turno · Fonte: TSE</span>
      </p>
      <div className="flex items-center gap-6">
        <Relogio className={relogio} />
        <AoVivo ok={aoVivo} />
        <BotaoTema />
      </div>
    </header>
  );
}
