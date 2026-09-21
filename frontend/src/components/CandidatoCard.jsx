import { useState } from "react";
import { num, partido, situacao } from "../lib/tse";
import { IconClose, IconAlert } from "./icons";

/**
 * Card de um candidato acompanhado.
 *
 * A barra e proporcional ao LIDER DA SELECAO, nao aos votos validos: em
 * deputado federal o primeiro colocado tem ~4% e barras contra 100% ficariam
 * todas invisiveis. O percentual real continua escrito, para nao enganar.
 */
function Foto({ src, nome, cor }) {
  const [falhou, setFalhou] = useState(false);
  const iniciais = (nome || "?")
    .split(/\s+/).filter(Boolean).slice(0, 2).map((p) => p[0]).join("");

  if (!src || falhou) {
    return (
      <div
        className={`flex h-14 w-14 shrink-0 items-center justify-center rounded-lg bg-elevated text-sm font-semibold ${cor}`}
        aria-hidden="true"
      >
        {iniciais}
      </div>
    );
  }
  return (
    <img
      src={src}
      alt=""
      width={56}
      height={56}
      loading="lazy"
      onError={() => setFalhou(true)}
      className="h-14 w-14 shrink-0 rounded-lg object-cover"
    />
  );
}

const fmt = (n) => Math.abs(n).toLocaleString("pt-BR");

/** Frase da linha de corte — o indicador mais acionavel da tela. */
function LinhaDeCorte({ ind }) {
  if (!ind || ind.vagas_agremiacao === null || ind.margem === null) {
    return (
      <p className="text-xs text-faint">
        Linha de corte ainda indefinida — o TSE não publicou a situação desta agremiação.
      </p>
    );
  }
  const dentro = ind.dentro_do_corte;
  return (
    <p className={`text-xs ${dentro ? "text-successLit" : "text-accent"}`}>
      <span className="num font-mono font-semibold">{fmt(ind.margem)}</span>{" "}
      {dentro ? "votos acima da linha" : "votos abaixo da linha"}
      {ind.referencia && (
        <span className="text-faint"> · ref. {ind.referencia}</span>
      )}
    </p>
  );
}

export function CandidatoCard({ cand, cor, corTexto, proporcao, aoRemover }) {
  const ind = cand.ind;
  const votos = num(cand.vap);
  const pct = num(cand.pvap);
  const st = situacao(cand);
  const eleito = /eleito/i.test(st) && !/não|nao/i.test(st);
  const reprovadoNaBarreira = ind && ind.passou_barreira === false;

  return (
    <li className="rounded-xl border border-line bg-surface p-4">
      <div className="flex items-start gap-3">
        <Foto src={cand.foto} nome={cand.nm} cor={corTexto} />

        <div className="min-w-0 flex-1">
          <div className="flex items-start justify-between gap-2">
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <span className={`h-3 w-3 shrink-0 rounded-sm ${cor}`} aria-hidden="true" />
                <h3 className="truncate text-base font-semibold text-muted">{cand.nm}</h3>
              </div>
              <p className="mt-0.5 truncate text-xs text-faint">
                <span className="num font-mono">{cand.n}</span> · {partido(cand)}
              </p>
            </div>

            <button
              onClick={() => aoRemover(cand.sqcand)}
              aria-label={`Deixar de acompanhar ${cand.nm}`}
              title="Remover"
              className="-m-1.5 flex h-11 w-11 shrink-0 cursor-pointer items-center justify-center rounded-lg text-faint transition-colors duration-150 hover:bg-elevated hover:text-accent"
            >
              <IconClose className="h-4 w-4" />
            </button>
          </div>

          <div className="mt-2 flex items-baseline gap-3">
            <p className={`num font-mono text-2xl font-bold ${corTexto}`}>
              {pct.toFixed(2).replace(".", ",")}
              <span className="text-sm font-normal text-subtle">%</span>
            </p>
            <p className="num font-mono text-sm text-subtle">{votos.toLocaleString("pt-BR")} votos</p>
          </div>
        </div>
      </div>

      <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-elevated">
        <div
          className={`h-full rounded-full ${cor} transition-[width] duration-500 ease-out`}
          style={{ width: `${Math.max(proporcao, 1.5)}%` }}
        />
      </div>

      <div className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-2">
        {st && (
          <span
            className={`rounded px-1.5 py-0.5 text-[11px] font-medium ${
              eleito ? "bg-success/25 text-successLit" : "bg-elevated text-subtle"
            }`}
          >
            {st}
          </span>
        )}
        {ind && (
          <span className="num font-mono text-[11px] text-faint">
            {ind.posicao_agremiacao}º de {ind.total_agremiacao} na legenda
            {ind.vagas_agremiacao !== null && ` · ${ind.vagas_agremiacao} vaga(s)`}
          </span>
        )}
      </div>

      <div className="mt-1.5">
        <LinhaDeCorte ind={ind} />
      </div>

      {reprovadoNaBarreira && (
        <p className="mt-2 flex items-start gap-1.5 rounded-lg bg-accent/10 px-2 py-1.5 text-xs text-accent">
          <IconAlert className="mt-0.5 h-3.5 w-3.5 shrink-0" />
          <span>
            Abaixo da barreira individual: faltam{" "}
            <span className="num font-mono font-semibold">{fmt(ind.falta_barreira)}</span> votos.
            Sem isso não se elege, mesmo com vaga da legenda.
          </span>
        </p>
      )}
    </li>
  );
}
