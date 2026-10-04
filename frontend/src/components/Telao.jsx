import { useEffect, useState } from "react";
import { IconBallot } from "./icons";

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
        ok ? "border-accent/40 bg-accent/10 text-accent" : "border-line bg-elevated text-subtle"}`}>
      <span className={`h-3 w-3 rounded-full ${ok ? "bg-accent animate-pulseSoft" : "bg-faint"}`} aria-hidden="true" />
      {ok ? "Ao vivo" : "Reconectando…"}
    </span>
  );
}

export function CabecalhoTelao({ aoVivo, relogio = "text-3xl", titulo = "text-2xl" }) {
  return (
    <header className="flex items-center justify-between border-b border-line px-10 py-4">
      <p className={`flex items-center gap-3 font-semibold text-primaryLit ${titulo}`}>
        <IconBallot className="h-8 w-8" />
        {MARCA}
        <span className="ml-3 text-lg font-normal text-faint">Eleições 2026 · 1º turno · Fonte: TSE</span>
      </p>
      <div className="flex items-center gap-6">
        <Relogio className={relogio} />
        <AoVivo ok={aoVivo} />
      </div>
    </header>
  );
}
