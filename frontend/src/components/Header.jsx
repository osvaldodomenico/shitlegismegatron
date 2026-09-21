/**
 * Barra superior: escolha de abrangencia e cargo.
 *
 * A identidade e o estado "ao vivo" moram no Hero — repetir aqui competiria
 * com ele. Esta barra e fixa porque trocar de corrida e a acao mais repetida
 * do painel e nao deve exigir rolar de volta ao topo.
 */
const UFS_OPCOES = ["br", "sp", "rj", "mg", "rs", "ba", "pr", "pe", "ce", "pa", "sc"];
const CARGOS_OPCOES = ["governador", "presidente", "senador", "dep_federal", "dep_estadual"];

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

export function Header({ uf, cargo, onUfChange, onCargoChange }) {
  return (
    <header className="sticky top-0 z-30 border-b border-line bg-bg/85 backdrop-blur-md">
      <nav className="mx-auto flex max-w-6xl items-center gap-3 px-4 py-2.5">
        <label className="sr-only" htmlFor="sel-uf">Abrangência</label>
        <select id="sel-uf" className={campo} value={uf} onChange={(e) => onUfChange(e.target.value)}>
          {UFS_OPCOES.map((u) => (
            <option key={u} value={u}>{u === "br" ? "BRASIL" : u.toUpperCase()}</option>
          ))}
        </select>

        <label className="sr-only" htmlFor="sel-cargo">Cargo</label>
        <select id="sel-cargo" className={`${campo} min-w-0 flex-1 sm:flex-none`} value={cargo} onChange={(e) => onCargoChange(e.target.value)}>
          {CARGOS_OPCOES.map((c) => (
            <option key={c} value={c}>{CARGO_LABELS[c] || c}</option>
          ))}
        </select>
      </nav>
    </header>
  );
}
