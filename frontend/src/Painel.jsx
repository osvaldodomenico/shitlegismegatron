import { useEffect } from "react";
import { useElectionSocket } from "./hooks/useElectionSocket";
import { candidatos as lerCandidatos, num, partido, situacao, urlFoto, legendaBoletim, rankingDaLegenda } from "./lib/tse";
import * as api from "./lib/api";
import { IconTrophy } from "./components/icons";
import { Foto, CabecalhoTelao } from "./components/Telao";

/**
 * Painel de telao (1920x1080): Presidente, Governador SP e, na terceira coluna,
 * o ranking de Deputado Federal SP dentro de UMA legenda (os mais votados do
 * partido + o candidato em destaque, mesmo fora do top).
 *
 * Nada e clicavel — a tela fica aberta num monitor e se atualiza sozinha pelo
 * WebSocket.
 */

const CORES = ["bg-s1", "bg-s2", "bg-s3", "bg-s4", "bg-s5", "bg-primaryLit", "bg-subtle", "bg-faint"];
const MAX_LINHAS = 6;

// Pedido de 04/10: Milton Vieira (1055) + os 9 Republicanos mais votados.
const RANKING = { partido: "REPUBLICANOS", destaque: "1055", n: 10 };

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

function LinhaRanking({ cand, proporcao, foto }) {
  const st = situacao(cand);
  const eleito = /eleito/i.test(st) && !/não|nao/i.test(st);
  const alvo = cand.destaque;
  return (
    <li className={`flex items-center gap-3 rounded-xl border px-3 py-1.5 ${
      alvo ? "border-primaryLit bg-primary/20" : "border-line bg-surface"}`}>
      <span className={`num w-11 shrink-0 text-right font-mono text-2xl font-bold ${alvo ? "text-primaryLit" : "text-subtle"}`}>
        {cand.posicao}º
      </span>
      <Foto src={foto} nome={cand.nm} tamanho="h-12 w-12" texto="text-sm" />
      <div className="min-w-0 flex-1">
        <div className="flex items-baseline justify-between gap-3">
          <p className={`flex min-w-0 items-center gap-2 truncate text-lg font-semibold leading-tight ${alvo ? "text-primaryLit" : "text-muted"}`}>
            <span className="truncate">{cand.nmu || cand.nm}</span>
            <span className="num shrink-0 rounded bg-elevated px-1.5 py-0.5 font-mono text-sm font-bold text-muted">{cand.n}</span>
            {eleito && (
              <span className="flex shrink-0 items-center gap-1 rounded bg-success/25 px-1.5 py-0.5 text-xs font-bold uppercase tracking-wider text-successLit">
                <IconTrophy className="h-3.5 w-3.5" />
                Eleito
              </span>
            )}
          </p>
          <p className="num shrink-0 font-mono text-lg font-bold text-muted">
            {fmtPct(cand.pvap)}<span className="text-xs font-normal text-subtle">%</span>
            <span className="ml-2 text-sm font-normal text-subtle">{fmtInt(cand.vap)}</span>
          </p>
        </div>
        <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-elevated">
          <div className={`h-full rounded-full ${alvo ? "bg-primaryLit" : "bg-s1"} transition-[width] duration-700 ease-out`}
            style={{ width: `${Math.max(proporcao, 1)}%` }} />
        </div>
      </div>
    </li>
  );
}

function ColunaRanking({ titulo, lugar, data, connected, ranking }) {
  const pst = num(data?.pst);
  const { lista, total } = ranking;
  const lider = Math.max(...lista.map((c) => num(c.vap)), 1);
  const uf = data?.cdabr || "sp";
  const ele = data?.ele;
  const alvo = lista.find((c) => c.destaque);

  return (
    <section className="flex min-h-0 flex-col px-6 py-5" aria-label={`${titulo} · ${lugar} · ${RANKING.partido}`}>
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
        <p className="mt-3 flex items-center gap-2 text-sm">
          <span className="rounded bg-elevated px-2 py-0.5 font-semibold uppercase text-muted">{RANKING.partido}</span>
          <span className="text-subtle">Ranking na legenda · {total} candidatos</span>
          {alvo && (
            <span className="ml-auto rounded-lg border border-primaryLit/40 bg-primary/20 px-2 py-0.5 font-semibold text-primaryLit">
              {alvo.nmu || alvo.nm}: <span className="num font-mono font-bold">{alvo.posicao}º</span> de {total}
            </span>
          )}
        </p>
      </header>

      {lista.length === 0 ? (
        <p className="mt-10 rounded-2xl border border-dashed border-line px-6 py-12 text-center text-xl text-subtle">
          {connected ? "Aguardando o primeiro boletim do TSE" : "Reconectando…"}
        </p>
      ) : (
        <ol className="mt-3 flex min-h-0 flex-1 flex-col gap-1.5">
          {lista.map((c) => (
            <LinhaRanking key={c.sqcand || c.seq} cand={c}
              proporcao={(num(c.vap) / lider) * 100}
              foto={c.foto || urlFoto(uf, ele, c.sqcand)} />
          ))}
        </ol>
      )}
      <p className="mt-3 text-sm text-faint">
        Barras proporcionais ao 1º da legenda. Percentual sobre os votos válidos da corrida.
      </p>
    </section>
  );
}

export function Painel() {
  // Presidente e governador: corrida inteira (poucos candidatos, payload pequeno).
  const pres = useElectionSocket("br", "presidente");
  const gov = useElectionSocket("sp", "governador");
  // Federais: corrida INTEIRA (~235 KB por boletim) — o ranking da legenda
  // precisa de todos os candidatos do partido, nao so dos acompanhados.
  const fed = useElectionSocket("sp", "dep_federal");

  // Primeira pintura via REST: o socket so empurra quando o TSE muda o boletim.
  useEffect(() => {
    api.buscarResultado("br", "presidente").then(pres.setData).catch(() => {});
    api.buscarResultado("sp", "governador").then(gov.setData).catch(() => {});
    api.buscarResultado("sp", "dep_federal").then(fed.setData).catch(() => {});
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

  const ranking = rankingDaLegenda(lerCandidatos(fed.data), RANKING.partido, RANKING.destaque, RANKING.n);
  const aoVivo = pres.connected && gov.connected && fed.connected;

  return (
    <div className="flex h-screen w-screen flex-col overflow-hidden bg-bg text-muted">
      <CabecalhoTelao aoVivo={aoVivo} />

      <main className="grid min-h-0 flex-1 grid-cols-3 divide-x divide-line">
        <Coluna titulo="Presidente" lugar="Brasil" data={pres.data} connected={pres.connected}
          candidatos={presV.top} rodape={presV.rodape} vazio="Aguardando o primeiro boletim do TSE" />
        <Coluna titulo="Governador" lugar="São Paulo" data={gov.data} connected={gov.connected}
          candidatos={govV.top} rodape={govV.rodape} vazio="Aguardando o primeiro boletim do TSE" />
        <ColunaRanking titulo="Deputado Federal" lugar="São Paulo" data={fed.data} connected={fed.connected}
          ranking={ranking} />
      </main>
    </div>
  );
}
