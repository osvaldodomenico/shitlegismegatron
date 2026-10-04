import { num } from "../lib/tse";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from "recharts";

const CORES = ["#1565C0", "#2E7D32", "#E65100", "#7B1FA2"];

export function ResultadoChart({ candidatos = [] }) {
  if (!candidatos.length) return null;
  const dados = candidatos.map((c) => ({
    nome: c.nm.split(" ")[0],
    votos: num(c.vap),
  }));

  return (
    <div className="bg-surface rounded-xl p-4 mb-6 text-muted">
      <h3 className="text-sm text-subtle mb-3">Distribuição de votos</h3>
      <ResponsiveContainer width="100%" height={200}>
        <BarChart data={dados} layout="vertical" margin={{ left: 10 }}>
          <XAxis type="number" hide />
          <YAxis type="category" dataKey="nome" width={90} tick={{ fill: "currentColor", fontSize: 12 }} />
          <Tooltip
            formatter={(v) => v.toLocaleString("pt-BR")}
            contentStyle={{ background: "rgb(var(--c-surface))", border: "1px solid rgb(var(--c-line))", borderRadius: 8 }}
            labelStyle={{ color: "rgb(var(--c-muted))" }}
          />
          <Bar dataKey="votos" radius={[0, 6, 6, 0]}>
            {dados.map((_, i) => <Cell key={i} fill={CORES[i % CORES.length]} />)}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
