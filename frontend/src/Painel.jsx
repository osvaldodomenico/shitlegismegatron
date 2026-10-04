import { useEffect } from "react";
import { useElectionSocket } from "./hooks/useElectionSocket";
import { candidatos as lerCandidatos, num, partido, situacao, urlFoto, legendaBoletim } from "./lib/tse";
import * as api from "./lib/api";
import { IconTrophy } from "./components/icons";
import { Foto, CabecalhoTelao } from "./components/Telao";

/**
 * Painel de telao (1920x1080): Presidente, Governador SP e Deputado Federal SP
 * lado a lado.
 *
 * Nada e clicavel — a tela fica aberta num monitor e se atualiza sozinha pelo
 * WebSocket. A selecao de federais e a mesma da tela principal; e la que se
 * escolhe quem aparece aqui.
 */

const CORES = ["bg-s1", "bg-s2", "bg-s3", "bg-s4", "bg-s5", "bg-primaryLit", "bg-subtle", "bg-faint"];
const MAX_LINHAS = 6;

const fmtPct = (v) => num(v).toFixed(2).replace(".", ",");
const fmtInt = (v) => num(v).toLocaleString("pt-BR");

function Linha({ cand, cor, proporcao, foto }) {
  const st = situacao(cand);
  const eleito = /eleito/i.test(st) && !/não|nao/i.test(st);
  const ind = cand.ind;
  return (
    <li className="flex items-center gap-4 rounded-2xl border border-line bg-surface px-4 py-3">
      <Foto src={foto} nome={cand.nm} />
      <div className="min-w-0 flex-1">
        <div className="flex items-baseline justify-between gap-4">
          <div className="min-w-0">
            <p className="truncate text-xl font-semibold leading-tight text-muted">{cand.nmu || cand.nm}</p>
            <p className="mt-1 flex items-center gap-2.5 truncate text-base text-subtle">
              <span className="num rounded bg-elevated px-2 py-0.5 font-mono text-lg font-bold text-muted">{cand.n}</span>
              <span className="font-semibold uppercase">{partido(cand)}</span>
              {ind && (
                <span className="flex items-center gap-1 rounded-lg border border-primaryLit/40 bg-primary/20 px-2 py-0.5 text-sm font-semibold text-primaryLit">
                  <span className="num font-mono text-base font-bold">{ind.posicao_agremiacao}º</span>
                  de {ind.total_agremiacao} na legenda
                </span>
              )}
              {eleito ? (
                <span className="flex items-center gap-1.5 rounded bg-success/25 px-2 py-0.5 text-sm font-bold uppercase tracking-wider text-successLit">
                  <IconTrophy className="h-4 w-4" />
                  Eleito
                </span>
              ) : st && (
                <span className="rounded bg-elevated px-2 py-0.5 text-sm font-medium text-subtle">{st}</span>
              )}
            </p>
          </div>
          <div className="shrink-0 text-right">
            <p className="num font-mono text-3xl font-bold leading-none text-muted">
              {fmtPct(cand.pvap)}<span className="text-lg font-normal text-subtle">%</span>
            </p>
            <p className="num mt-1 font-mono text-sm text-subtle">{fmtInt(cand.vap)} votos</p>
          </div>
        </div>
        <div className="mt-2.5 h-2.5 overflow-hidden rounded-full bg-elevated">
          <div className={`h-full rounded-full ${cor} transition-[width] duration-700 ease-out`}
            style={{ width: `${Math.max(proporcao, 1)}%` }} />
        </div>
      </div>
    </li>
  );
}

