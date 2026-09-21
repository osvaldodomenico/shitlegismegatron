import { num } from "../lib/tse";
import { CandidatoCard } from "./CandidatoCard";
import { IconUsers, IconPlus } from "./icons";

const CORES = ["bg-s1", "bg-s2", "bg-s3", "bg-s4", "bg-s5"];
const TEXTO = ["text-s1", "text-s2", "text-s3", "text-s4", "text-s5"];

/** Regras da corrida: o contexto sem o qual nenhuma margem faz sentido. */
function FaixaIndicadores({ ind }) {
  if (!ind || !ind.quociente_eleitoral) return null;
  const item = (rotulo, valor, dica) => (
    <div key={rotulo} className="min-w-0">
      <dt className="text-[10px] uppercase tracking-wider text-faint">{rotulo}</dt>
      <dd className="num font-mono text-sm font-semibold text-muted" title={dica}>{valor}</dd>
    </div>
  );
  return (
    <dl className="mb-4 flex flex-wrap items-start gap-x-6 gap-y-3 rounded-xl border border-line bg-elevated/50 px-4 py-3">
      {item("Quociente eleitoral", ind.quociente_eleitoral.toLocaleString("pt-BR"),
            "Votos válidos divididos pelo número de vagas")}
      {item("Vagas", ind.vagas)}
      {item("Barreira individual", ind.barreira_individual.toLocaleString("pt-BR"),
            "10% do quociente eleitoral — abaixo disso o candidato não se elege")}
      {ind.parcial && (
        <div className="basis-full text-[11px] text-accent">
          Apuração parcial: o quociente ainda vai subir até o fim da totalização.
        </div>
      )}
    </dl>
  );
}

function Vazio({ aoAbrirSeletor, cargoNome }) {
  return (
    <div className="rounded-2xl border border-dashed border-line bg-surface/50 px-6 py-12 text-center">
      <IconUsers className="mx-auto h-10 w-10 text-faint" />
      <h3 className="mt-3 text-base font-semibold text-muted">Nenhum candidato acompanhado</h3>
      <p className="mx-auto mt-1 max-w-sm text-sm text-subtle">
        Escolha até 5 candidatos de {cargoNome} para comparar votos, posição na legenda
        e distância da linha de corte.
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

export function ComparacaoPainel({
  candidatos, indicadores, cargoNome, aoAbrirSeletor, aoRemover, carregando, maximo = 5,
}) {
  if (carregando) {
    return (
      <div className="space-y-3" aria-busy="true" aria-label="Carregando comparativo">
        {[0, 1, 2].map((i) => (
          <div key={i} className="h-32 animate-pulseSoft rounded-xl border border-line bg-surface" />
        ))}
      </div>
    );
  }

  if (!candidatos || candidatos.length === 0) {
    return <Vazio aoAbrirSeletor={aoAbrirSeletor} cargoNome={cargoNome} />;
  }

  const lider = Math.max(...candidatos.map((c) => num(c.vap)), 1);
  const podeAdicionar = candidatos.length < maximo;

  return (
    <section aria-label="Comparativo dos candidatos acompanhados">
      <header className="mb-3 flex items-center justify-between gap-3">
        <h2 className="text-sm font-semibold uppercase tracking-wider text-faint">
          Acompanhando {candidatos.length} de {maximo}
        </h2>
        <button
          onClick={aoAbrirSeletor}
          className="flex h-9 cursor-pointer items-center gap-1.5 rounded-lg border border-line px-3 text-sm font-medium text-subtle transition-colors duration-150 hover:bg-elevated hover:text-muted"
        >
          <IconPlus className="h-4 w-4" />
          {podeAdicionar ? "Adicionar" : "Alterar"}
        </button>
      </header>

      <FaixaIndicadores ind={indicadores} />

      <ol className="space-y-2.5">
        {candidatos.map((c, i) => (
          <CandidatoCard
            key={c.sqcand || c.seq}
            cand={c}
            cor={CORES[i % 5]}
            corTexto={TEXTO[i % 5]}
            proporcao={(num(c.vap) / lider) * 100}
            aoRemover={aoRemover}
          />
        ))}
      </ol>

      {podeAdicionar && (
        <button
          onClick={aoAbrirSeletor}
          className="mt-2.5 flex h-14 w-full cursor-pointer items-center justify-center gap-2 rounded-xl border border-dashed border-line text-sm font-medium text-subtle transition-colors duration-150 hover:border-primaryLit hover:text-muted"
        >
          <IconPlus className="h-4 w-4" />
          Adicionar candidato ({maximo - candidatos.length} vaga(s))
        </button>
      )}

      <p className="mt-3 text-xs text-faint">
        Barras proporcionais ao primeiro colocado da seleção. Percentual sobre os votos válidos.
        A linha de corte usa a situação publicada pelo TSE para cada agremiação.
      </p>
    </section>
  );
}
