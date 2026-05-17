import { StatusBanner } from "./StatusBanner";

const UFS_OPCOES = ["sp", "rj", "mg", "rs", "ba", "pr", "pe", "ce", "pa", "sc"];
const CARGOS_OPCOES = ["governador", "presidente", "senador"];

export function Header({ uf, cargo, connected, onUfChange, onCargoChange }) {
  return (
    <header className="flex flex-wrap items-center justify-between gap-4 mb-8 pb-4 border-b border-gray-800">
      <h1 className="text-xl font-bold tracking-wide">
        🗳️ <span className="text-primary">MEGATRON</span>
      </h1>
      <div className="flex items-center gap-3 flex-wrap">
        <select
          className="bg-surface border border-gray-700 rounded-lg px-3 py-1.5 text-sm text-muted focus:outline-none focus:border-primary"
          value={uf}
          onChange={(e) => onUfChange(e.target.value)}
        >
          {UFS_OPCOES.map((u) => (
            <option key={u} value={u}>{u.toUpperCase()}</option>
          ))}
        </select>
        <select
          className="bg-surface border border-gray-700 rounded-lg px-3 py-1.5 text-sm text-muted focus:outline-none focus:border-primary"
          value={cargo}
          onChange={(e) => onCargoChange(e.target.value)}
        >
          {CARGOS_OPCOES.map((c) => (
            <option key={c} value={c}>{c.charAt(0).toUpperCase() + c.slice(1)}</option>
          ))}
        </select>
        <StatusBanner connected={connected} />
      </div>
    </header>
  );
}
