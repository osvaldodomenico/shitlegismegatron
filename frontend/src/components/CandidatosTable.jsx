const SITUACAO_COLORS = {
  "Eleito": "text-green-400",
  "Não eleito": "text-gray-400",
  "2º turno": "text-yellow-400",
};

export function CandidatosTable({ candidatos = [] }) {
  if (!candidatos.length) return null;
  const maxVotos = Math.max(...candidatos.map((c) => parseInt(c.vap || 0)));

  return (
    <div className="bg-surface rounded-xl overflow-hidden mb-6">
      <table className="w-full text-sm">
        <thead>
          <tr className="text-gray-500 text-xs uppercase tracking-wider">
            <th className="text-left px-4 py-3">Candidato</th>
            <th className="text-right px-4 py-3">Votos</th>
            <th className="text-right px-4 py-3">%</th>
            <th className="px-4 py-3 w-32">Barra</th>
            <th className="text-left px-4 py-3">Situação</th>
          </tr>
        </thead>
        <tbody>
          {candidatos.map((c) => {
            const votos = parseInt(c.vap || 0);
            const pct = parseFloat(c.pvap?.replace("%", "") || 0);
            const barW = maxVotos > 0 ? (votos / maxVotos) * 100 : 0;
            return (
              <tr key={c.sqcand} className="border-t border-gray-800 hover:bg-gray-900/30">
                <td className="px-4 py-3">
                  <span className="font-medium">{c.nm}</span>
                  <span className="text-gray-500 text-xs ml-2">{c.sg} · nº {c.n}</span>
                </td>
                <td className="px-4 py-3 text-right">{votos.toLocaleString("pt-BR")}</td>
                <td className="px-4 py-3 text-right font-mono">{pct.toFixed(2)}%</td>
                <td className="px-4 py-3">
                  <div className="flex items-center gap-2">
                    <div className="flex-1 h-2 bg-gray-800 rounded-full">
                      <div className="h-2 bg-primary rounded-full" style={{ width: `${barW}%` }} />
                    </div>
                    <span className="text-xs w-10 text-right">{pct.toFixed(1)}%</span>
                  </div>
                </td>
                <td className={`px-4 py-3 ${SITUACAO_COLORS[c.e] || "text-gray-400"}`}>{c.e}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
