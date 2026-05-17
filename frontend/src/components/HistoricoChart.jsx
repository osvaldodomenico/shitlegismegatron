import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer } from "recharts";

export function HistoricoChart({ historico = [] }) {
  if (!historico.length) return null;
  const dados = [...historico].reverse().map((h) => ({
    hora: new Date(h.time).toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" }),
    pct: parseFloat(h.pst_pct),
  }));

  return (
    <div className="bg-surface rounded-xl p-4 mb-6">
      <h3 className="text-sm text-gray-400 mb-3">Evolução da apuração</h3>
      <ResponsiveContainer width="100%" height={160}>
        <LineChart data={dados}>
          <XAxis dataKey="hora" tick={{ fill: "#9CA3AF", fontSize: 10 }} />
          <YAxis domain={[0, 100]} tick={{ fill: "#9CA3AF", fontSize: 10 }} unit="%" />
          <Tooltip
            contentStyle={{ background: "#12122a", border: "1px solid #334155", borderRadius: 8 }}
            labelStyle={{ color: "#E8EAF6" }}
          />
          <Line type="monotone" dataKey="pct" stroke="#1565C0" strokeWidth={2} dot={false} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
