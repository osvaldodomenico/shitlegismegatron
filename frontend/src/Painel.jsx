import { useEffect, useState } from "react";
import { useElectionSocket } from "./hooks/useElectionSocket";
import { candidatos as lerCandidatos, num, partido, situacao, urlFoto, legendaBoletim, rankingDaLegenda } from "./lib/tse";
import * as api from "./lib/api";
import { IconTrophy } from "./components/icons";
import { Foto, CabecalhoTelao } from "./components/Telao";

/**
 * Painel de telao (1920x1080), da esquerda para a direita:
 *   1. Presidente — corrida inteira, os 6 mais votados + "outros".
 *   2. Senador (em cima) e Governador (embaixo) — os acompanhados da tela
 *      principal; sem selecao, os 5 mais votados.
 *   3+. Uma coluna por RANKING: os mais votados de UMA legenda num cargo
 *      proporcional, com o candidato em destaque mesmo fora do top.
 *
 * Nada e clicavel — a tela fica aberta num monitor e se atualiza sozinha pelo
 * WebSocket.
 */

const CORES = ["bg-s1", "bg-s2", "bg-s3", "bg-s4", "bg-s5", "bg-primaryLit", "bg-subtle", "bg-faint"];
const MAX_LINHAS = 6;   // presidente
const MAX_MEIA = 5;     // senador / governador (meia coluna)

// Rankings por legenda, um por coluna. Para ligar a estadual, basta
// acrescentar a entrada com o numero de urna do candidato em destaque.
const RANKINGS = [
  { cargo: "dep_federal", titulo: "Deputado Federal", partido: "REPUBLICANOS", destaque: "1055", n: 10 },
  // { cargo: "dep_estadual", titulo: "Deputado Estadual", partido: "REPUBLICANOS", destaque: "?????", n: 10 },
];

const fmtPct = (v) => num(v).toFixed(2).replace(".", ",");
const fmtInt = (v) => num(v).toLocaleString("pt-BR");
const eEleito = (cand) => { const st = situacao(cand); return /eleito/i.test(st) && !/não|nao/i.test(st); };

function Eleito({ className = "text-sm", icone = "h-4 w-4" }) {
  return (
    <span className={`flex shrink-0 items-center gap-1 rounded bg-success/25 px-2 py-0.5 font-bold uppercase tracking-wider text-successLit ${className}`}>
      <IconTrophy className={icone} />
      Eleito
    </span>
  );
}

function Secoes({ data }) {
  const pst = num(data?.pst);
  return (
    <>
      <div className="mt-3 flex items-baseline justify-between text-xs uppercase tracking-wider text-faint">
        <span>{legendaBoletim(data)}</span>
        <span>Seções totalizadas</span>
      </div>
      <div className="mt-1.5 h-3 overflow-hidden rounded-full bg-elevated" role="progressbar"
        aria-valuenow={Math.round(pst)} aria-valuemin={0} aria-valuemax={100} aria-label="Seções totalizadas">
        <div className="h-full rounded-full bg-gradient-to-r from-primary to-primaryLit transition-[width] duration-700 ease-out"
          style={{ width: `${Math.min(pst, 100)}%` }} />
      </div>
    </>
  );
}

function Titulo({ titulo, lugar, data, tamanho = "text-3xl", pct = "text-4xl" }) {
  return (
    <div className="flex items-end justify-between gap-4">
      <h2 className={`${tamanho} font-bold leading-none text-muted`}>
        {titulo} <span className="text-primaryLit">· {lugar}</span>
      </h2>
      <span className={`num font-mono ${pct} font-bold leading-none text-muted`}>
        {fmtPct(num(data?.pst))}<span className="text-xl font-normal text-subtle">%</span>
      </span>
    </div>
  );
}

/* ----------------------------------------------------------- presidente */

