/**
 * Barra superior: escolha de abrangencia e cargo.
 *
 * A identidade e o estado "ao vivo" moram no Hero — repetir aqui competiria
 * com ele. Esta barra e fixa porque trocar de corrida e a acao mais repetida
 * do painel e nao deve exigir rolar de volta ao topo.
 */
export const CARGO_LABELS = {
  governador:   "Governador",
  presidente:   "Presidente",
  senador:      "Senador",
  dep_federal:  "Deputado Federal",
  dep_estadual: "Deputado Estadual",
};

const campo =
  "h-11 cursor-pointer rounded-lg border border-line bg-surface px-3 text-sm " +
  "text-muted transition-colors duration-150 hover:border-primaryLit " +
  "focus:border-primaryLit focus:outline-none";

export function Header({ uf, cargo, corridas, onUfChange, onCargoChange }) {
  // Listas vindas de /corridas: o seletor nao pode oferecer combinacao que o
  // backend nao coleta — era o que deixava a tela em "sem boletim" sem
  // explicar o porque.
  const ufs = [...new Set(corridas.map((c) => c.uf))];
  const cargosDaUf = corridas.filter((c) => c.uf === uf);
  const nomeUf = corridas.find((c) => c.uf === uf)?.uf_nome;

  if (corridas.length === 0) return null;

  return (
    <header className="sticky top-0 z-30 border-b border-line bg-bg/85 backdrop-blur-md">
      <nav className="mx-auto flex max-w-6xl items-center gap-3 px-4 py-2.5" aria-label={`Corrida: ${nomeUf || uf}`}>
        <label className="sr-only" htmlFor="sel-uf">Abrangência</label>
        <select id="sel-uf" className={campo} value={uf} onChange={(e) => onUfChange(e.target.value)}>
          {ufs.map((u) => (
            <option key={u} value={u}>
              {corridas.find((c) => c.uf === u)?.uf_nome || u.toUpperCase()}
            </option>
          ))}
        </select>

        <label className="sr-only" htmlFor="sel-cargo">Cargo</label>
        <select id="sel-cargo" className={`${campo} min-w-0 flex-1 sm:flex-none`} value={cargo} onChange={(e) => onCargoChange(e.target.value)}>
          {cargosDaUf.map((c) => (
            <option key={c.cargo} value={c.cargo}>{c.cargo_nome}</option>
          ))}
        </select>
      </nav>
    </header>
  );
}
