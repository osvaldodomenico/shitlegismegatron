import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from "recharts";

const CORES = ["#1565C0", "#2E7D32", "#E65100", "#7B1FA2"];

export function ResultadoChart({ candidatos = [] }) {
  if (!candidatos.length) return null;
  const dados = candidatos.map((c) => ({
    nome: c.nm.split(" ")[0],
    votos: parseInt(c.vap || 0),
  }));

  return (
    <div className="bg-surface rounded-xl p-4 mb-6">
      <h3 className="text-sm text-gray-400 mb-3">Distribuição de votos</h3>
      <ResponsiveContainer width="100%" height={200}>
        <BarChart data={dados} layout="vertical" margin={{ left: 10 }}>
          <XAxis type="number" hide />
          <YAxis type="category" dataKey="nome" width={90} tick={{ fill: "#E8EAF6", fontSize: 12 }} />
          <Tooltip
            formatter={(v) => v.toLocaleString("pt-BR")}
            contentStyle={{ background: "#12122a", border: "1px solid #334155", borderRadius: 8 }}
            labelStyle={{ color: "#E8EAF6" }}
          />
          <Bar dataKey="votos" radius={[0, 6, 6, 0]}>
            {dados.map((_, i) => <Cell key={i} fill={CORES[i % CORES.length]} />)}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