function Linha({ cand, cor, proporcao, foto }) {
  const st = situacao(cand);
  const eleito = eEleito(cand);
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
              {eleito ? <Eleito /> : st && (
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

function ColunaPresidente({ data, connected }) {
  const todos = [...lerCandidatos(data)].sort((a, b) => num(b.vap) - num(a.vap));
  const top = todos.slice(0, MAX_LINHAS);
  const resto = todos.slice(MAX_LINHAS);
  const lider = Math.max(...top.map((c) => num(c.vap)), 1);

  return (
    <section className="flex min-h-0 flex-col px-6 py-5" aria-label="Presidente · Brasil">
      <header>
        <Titulo titulo="Presidente" lugar="Brasil" data={data} />
        <Secoes data={data} />
      </header>
      {top.length === 0 ? (
        <Vazio connected={connected} />
      ) : (
        <ol className="mt-4 flex min-h-0 flex-1 flex-col gap-2.5">
          {top.map((c, i) => (
            <Linha key={c.sqcand || c.seq} cand={c} cor={CORES[i % CORES.length]}
              proporcao={(num(c.vap) / lider) * 100}
              foto={c.foto || urlFoto(data?.cdabr || "br", data?.ele, c.sqcand)} />
          ))}
        </ol>
      )}
      {resto.length > 0 && (
        <p className="mt-3 text-sm text-faint">
          Outros {resto.length} candidatos: {fmtPct(resto.reduce((s, c) => s + num(c.pvap), 0))}% dos votos válidos
        </p>
      )}
    </section>
  );
}

/* ------------------------------------------ linha compacta (meia coluna e ranking) */

function LinhaCompacta({ cand, proporcao, foto, posicao, destaque, mostrarPartido }) {
  const st = situacao(cand);
  const eleito = eEleito(cand);
  return (
    <li className={`flex items-center gap-3 rounded-xl border px-3 py-1.5 ${
      destaque ? "border-primaryLit bg-primary/20" : "border-line bg-surface"}`}>
      {posicao && (
        <span className={`num w-11 shrink-0 text-right font-mono text-2xl font-bold ${destaque ? "text-primaryLit" : "text-subtle"}`}>
          {posicao}º
        </span>
      )}
      <Foto src={foto} nome={cand.nm} tamanho="h-12 w-12" texto="text-sm" />
      <div className="min-w-0 flex-1">
        <div className="flex items-baseline justify-between gap-3">
          <p className={`flex min-w-0 items-center gap-2 truncate text-lg font-semibold leading-tight ${destaque ? "text-primaryLit" : "text-muted"}`}>
            <span className="truncate">{cand.nmu || cand.nm}</span>
            <span className="num shrink-0 rounded bg-elevated px-1.5 py-0.5 font-mono text-sm font-bold text-muted">{cand.n}</span>
            {mostrarPartido && <span className="shrink-0 text-sm font-semibold uppercase text-subtle">{partido(cand)}</span>}
            {eleito ? <Eleito className="text-xs" icone="h-3.5 w-3.5" /> : (!posicao && st) && (
              <span className="shrink-0 rounded bg-elevated px-1.5 py-0.5 text-xs font-medium text-subtle">{st}</span>
            )}
          </p>
          <p className="num shrink-0 font-mono text-lg font-bold text-muted">
            {fmtPct(cand.pvap)}<span className="text-xs font-normal text-subtle">%</span>
            <span className="ml-2 text-sm font-normal text-subtle">{fmtInt(cand.vap)}</span>
          </p>
        </div>
        <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-elevated">
          <div className={`h-full rounded-full ${destaque ? "bg-primaryLit" : "bg-s1"} transition-[width] duration-700 ease-out`}
            style={{ width: `${Math.max(proporcao, 1)}%` }} />
        </div>
      </div>
    </li>
  );
}

function Vazio({ connected, texto = "Aguardando o primeiro boletim do TSE" }) {
  return (
    <p className="mt-6 rounded-2xl border border-dashed border-line px-6 py-8 text-center text-lg text-subtle">
      {connected ? texto : "Reconectando…"}
    </p>
  );
}

/* ------------------------------------------------- senador / governador */

function MeiaColuna({ titulo, lugar, data, connected, temSelecao }) {
  const todos = [...lerCandidatos(data)].sort((a, b) => num(b.vap) - num(a.vap));
  const lista = todos.slice(0, MAX_MEIA);
  const lider = Math.max(...lista.map((c) => num(c.vap)), 1);
  const origem = temSelecao ? "Acompanhados" : `${MAX_MEIA} mais votados`;

  return (
    <section className="flex min-h-0 flex-col px-6 py-4" aria-label={`${titulo} · ${lugar}`}>
      <header>
        <Titulo titulo={titulo} lugar={lugar} data={data} tamanho="text-2xl" pct="text-3xl" />
        <Secoes data={data} />
        <p className="mt-2 text-xs uppercase tracking-wider text-faint">{origem}</p>
      </header>
      {lista.length === 0 ? (
        <Vazio connected={connected} />
      ) : (
        <ol className="mt-2 flex min-h-0 flex-1 flex-col gap-1.5">
          {lista.map((c) => (
            <LinhaCompacta key={c.sqcand || c.seq} cand={c} mostrarPartido
              proporcao={(num(c.vap) / lider) * 100}
              foto={c.foto || urlFoto(data?.cdabr || "sp", data?.ele, c.sqcand)} />
          ))}
        </ol>
      )}
    </section>
  );
}

/* ------------------------------------------------------ ranking por legenda */

function ColunaRanking({ cfg, data, connected }) {
  const { lista, total } = rankingDaLegenda(lerCandidatos(data), cfg.partido, cfg.destaque, cfg.n);
  const lider = Math.max(...lista.map((c) => num(c.vap)), 1);
  const alvo = lista.find((c) => c.destaque);

  return (
    <section className="flex min-h-0 flex-col px-6 py-5" aria-label={`${cfg.titulo} · São Paulo · ${cfg.partido}`}>
      <header>
        <Titulo titulo={cfg.titulo} lugar="São Paulo" data={data} />
        <Secoes data={data} />
        <p className="mt-3 flex items-center gap-2 text-sm">
          <span className="rounded bg-elevated px-2 py-0.5 font-semibold uppercase text-muted">{cfg.partido}</span>
          <span className="text-subtle">Ranking na legenda · {total} candidatos</span>
          {alvo && (
            <span className="ml-auto rounded-lg border border-primaryLit/40 bg-primary/20 px-2 py-0.5 font-semibold text-primaryLit">
              {alvo.nmu || alvo.nm}: <span className="num font-mono font-bold">{alvo.posicao}º</span> de {total}
            </span>
          )}
        </p>
      </header>
      {lista.length === 0 ? (
        <Vazio connected={connected} />
      ) : (
        <ol className="mt-3 flex min-h-0 flex-1 flex-col gap-1.5">
          {lista.map((c) => (
            <LinhaCompacta key={c.sqcand || c.seq} cand={c} posicao={c.posicao} destaque={c.destaque}
              proporcao={(num(c.vap) / lider) * 100}
              foto={c.foto || urlFoto(data?.cdabr || "sp", data?.ele, c.sqcand)} />
          ))}
        </ol>
      )}
      <p className="mt-3 text-sm text-faint">
        Barras proporcionais ao 1º da legenda. Percentual sobre os votos válidos da corrida.
      </p>
    </section>
  );
}

/* ------------------------------------------------------------------ dados */

/** Socket + primeira pintura via REST (o socket so empurra quando o TSE muda). */
function useCorrida(uf, cargo, selecionados = false) {
  const sock = useElectionSocket(uf, cargo, { selecionados });
  const [temSelecao, setTemSelecao] = useState(false);
  useEffect(() => {
    api.buscarResultado(uf, cargo, selecionados).then(sock.setData).catch(() => {});
    if (selecionados) {
      api.buscarSelecao(uf, cargo).then((s) => setTemSelecao((s.sqcands || []).length > 0)).catch(() => {});
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  return { ...sock, temSelecao };
}

export function Painel() {
  const pres = useCorrida("br", "presidente");
  const sen = useCorrida("sp", "senador", true);
  const gov = useCorrida("sp", "governador", true);
  // RANKINGS e constante de modulo: o numero de hooks nao varia entre renders.
  const rankings = RANKINGS.map((cfg) => useCorrida("sp", cfg.cargo));

  const aoVivo = [pres, sen, gov, ...rankings].every((c) => c.connected);
  const colunas = 2 + RANKINGS.length;

  return (
    <div className="flex h-screen w-screen flex-col overflow-hidden bg-bg text-muted">
      <CabecalhoTelao aoVivo={aoVivo} />

      <main className="grid min-h-0 flex-1 divide-x divide-line"
        style={{ gridTemplateColumns: `repeat(${colunas}, minmax(0, 1fr))` }}>
        <ColunaPresidente data={pres.data} connected={pres.connected} />

        <div className="grid min-h-0 grid-rows-2 divide-y divide-line">
          <MeiaColuna titulo="Senador" lugar="São Paulo" data={sen.data} connected={sen.connected} temSelecao={sen.temSelecao} />
          <MeiaColuna titulo="Governador" lugar="São Paulo" data={gov.data} connected={gov.connected} temSelecao={gov.temSelecao} />
        </div>

        {RANKINGS.map((cfg, i) => (
          <ColunaRanking key={cfg.cargo} cfg={cfg} data={rankings[i].data} connected={rankings[i].connected} />
        ))}
      </main>
    </div>
  );
}
