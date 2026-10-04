import { useState } from "react";
import { aplicarTema, temaAtual } from "../lib/tema";
import { IconSun, IconMoon } from "./icons";

/** Alterna claro/escuro. Texto + icone: a acao nao depende so do desenho. */
export function BotaoTema({ className = "" }) {
  const [tema, setTema] = useState(temaAtual());
  const claro = tema === "light";
  function alternar() {
    setTema(aplicarTema(claro ? "dark" : "light"));
  }
  return (
    <button
      type="button"
      onClick={alternar}
      aria-pressed={claro}
      title={claro ? "Mudar para o tema escuro" : "Mudar para o tema claro"}
      className={`flex h-11 cursor-pointer items-center gap-2 rounded-lg border border-line bg-surface px-3 text-sm font-medium text-subtle transition-colors duration-150 hover:border-primaryLit hover:text-muted ${className}`}
    >
      {claro ? <IconMoon className="h-4 w-4" /> : <IconSun className="h-4 w-4" />}
      {claro ? "Escuro" : "Claro"}
    </button>
  );
}
