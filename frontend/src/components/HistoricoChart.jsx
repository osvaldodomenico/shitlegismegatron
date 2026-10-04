import { num } from "../lib/tse";
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer } from "recharts";

export function HistoricoChart({ historico = [] }) {
  if (!historico.length) return null;
  const dados = [...historico].reverse().map((h) => ({
    hora: new Date(h.time).toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" }),
    pct: num(h.pst_pct),
  }));

  return (
    <div className="bg-surface rounded-xl p-4 mb-6 text-faint">
      <h3 className="text-sm text-subtle mb-3">Evolução da apuração</h3>
      <ResponsiveContainer width="100%" height={160}>
        <LineChart data={dados}>
          <XAxis dataKey="hora" tick={{ fill: "currentColor", fontSize: 10 }} />
          <YAxis domain={[0, 100]} tick={{ fill: "currentColor", fontSize: 10 }} unit="%" />
          <Tooltip
            contentStyle={{ background: "rgb(var(--c-surface))", border: "1px solid rgb(var(--c-line))", borderRadius: 8 }}
            labelStyle={{ color: "rgb(var(--c-muted))" }}
          />
          <Line type="monotone" dataKey="pct" stroke="#1565C0" strokeWidth={2} dot={false} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