function Coluna({ titulo, lugar, data, connected, candidatos, rodape, vazio }) {
  const pst = num(data?.pst);
  const lider = Math.max(...candidatos.map((c) => num(c.vap)), 1);
  const uf = data?.cdabr || "br";
  const ele = data?.ele;

  return (
    <section className="flex min-h-0 flex-col px-6 py-5" aria-label={`${titulo} · ${lugar}`}>
      <header>
        <div className="flex items-end justify-between gap-4">
          <h2 className="text-3xl font-bold leading-none text-muted">
            {titulo} <span className="text-primaryLit">· {lugar}</span>
          </h2>
          <span className="num font-mono text-4xl font-bold leading-none text-muted">
            {fmtPct(pst)}<span className="text-xl font-normal text-subtle">%</span>
          </span>
        </div>
        <div className="mt-3 flex items-baseline justify-between text-xs uppercase tracking-wider text-faint">
          <span>{legendaBoletim(data)}</span>
          <span>Seções totalizadas</span>
        </div>
        <div className="mt-1.5 h-3 overflow-hidden rounded-full bg-elevated" role="progressbar"
          aria-valuenow={Math.round(pst)} aria-valuemin={0} aria-valuemax={100} aria-label="Seções totalizadas">
          <div className="h-full rounded-full bg-gradient-to-r from-primary to-primaryLit transition-[width] duration-700 ease-out"
            style={{ width: `${Math.min(pst, 100)}%` }} />
        </div>
      </header>

      {candidatos.length === 0 ? (
        <p className="mt-10 rounded-2xl border border-dashed border-line px-6 py-12 text-center text-xl text-subtle">
          {connected ? vazio : "Reconectando…"}
        </p>
      ) : (
        <ol className="mt-4 flex min-h-0 flex-1 flex-col gap-2.5">
          {candidatos.map((c, i) => (
            <Linha key={c.sqcand || c.seq} cand={c} cor={CORES[i % CORES.length]}
              proporcao={(num(c.vap) / lider) * 100}
              foto={c.foto || urlFoto(uf, ele, c.sqcand)} />
          ))}
        </ol>
      )}
      {rodape && <p className="mt-3 text-sm text-faint">{rodape}</p>}
    </section>
  );
}

export function Painel() {
  // Presidente e governador: corrida inteira (poucos candidatos, payload pequeno).
  const pres = useElectionSocket("br", "presidente");
  const gov = useElectionSocket("sp", "governador");
  // Federais: so os acompanhados — a room filtrada entrega ~2 KB em vez de ~235 KB.
  const fed = useElectionSocket("sp", "dep_federal", { selecionados: true });

  // Primeira pintura via REST: o socket so empurra quando o TSE muda o boletim.
  useEffect(() => {
    api.buscarResultado("br", "presidente").then(pres.setData).catch(() => {});
    api.buscarResultado("sp", "governador").then(gov.setData).catch(() => {});
    api.buscarResultado("sp", "dep_federal", true).then(fed.setData).catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Corrida majoritaria: os mais votados cabem na tela; o resto vira uma linha.
  function recortar(data) {
    const todos = [...lerCandidatos(data)].sort((a, b) => num(b.vap) - num(a.vap));
    const resto = todos.slice(MAX_LINHAS);
    const rodape = resto.length
      ? `Outros ${resto.length} candidatos: ${fmtPct(resto.reduce((s, c) => s + num(c.pvap), 0))}% dos votos válidos`
      : null;
    return { top: todos.slice(0, MAX_LINHAS), rodape };
  }
  const presV = recortar(pres.data);
  const govV = recortar(gov.data);

  const feds = [...lerCandidatos(fed.data)].sort((a, b) => num(b.vap) - num(a.vap));
  const aoVivo = pres.connected && gov.connected && fed.connected;

  return (
    <div className="flex h-screen w-screen flex-col overflow-hidden bg-bg text-muted">
      <CabecalhoTelao aoVivo={aoVivo} />

      <main className="grid min-h-0 flex-1 grid-cols-3 divide-x divide-line">
        <Coluna titulo="Presidente" lugar="Brasil" data={pres.data} connected={pres.connected}
          candidatos={presV.top} rodape={presV.rodape} vazio="Aguardando o primeiro boletim do TSE" />
        <Coluna titulo="Governador" lugar="São Paulo" data={gov.data} connected={gov.connected}
          candidatos={govV.top} rodape={govV.rodape} vazio="Aguardando o primeiro boletim do TSE" />
        <Coluna titulo="Deputado Federal" lugar="São Paulo" data={fed.data} connected={fed.connected}
          candidatos={feds} rodape={feds.length ? "Barras proporcionais ao primeiro colocado da seleção. Percentual sobre os votos válidos." : null}
          vazio="Nenhum candidato acompanhado — escolha os deputados na tela principal" />
      </main>
    </div>
  );
}
