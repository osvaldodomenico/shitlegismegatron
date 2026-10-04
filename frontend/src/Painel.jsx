import { useCallback, useEffect, useState } from "react";
import { useElectionSocket } from "./hooks/useElectionSocket";
import { candidatos as lerCandidatos, num, partido, urlFoto, legendaBoletim, rankingDaLegenda, resumoSituacoes, votosDoPartido, eleitosMatematicos, corProgresso, derrotado } from "./lib/tse";
import * as api from "./lib/api";
import { Foto, CabecalhoTelao, Selo, Final } from "./components/Telao";
import { SeletorCandidatos } from "./components/SeletorCandidatos";
import { IconPlus } from "./components/icons";

/**
 * Painel de telao (1920x1080), da esquerda para a direita:
 *   1. Presidente, Senador e Governador empilhados — sempre os acompanhados
 *      da tela principal (sem selecao, os 3 mais votados).
 *   2+. Uma coluna por RANKING: os mais votados de UMA legenda num cargo
 *      proporcional; `destaque` (numero de urna) e opcional e, quando existe,
 *      entra na lista mesmo fora do top.
 *
 * `perfil` escolhe qual lista de acompanhados (padrao = a da tela principal;
 * "geral" = a do /apuracaogeral, independente). Com `editavel`, cada faixa
 * ganha o botao "Escolher" que abre o seletor e grava nesse perfil — e so
 * nesse perfil.
 */

const MAX_FAIXA = 3;    // linhas por faixa na coluna 1

// Rankings por legenda, um por coluna, na ordem da tela.
const RANKINGS = [
  { cargo: "dep_estadual", titulo: "Deputado Estadual", partido: "REPUBLICANOS", destaque: null,   n: 8 },
  { cargo: "dep_federal",  titulo: "Deputado Federal",  partido: "REPUBLICANOS", destaque: "1055", n: 8 },
];

const fmtPct = (v) => num(v).toFixed(2).replace(".", ",");
const fmtInt = (v) => num(v).toLocaleString("pt-BR");

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
        <div className="h-full rounded-full transition-[width,background-color] duration-700 ease-out"
          style={{ width: `${Math.min(pst, 100)}%`, backgroundColor: corProgresso(pst) }} />
      </div>
    </>
  );
}

function Titulo({ titulo, lugar, data, tamanho = "text-3xl", pct = "text-4xl" }) {
  return (
    <div className="flex items-end justify-between gap-4">
      <h2 className={`flex items-end gap-3 ${tamanho} font-bold leading-none text-muted`}>
        <span>{titulo} <span className="text-primaryLit">· {lugar}</span></span>
        <Final data={data} className="text-xs mb-0.5" />
      </h2>
      <span className={`num font-mono ${pct} font-bold leading-none text-muted`}>
        {fmtPct(num(data?.pst))}<span className="text-xl font-normal text-subtle">%</span>
      </span>
    </div>
  );
}

/* ------------------------------------------ linha compacta (meia coluna e ranking) */

function LinhaCompacta({ cand, proporcao, foto, posicao, destaque, mostrarPartido, projecao = false, apagada = false }) {
  return (
    <li className={`flex items-center gap-3 rounded-xl border px-3 py-1.5 ${
      destaque ? "border-primaryLit bg-primary/20" : "border-line bg-surface"}`}>
      {posicao && (
        <span className={`num w-11 shrink-0 text-right font-mono text-2xl font-bold ${destaque ? "text-primaryLit" : "text-subtle"}`}>
          {posicao}º
        </span>
      )}
      <Foto src={foto} nome={cand.nm} tamanho="h-12 w-12" texto="text-sm" apagada={apagada} />
      <div className="min-w-0 flex-1">
        <div className="flex items-baseline justify-between gap-3">
          <p className={`flex min-w-0 items-center gap-2 truncate text-lg font-semibold leading-tight ${destaque ? "text-primaryLit" : "text-muted"}`}>
            <span className="truncate">{cand.nmu || cand.nm}</span>
            <span className="num shrink-0 rounded bg-elevated px-1.5 py-0.5 font-mono text-sm font-bold text-muted">{cand.n}</span>
            {mostrarPartido && <span className="shrink-0 text-sm font-semibold uppercase text-subtle">{partido(cand)}</span>}
            <Selo cand={cand} tamanho="xs" projecao={projecao} />
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
    <p className="mt-3 rounded-2xl border border-dashed border-line px-6 py-5 text-center text-base text-subtle">
      {connected ? texto : "Reconectando…"}
    </p>
  );
}

