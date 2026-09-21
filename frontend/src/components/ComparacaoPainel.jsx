import { num, partido, situacao } from "../lib/tse";
import { IconUsers, IconPlus } from "./icons";

/**
 * Comparacao ao vivo dos candidatos acompanhados.
 *
 * As barras sao proporcionais ao LIDER DA SELECAO, nao ao total de votos
 * validos: com deputado federal o maior tem ~4% e barras contra 100%
 * ficariam todas invisiveis. O percentual real (contra os validos) continua
 * escrito ao lado, para nao enganar a leitura.
 */
const CORES = ["bg-s1", "bg-s2", "bg-s3", "bg-s4", "bg-s5"];
const TEXTO = ["text-s1", "text-s2", "text-s3", "text-s4", "text-s5"];

function Vazio({ aoAbrirSeletor, cargoNome }) {
  return (
    <div className="rounded-2xl border border-dashed border-line bg-surface/50 px-6 py-12 text-center">
      <IconUsers className="mx-auto h-10 w-10 text-faint" />
      <h3 className="mt-3 text-base font-semibold text-muted">Nenhum candidato acompanhado</h3>
      <p className="mx-auto mt-1 max-w-sm text-sm text-subtle">
        Escolha até 5 candidatos de {cargoNome} para ver votos e percentual lado a lado,
        atualizando ao vivo.
      </p>
      <button
        onClick={aoAbrirSeletor}
        className="mt-5 inline-flex h-11 cursor-pointer items-center gap-2 rounded-lg bg-primary px-5 text-sm font-semibold text-white transition-colors duration-150 hover:bg-primaryLit"
      >
        <IconPlus className="h-4 w-4" />
        Escolher candidatos
      </button>
    </div>
  );
}

export function ComparacaoPainel({ candidatos, cargoNome, aoAbrirSeletor, carregando }) {
  if (carregando) {
    return (
      <div className="space-y-3" aria-busy="true" aria-label="Carregando comparativo">
        {[0, 1, 2].map((i) => (
          <div key={i} className="h-20 animate-pulseSoft rounded-xl border border-line bg-surface" />
        ))}
      </div>
    );
  }

  if (!candidatos || candidatos.length === 0) {
    return <Vazio aoAbrirSeletor={aoAbrirSeletor} cargoNome={cargoNome} />;
  }

  const lider = Math.max(...candidatos.map((c) => num(c.vap)), 1);

  return (
    <section aria-label="Comparativo dos candidatos acompanhados">
      <header className="mb-3 flex items-center justify-between gap-3">
        <h2 className="text-sm font-semibold uppercase tracking-wider text-faint">
          Acompanhando {candidatos.length}
        </h2>
        <button
          onClick={aoAbrirSeletor}
          className="flex h-9 cursor-pointer items-center gap-1.5 rounded-lg border border-line px-3 text-sm font-medium text-subtle transition-colors duration-150 hover:bg-elevated hover:text-muted"
        >
          <IconPlus className="h-4 w-4" />
          Alterar
        </button>
      </header>

      <ol className="space-y-2.5">
        {candidatos.map((c, i) => {
          const votos = num(c.vap);
          const pct = num(c.pvap);
          const st = situacao(c);
          const eleito = /eleito/i.test(st) && !/não|nao/i.test(st);
          return (
            <li
              key={c.sqcand || c.seq}
              className="rounded-xl border border-line bg-surface p-4 transition-colors duration-150 hover:border-line/80"
            >
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    {/* Quadrado de cor + numero: a cor nunca e o unico sinal. */}
                    <span className={`h-3 w-3 shrink-0 rounded-sm ${CORES[i % 5]}`} aria-hidden="true" />
                    <h3 className="truncate text-base font-semibold text-muted">{c.nm}</h3>
                  </div>
                  <p className="mt-0.5 truncate pl-5 text-xs text-faint">
                    <span className="num font-mono">{c.n}</span> · {partido(c)}
                  </p>
                </div>
                <div className="shrink-0 text-right">
                  <p className={`num font-mono text-xl font-bold ${TEXTO[i % 5]}`}>
                    {pct.toFixed(2).replace(".", ",")}
                    <span className="text-sm font-normal text-subtle">%</span>
                  </p>
                  <p className="num font-mono text-xs text-faint">
                    {votos.toLocaleString("pt-BR")} votos
                  </p>
                </div>
              </div>

              <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-elevated">
                <div
                  className={`h-full rounded-full ${CORES[i % 5]} transition-[width] duration-500 ease-out`}
                  style={{ width: `${Math.max((votos / lider) * 100, 1.5)}%` }}
                />
              </div>

              {st && (
                <p className="mt-2">
                  <span
                    className={`inline-block rounded px-1.5 py-0.5 text-[11px] font-medium ${
                      eleito ? "bg-success/25 text-successLit" : "bg-elevated text-subtle"
                    }`}
                  >
                    {st}
                  </span>
                </p>
              )}
            </li>
          );
        })}
      </ol>

      <p className="mt-3 text-xs text-faint">
        Barras proporcionais ao primeiro colocado da seleção. O percentual é sobre o total de votos válidos.
      </p>
    </section>
  );
}
