import { num } from "../lib/tse";
import { IconBallot } from "./icons";

/**
 * Abertura do painel: identidade, estado da conexao e os numeros que dao
 * contexto a tudo que vem abaixo (secoes totalizadas, comparecimento,
 * abstencao, votos validos).
 *
 * O percentual de secoes e a informacao mais importante da tela — sem ele,
 * qualquer diferenca entre candidatos pode ser ruido de apuracao parcial.
 */
function Metrica({ rotulo, valor, sufixo, destaque }) {
  return (
    <div className="rounded-xl border border-line bg-elevated/60 px-4 py-3">
      <dt className="text-[11px] uppercase tracking-wider text-faint">{rotulo}</dt>
      <dd className={`num mt-1 font-mono text-xl font-semibold ${destaque ? "text-accent" : "text-muted"}`}>
        {valor}
        {sufixo && <span className="ml-0.5 text-sm font-normal text-subtle">{sufixo}</span>}
      </dd>
    </div>
  );
}

const inteiro = (v) => num(v).toLocaleString("pt-BR");

export function Hero({ data, uf, ufNome, cargoNome, connected, hora }) {
  const pst = num(data?.pst);

  return (
    <section className="relative overflow-hidden border-b border-line">
      {/* Brilho de fundo puramente decorativo — nao carrega informacao. */}
      <div
        aria-hidden="true"
        className="pointer-events-none absolute -top-32 left-1/2 h-64 w-[42rem] -translate-x-1/2 rounded-full bg-primary/20 blur-3xl"
      />
      <div className="relative mx-auto max-w-6xl px-4 py-8 sm:py-10">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="flex items-center gap-2 text-sm font-medium text-primaryLit">
              <IconBallot className="h-5 w-5" />
              MEGATRON
            </p>
            <h1 className="mt-2 text-3xl font-bold leading-tight text-muted sm:text-4xl">
              {cargoNome}
              <span className="block text-subtle sm:inline sm:before:content-['_·_']">
                {ufNome}
              </span>
            </h1>
            <p className="mt-1 text-sm text-faint">
              {hora ? `Dados do TSE, atualizados às ${hora}` : "Aguardando primeiro boletim"}
            </p>
          </div>

          {/* Estado da conexao: cor + texto + ponto. Nunca so a cor. */}
          <div
            role="status"
            aria-live="polite"
            className={`flex items-center gap-2 rounded-full border px-3 py-1.5 text-sm font-medium ${
              connected
                ? "border-accent/40 bg-accent/10 text-accent"
                : "border-line bg-elevated text-subtle"
            }`}
          >
            <span
              className={`h-2 w-2 rounded-full ${connected ? "bg-accent animate-pulseSoft" : "bg-faint"}`}
              aria-hidden="true"
            />
            {connected ? "Ao vivo" : "Reconectando…"}
          </div>
        </div>

        {/* Barra de secoes totalizadas */}
        <div className="mt-7">
          <div className="mb-1.5 flex items-baseline justify-between">
            <span className="text-xs uppercase tracking-wider text-faint">Seções totalizadas</span>
            <span className="num font-mono text-2xl font-bold text-muted">
              {pst.toFixed(2).replace(".", ",")}<span className="text-base text-subtle">%</span>
            </span>
          </div>
          <div
            className="h-2 overflow-hidden rounded-full bg-elevated"
            role="progressbar"
            aria-valuenow={Math.round(pst)}
            aria-valuemin={0}
            aria-valuemax={100}
            aria-label="Percentual de seções totalizadas"
          >
            <div
              className="h-full rounded-full bg-gradient-to-r from-primary to-primaryLit transition-[width] duration-500 ease-out"
              style={{ width: `${Math.min(pst, 100)}%` }}
            />
          </div>
        </div>

        <dl className="mt-6 grid grid-cols-2 gap-3 sm:grid-cols-4">
          <Metrica rotulo="Comparecimento" valor={inteiro(data?.c)} />
          <Metrica rotulo="Abstenção" valor={num(data?.pa).toFixed(2).replace(".", ",")} sufixo="%" />
          <Metrica rotulo="Votos válidos" valor={inteiro(data?.vv)} />
          <Metrica rotulo="Brancos e nulos" valor={inteiro(num(data?.vb) + num(data?.vn))} />
        </dl>
      </div>
    </section>
  );
}