/* ------------------------------------- faixas da coluna 1 (pres/sen/gov) */

function Faixa({ titulo, lugar, data, connected, temSelecao, comOutros, aoEscolher, solto = false }) {
  const todos = [...lerCandidatos(data)].sort((a, b) => num(b.vap) - num(a.vap));
  const lista = todos.slice(0, MAX_FAIXA);
  // "outros" so faz sentido sobre a corrida inteira, nao sobre uma selecao.
  const resto = comOutros && !temSelecao ? todos.slice(MAX_FAIXA) : [];
  // Projecao matematica sobre o que o payload traz (com selecao, so os
  // acompanhados contra o total apurado — conservadora).
  const matematicos = eleitosMatematicos(data, data?.v);
  const lider = Math.max(...lista.map((c) => num(c.vap)), 1);
  const origem = temSelecao ? "Acompanhados" : `${MAX_FAIXA} mais votados`;
  const outros = resto.length
    ? ` · outros ${resto.length}: ${fmtPct(resto.reduce((t, c) => t + num(c.pvap), 0))}% dos válidos`
    : "";

  return (
    <section className={`flex min-w-0 flex-col overflow-hidden px-6 py-3 ${solto ? "" : "min-h-0"}`} aria-label={`${titulo} · ${lugar}`}>
      <header>
        <Titulo titulo={titulo} lugar={lugar} data={data} tamanho="text-2xl" pct="text-3xl" />
        <Secoes data={data} />
        <p className="mt-1.5 flex items-center justify-between text-xs uppercase tracking-wider text-faint">
          <span>{origem}{outros}</span>
          {aoEscolher && (
            <button onClick={aoEscolher}
              className="flex h-7 cursor-pointer items-center gap-1 rounded-md border border-line px-2 text-xs font-medium normal-case tracking-normal text-subtle transition-colors duration-150 hover:border-primaryLit hover:text-muted">
              <IconPlus className="h-3.5 w-3.5" />
              {temSelecao ? "Alterar" : "Escolher"}
            </button>
          )}
        </p>
      </header>
      {lista.length === 0 ? (
        <Vazio connected={connected} />
      ) : (
        <ol className={`mt-1.5 flex flex-col gap-1.5 ${solto ? "" : "min-h-0 flex-1"}`}>
          {lista.map((c) => (
            <LinhaCompacta key={c.sqcand || c.seq} cand={c} mostrarPartido
              projecao={matematicos.has(String(c.sqcand))}
              apagada={derrotado(c, matematicos, data?.v)}
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
  const { lista, total, todos } = rankingDaLegenda(lerCandidatos(data), cfg.partido, cfg.destaque, cfg.n);
  const lider = Math.max(...lista.map((c) => num(c.vap)), 1);
  const alvo = lista.find((c) => c.destaque);
  // Assim que o TSE preencher `st`, o resumo da legenda substitui a contagem crua.
  const resumo = resumoSituacoes(todos);
  const vp = votosDoPartido(data, cfg.partido);

  return (
    <section className="flex min-h-0 min-w-0 flex-col overflow-hidden px-6 py-5" aria-label={`${cfg.titulo} · São Paulo · ${cfg.partido}`}>
      <header>
        <Titulo titulo={cfg.titulo} lugar="São Paulo" data={data} />
        <Secoes data={data} />
        <p className="mt-3 flex items-center gap-2 text-sm">
          <span className="rounded bg-elevated px-2 py-0.5 font-semibold uppercase text-muted">{cfg.partido}</span>
          {resumo.length ? (
            <span className="font-semibold text-successLit">
              {resumo.map((r) => `${r.n} ${r.texto}`).join(" · ")}
            </span>
          ) : (
            <span className="text-subtle">Ranking na legenda · {total} candidatos</span>
          )}
          {alvo && (
            <span className="ml-auto rounded-lg border border-primaryLit/40 bg-primary/20 px-2 py-0.5 font-semibold text-primaryLit">
              {alvo.nmu || alvo.nm}: <span className="num font-mono font-bold">{alvo.posicao}º</span> de {total}
            </span>
          )}
        </p>
        {/* Votos do partido na corrida inteira: o numero que decide quantas vagas a legenda leva. */}
        {vp.total > 0 && (
          <dl className="mt-2 flex items-baseline gap-x-5 rounded-xl border border-line bg-elevated/60 px-4 py-2">
            <div>
              <dt className="text-[10px] uppercase tracking-wider text-faint">Votos do partido</dt>
              <dd className="num font-mono text-2xl font-bold leading-none text-muted">
                {fmtInt(vp.total)}
                <span className="ml-2 text-base font-semibold text-primaryLit">{fmtPct(vp.pct)}%</span>
                <span className="ml-1 text-xs font-normal text-subtle">dos válidos</span>
              </dd>
            </div>
            <div className="ml-auto flex gap-x-4 text-right">
              <div>
                <dt className="text-[10px] uppercase tracking-wider text-faint">Nominais</dt>
                <dd className="num font-mono text-sm font-semibold text-subtle">{fmtInt(vp.nominais)}</dd>
              </div>
              <div>
                <dt className="text-[10px] uppercase tracking-wider text-faint">Legenda</dt>
                <dd className="num font-mono text-sm font-semibold text-subtle">{vp.legenda === null ? "—" : fmtInt(vp.legenda)}</dd>
              </div>
              <div>
                <dt className="text-[10px] uppercase tracking-wider text-faint">Vagas</dt>
                <dd className="num font-mono text-sm font-semibold text-successLit">{vp.vagas === null ? "—" : vp.vagas}</dd>
              </div>
            </div>
          </dl>
        )}
      </header>
      {lista.length === 0 ? (
        <Vazio connected={connected} />
      ) : (
        <ol className="mt-3 flex min-h-0 flex-1 flex-col gap-1.5">
          {lista.map((c) => (
            <LinhaCompacta key={c.sqcand || c.seq} cand={c} posicao={c.posicao} destaque={c.destaque}
              apagada={derrotado(c)}
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
function useCorrida(uf, cargo, selecionados = false, perfil = "padrao") {
  const sock = useElectionSocket(uf, cargo, { selecionados, perfil });
  const [selecao, setSelecao] = useState([]);
  const [maximo, setMaximo] = useState(50);
  const recarregar = useCallback(() => {
    api.buscarResultado(uf, cargo, selecionados, perfil).then(sock.setData).catch(() => {});
    if (selecionados) {
      api.buscarSelecao(uf, cargo, perfil)
        .then((s) => { setSelecao(s.sqcands || []); setMaximo(s.maximo || 50); })
        .catch(() => {});
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [uf, cargo, selecionados, perfil]);
  useEffect(() => { recarregar(); }, [recarregar]);
  return { ...sock, uf, cargo, selecao, maximo, temSelecao: selecao.length > 0, recarregar };
}

/** Estado do seletor de candidatos (so no modo editavel). */
function useSeletor(perfil) {
  const [alvo, setAlvo] = useState(null);        // corrida sendo editada
  const [candidatos, setCandidatos] = useState([]);
  const [salvando, setSalvando] = useState(false);
  const [erro, setErro] = useState("");

  const abrir = useCallback(async (corrida) => {
    setErro("");
    setAlvo(corrida);
    try {
      const r = await api.buscarCandidatos(corrida.uf, corrida.cargo);
      setCandidatos(r.candidatos || []);
    } catch {
      setCandidatos([]);
      setErro("Não foi possível carregar a lista de candidatos desta corrida.");
    }
  }, []);

  async function confirmar(sqcands) {
    if (!alvo) return;
    setSalvando(true);
    setErro("");
    try {
      await api.salvarSelecao(alvo.uf, alvo.cargo, sqcands, perfil);
      alvo.recarregar();     // o socket so empurra no proximo boletim; a tela nao pode esperar
      setAlvo(null);
    } catch (e) {
      setErro(e.message);
    } finally {
      setSalvando(false);
    }
  }

  return { alvo, candidatos, salvando, erro, abrir, confirmar, fechar: () => setAlvo(null) };
}

export function Painel({ perfil = "padrao", editavel = false }) {
  const pres = useCorrida("br", "presidente", true, perfil);
  const sen = useCorrida("sp", "senador", true, perfil);
  const gov = useCorrida("sp", "governador", true, perfil);
  const seletor = useSeletor(perfil);
  // RANKINGS e constante de modulo: o numero de hooks nao varia entre renders.
  const rankings = RANKINGS.map((cfg) => useCorrida("sp", cfg.cargo));

  const aoVivo = [pres, sen, gov, ...rankings].every((c) => c.connected);
  const colunas = 1 + RANKINGS.length;

  // Telao (/painel): tudo preso em 1080 de altura, sem rolagem. Editavel
  // (/apuracaogeral): operado num navegador comum, entao a pagina rola e as
  // faixas tem altura natural — nada se sobrepoe em janela menor.
  const raiz = editavel
    ? "flex min-h-screen w-screen flex-col bg-bg text-muted"
    : "flex h-screen w-screen flex-col overflow-hidden bg-bg text-muted";
  const coluna1 = editavel
    ? "flex flex-col divide-y divide-line"
    : "grid min-h-0 grid-rows-3 divide-y divide-line";

  return (
    <div className={raiz}>
      <CabecalhoTelao aoVivo={aoVivo} />

      <main className={`grid flex-1 divide-x divide-line ${editavel ? "" : "min-h-0"}`}
        style={{ gridTemplateColumns: `repeat(${colunas}, minmax(0, 1fr))` }}>
        <div className={coluna1}>
          <Faixa titulo="Presidente" lugar="Brasil" data={pres.data} connected={pres.connected} temSelecao={pres.temSelecao} comOutros
            solto={editavel} aoEscolher={editavel ? () => seletor.abrir(pres) : undefined} />
          <Faixa titulo="Senador" lugar="São Paulo" data={sen.data} connected={sen.connected} temSelecao={sen.temSelecao}
            solto={editavel} aoEscolher={editavel ? () => seletor.abrir(sen) : undefined} />
          <Faixa titulo="Governador" lugar="São Paulo" data={gov.data} connected={gov.connected} temSelecao={gov.temSelecao}
            solto={editavel} aoEscolher={editavel ? () => seletor.abrir(gov) : undefined} />
        </div>

        {RANKINGS.map((cfg, i) => (
          <ColunaRanking key={cfg.cargo} cfg={cfg} data={rankings[i].data} connected={rankings[i].connected} />
        ))}
      </main>

      {editavel && (
        <SeletorCandidatos
          aberto={seletor.alvo !== null}
          aoFechar={seletor.fechar}
          candidatos={seletor.candidatos}
          selecionados={seletor.alvo?.selecao || []}
          maximo={seletor.alvo?.maximo || 50}
          aoConfirmar={seletor.confirmar}
          salvando={seletor.salvando}
          erro={seletor.erro}
        />
      )}
    </div>
  );
}
