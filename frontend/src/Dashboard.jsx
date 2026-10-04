import { useEffect, useState } from "react";
import { useElectionSocket } from "./hooks/useElectionSocket";
import { candidatos as lerCandidatos, num, partido, urlFoto, horaAtualizacao, eleitosMatematicos } from "./lib/tse";
import * as api from "./lib/api";
import { Foto, CabecalhoTelao, Selo, Final } from "./components/Telao";

/**
 * Dashboard vertical (1080x1920): os cinco pleitos de uma vez, uma faixa por
 * pleito e cinco cards por faixa.
 *
 * Toda faixa mostra os acompanhados na tela principal; sem acompanhados,
 * os 5 mais votados — nunca uma faixa vazia no telao. `proporcional` so
 * decide se o chip de posicao na legenda aparece.
 */

const PLEITOS = [
  { uf: "br", cargo: "presidente",   titulo: "Presidente",        lugar: "Brasil",    proporcional: false },
  { uf: "sp", cargo: "senador",      titulo: "Senador",           lugar: "São Paulo", proporcional: false },
  { uf: "sp", cargo: "governador",   titulo: "Governador",        lugar: "São Paulo", proporcional: false },
  { uf: "sp", cargo: "dep_federal",  titulo: "Deputado Federal",  lugar: "São Paulo", proporcional: true },
  { uf: "sp", cargo: "dep_estadual", titulo: "Deputado Estadual", lugar: "São Paulo", proporcional: true },
];
const POR_FAIXA = 5;

const fmtPct = (v) => num(v).toFixed(2).replace(".", ",");
const fmtInt = (v) => num(v).toLocaleString("pt-BR");

function Card({ cand, proporcao, foto, proporcional, projecao = false }) {
  const ind = proporcional ? cand.ind : null;
  return (
    <li className="flex min-w-0 flex-col rounded-2xl border border-line bg-surface p-3">
      <div className="flex items-start justify-between gap-2">
        <Foto src={foto} nome={cand.nm} tamanho="h-14 w-14" texto="text-base" />
        <Selo cand={cand} tamanho="xs" projecao={projecao} />
      </div>
      <p className="mt-2.5 line-clamp-2 min-h-[2.25rem] text-base font-semibold leading-tight text-muted" title={cand.nm}>
        {cand.nmu || cand.nm}
      </p>
      <p className="mt-1 flex items-center gap-2 truncate text-sm text-subtle">
        <span className="num rounded bg-elevated px-1.5 py-0.5 font-mono font-bold text-muted">{cand.n}</span>
        <span className="truncate font-medium uppercase">{partido(cand)}</span>
      </p>
      <p className="num mt-2.5 font-mono text-2xl font-bold leading-none text-muted">
        {fmtPct(cand.pvap)}<span className="text-base font-normal text-subtle">%</span>
      </p>
      <p className="num mt-1 font-mono text-sm text-subtle">{fmtInt(cand.vap)} votos</p>
      <div className="mt-2.5 h-1.5 overflow-hidden rounded-full bg-elevated">
        <div className="h-full rounded-full bg-primaryLit transition-[width] duration-700 ease-out"
          style={{ width: `${Math.max(proporcao, 1)}%` }} />
      </div>
      {ind && (
        <p className="mt-2.5 flex items-center gap-1.5 self-start rounded-md border border-primaryLit/40 bg-primary/20 px-2 py-0.5 text-xs font-semibold text-primaryLit">
          <span className="num font-mono text-sm font-bold">{ind.posicao_agremiacao}º</span>
          de {ind.total_agremiacao} na legenda
        </p>
      )}
    </li>
  );
}

