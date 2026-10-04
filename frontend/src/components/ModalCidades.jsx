import { useEffect, useMemo, useRef, useState } from "react";
import { num, partido } from "../lib/tse";
import * as api from "../lib/api";
import { IconClose, IconSearch } from "./icons";

/**
 * Votacao de um candidato por cidade (ou zona), do banco do coletor de
 * municipios (atualiza a cada 5 min). Abre ao clicar no card do candidato.
 */
const fmtInt = (v) => num(v).toLocaleString("pt-BR");
const fmtPct = (v) => num(v).toFixed(2).replace(".", ",");

export function ModalCidades({ aberto, aoFechar, uf, cargo, cand }) {
  const [nivel, setNivel] = useState("municipio");
  const [dados, setDados] = useState(null);
  const [erro, setErro] = useState("");
  const [carregando, setCarregando] = useState(false);
  const [busca, setBusca] = useState("");
  const buscaRef = useRef(null);

  useEffect(() => {
    if (!aberto || !cand) return;
    let vivo = true;
    setCarregando(true);
    setErro("");
    api.buscarCidades(uf, cargo, cand.sqcand, nivel)
      .then((d) => { if (vivo) setDados(d); })
      .catch((e) => { if (vivo) { setDados(null); setErro(/404/.test(e.message) ? "O coletor por cidade ainda não gravou esta corrida." : "Não foi possível carregar a votação por cidade."); } })
      .finally(() => { if (vivo) setCarregando(false); });
    return () => { vivo = false; };
  }, [aberto, uf, cargo, cand?.sqcand, nivel]);

  useEffect(() => {
    if (!aberto) return;
    setBusca("");
    setTimeout(() => buscaRef.current?.focus(), 50);
    const tecla = (e) => { if (e.key === "Escape") aoFechar(); };
    window.addEventListener("keydown", tecla);
    return () => window.removeEventListener("keydown", tecla);
  }, [aberto, aoFechar]);

  const lista = useMemo(() => {
    const todos = dados?.lista || [];
    const q = busca.trim().toLowerCase();
    return q ? todos.filter((l) => l.nome.toLowerCase().includes(q) || l.cod.includes(q) || (l.zona || "").includes(q)) : todos;
  }, [dados, busca]);
  const melhor = Math.max(...(dados?.lista || []).map((l) => l.votos), 1);

  if (!aberto || !cand) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center sm:items-center">
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={aoFechar} aria-hidden="true" />
      <div role="dialog" aria-modal="true" aria-labelledby="cidades-titulo"
        className="relative flex max-h-[90vh] w-full max-w-2xl animate-slideUp flex-col overflow-hidden rounded-t-2xl border border-line bg-surface shadow-2xl sm:rounded-2xl">
        <header className="flex items-start justify-between gap-3 border-b border-line px-5 py-4">
          <div className="flex min-w-0 items-center gap-3">
            {cand.foto && <img src={cand.foto} alt="" className="h-12 w-12 shrink-0 rounded-lg object-cover" />}
            <div className="min-w-0">
              <h2 id="cidades-titulo" className="truncate text-lg font-semibold text-muted">{cand.nmu || cand.nm}</h2>
              <p className="text-sm text-subtle">
                <span className="num font-mono">{cand.n}</span> · {partido(cand)} · votação por {nivel === "zona" ? "zona eleitoral" : "cidade"}
              </p>
            </div>
          </div>
          <button onClick={aoFechar} aria-label="Fechar"
            className="-m-2 flex h-11 w-11 shrink-0 items-center justify-center rounded-lg text-subtle transition-colors duration-150 hover:bg-elevated hover:text-muted">
            <IconClose className="h-5 w-5" />
          </button>
        </header>

        {dados && (
          <dl className="grid grid-cols-3 gap-3 border-b border-line px-5 py-3 text-center">
            <div><dt className="text-[10px] uppercase tracking-wider text-faint">Votos somados</dt>
              <dd className="num font-mono text-xl font-bold text-muted">{fmtInt(dados.total_votos)}</dd></div>
            <div><dt className="text-[10px] uppercase tracking-wider text-faint">{nivel === "zona" ? "Zonas com voto" : "Cidades com voto"}</dt>
              <dd className="num font-mono text-xl font-bold text-muted">{dados.com_voto}<span className="text-sm font-normal text-subtle"> de {dados.lugares}</span></dd></div>
            <div><dt className="text-[10px] uppercase tracking-wider text-faint">Melhor lugar</dt>
              <dd className="truncate text-sm font-semibold text-muted">{dados.lista[0]?.nome}<span className="num ml-1 font-mono text-subtle">{fmtInt(dados.lista[0]?.votos)}</span></dd></div>
          </dl>
        )}

        <div className="flex items-center gap-2 border-b border-line px-5 py-3">
          <div className="relative flex-1">
            <IconSearch className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-faint" />
            <input ref={buscaRef} type="search" value={busca} onChange={(e) => setBusca(e.target.value)}
              placeholder={nivel === "zona" ? "Cidade ou número da zona" : "Nome da cidade"} aria-label="Buscar"
              className="h-10 w-full rounded-lg border border-line bg-bg pl-9 pr-3 text-sm text-muted placeholder:text-faint focus:border-primaryLit focus:outline-none" />
          </div>
          <div className="flex rounded-lg border border-line p-0.5" role="tablist" aria-label="Nível">
            {[["municipio", "Cidade"], ["zona", "Zona"]].map(([v, rotulo]) => (
              <button key={v} role="tab" aria-selected={nivel === v} onClick={() => setNivel(v)}
                className={`h-9 rounded-md px-3 text-sm font-medium transition-colors duration-150 ${nivel === v ? "bg-primary text-white" : "text-subtle hover:text-muted"}`}>
                {rotulo}
              </button>
            ))}
          </div>
        </div>

        <div className="flex-1 overflow-y-auto overscroll-contain">
          {carregando && <p className="px-5 py-10 text-center text-sm text-subtle">Carregando…</p>}
          {!carregando && erro && <p className="px-5 py-10 text-center text-sm text-accent">{erro}</p>}
          {!carregando && !erro && dados && (
            <table className="w-full text-sm">
              <thead className="sticky top-0 bg-surface text-[11px] uppercase tracking-wider text-faint">
                <tr>
                  <th className="px-5 py-2 text-left font-medium">#</th>
                  <th className="py-2 text-left font-medium">{nivel === "zona" ? "Cidade · zona" : "Cidade"}</th>
                  <th className="py-2 text-right font-medium">Seções</th>
                  <th className="py-2 text-right font-medium">Votos</th>
                  <th className="px-5 py-2 text-right font-medium">% na cidade</th>
                </tr>
              </thead>
              <tbody>
                {lista.map((l, i) => (
                  <tr key={`${l.cod}-${l.zona}`} className="border-t border-line/60">
                    <td className="num px-5 py-1.5 font-mono text-faint">{i + 1}</td>
                    <td className="py-1.5">
                      <div className="font-medium text-muted">{l.nome}{l.zona && <span className="num ml-2 font-mono text-xs text-subtle">zona {l.zona}</span>}</div>
                      <div className="mt-1 h-1 w-40 overflow-hidden rounded-full bg-elevated">
                        <div className="h-full rounded-full bg-primaryLit" style={{ width: `${Math.max((l.votos / melhor) * 100, l.votos ? 1 : 0)}%` }} />
                      </div>
                    </td>
                    <td className={`num py-1.5 text-right font-mono ${l.pst >= 100 ? "text-successLit" : "text-subtle"}`}>{fmtPct(l.pst)}%</td>
                    <td className="num py-1.5 text-right font-mono font-semibold text-muted">{fmtInt(l.votos)}</td>
                    <td className="num px-5 py-1.5 text-right font-mono text-subtle">{l.pct}%</td>
                  </tr>
                ))}
                {lista.length === 0 && (
                  <tr><td colSpan={5} className="px-5 py-8 text-center text-subtle">Nada corresponde a “{busca}”.</td></tr>
                )}
              </tbody>
            </table>
          )}
        </div>
        {dados && (
          <p className="border-t border-line px-5 py-2 text-xs text-faint">
            Coletor por cidade a cada 5 min · último boletim gravado {String(dados.atualizado_em || "").slice(11, 16)} UTC · % na cidade = votos do candidato sobre os válidos da cidade.
          </p>
        )}
      </div>
    </div>
  );
}