function Faixa({ pleito, data, connected, temSelecao }) {
  const pst = num(data?.pst);
  const hora = horaAtualizacao(data);
  const todos = [...lerCandidatos(data)].sort((a, b) => num(b.vap) - num(a.vap));
  const cands = todos.slice(0, POR_FAIXA);
  const lider = Math.max(...cands.map((c) => num(c.vap)), 1);
  const origem = temSelecao ? "Acompanhados" : "5 mais votados";
  const matematicos = pleito.proporcional ? new Set() : eleitosMatematicos(data, data?.v);

  return (
    <section className="flex min-h-0 flex-col overflow-hidden" aria-label={`${pleito.titulo} · ${pleito.lugar}`}>
      <header className="flex items-end justify-between gap-4">
        <div>
          <h2 className="flex items-end gap-3 text-2xl font-bold leading-none text-muted">
            <span>{pleito.titulo} <span className="text-primaryLit">· {pleito.lugar}</span></span>
            <Final data={data} />
          </h2>
          <p className="mt-1.5 text-xs uppercase tracking-wider text-faint">
            {origem}{hora && ` · boletim das ${hora}`}
          </p>
        </div>
        <div className="text-right">
          <p className="num font-mono text-2xl font-bold leading-none text-muted">
            {fmtPct(pst)}<span className="text-sm font-normal text-subtle">%</span>
          </p>
          <p className="mt-1.5 text-xs uppercase tracking-wider text-faint">Seções totalizadas</p>
        </div>
      </header>
      <div className="mt-2 h-1 overflow-hidden rounded-full bg-elevated" role="progressbar"
        aria-valuenow={Math.round(pst)} aria-valuemin={0} aria-valuemax={100} aria-label="Seções totalizadas">
        <div className="h-full rounded-full bg-primaryLit transition-[width] duration-700 ease-out"
          style={{ width: `${Math.min(pst, 100)}%` }} />
      </div>

      {cands.length === 0 ? (
        <p className="mt-3 flex flex-1 items-center justify-center rounded-2xl border border-dashed border-line text-base text-subtle">
          {connected ? "Aguardando o primeiro boletim do TSE" : "Reconectando…"}
        </p>
      ) : (
        <ol className="mt-3 grid flex-1 grid-cols-5 gap-3">
          {cands.map((c) => (
            <Card key={c.sqcand || c.seq} cand={c} proporcional={pleito.proporcional}
              projecao={matematicos.has(String(c.sqcand))}
              proporcao={(num(c.vap) / lider) * 100}
              foto={c.foto || urlFoto(data?.cdabr || pleito.uf, data?.ele, c.sqcand)} />
          ))}
        </ol>
      )}
    </section>
  );
}

/** Um pleito do dashboard: socket + primeira pintura + se ha acompanhados. */
function usePleito(pleito) {
  // Room filtrada: com selecao vazia o servidor manda a corrida inteira.
  const sock = useElectionSocket(pleito.uf, pleito.cargo, { selecionados: true });
  const [temSelecao, setTemSelecao] = useState(false);
  useEffect(() => {
    api.buscarResultado(pleito.uf, pleito.cargo, true).then(sock.setData).catch(() => {});
    api.buscarSelecao(pleito.uf, pleito.cargo)
      .then((s) => setTemSelecao((s.sqcands || []).length > 0))
      .catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  return { ...sock, temSelecao };
}

export function Dashboard() {
  // Hooks em ordem fixa: PLEITOS e constante, entao o numero de hooks nao varia.
  const estados = PLEITOS.map(usePleito);
  const aoVivo = estados.every((e) => e.connected);

  return (
    <div className="flex h-screen w-screen flex-col overflow-hidden bg-bg text-muted">
      <CabecalhoTelao aoVivo={aoVivo} />
      <main className="grid min-h-0 flex-1 grid-rows-5 gap-4 px-8 py-4">
        {PLEITOS.map((p, i) => (
          <Faixa key={p.cargo} pleito={p} data={estados[i].data}
            connected={estados[i].connected} temSelecao={estados[i].temSelecao} />
        ))}
      </main>
    </div>
  );
}
