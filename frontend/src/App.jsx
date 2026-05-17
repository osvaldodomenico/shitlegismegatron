import { useState, useEffect } from "react";
import { useElectionSocket } from "./hooks/useElectionSocket";
import { Header } from "./components/Header";
import { ProgressBar } from "./components/ProgressBar";
import { CandidatosTable } from "./components/CandidatosTable";
import { ResultadoChart } from "./components/ResultadoChart";
import { HistoricoChart } from "./components/HistoricoChart";

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

export default function App() {
  const [uf, setUf] = useState("sp");
  const [cargo, setCargo] = useState("governador");
  const [historico, setHistorico] = useState([]);

  const { data, connected } = useElectionSocket(uf, cargo);
  const estado = data?.e?.[0];

  useEffect(() => {
    fetch(`${API_URL}/historico/${uf}/${cargo}?ultimas=30`)
      .then((r) => r.json())
      .then((d) => setHistorico(Array.isArray(d) ? d : []))
      .catch(() => {});
  }, [uf, cargo, data?.hor]);

  return (
    <div className="min-h-screen bg-bg">
      <div className="max-w-4xl mx-auto px-4 py-6">
        <Header
          uf={uf}
          cargo={cargo}
          connected={connected}
          onUfChange={setUf}
          onCargoChange={setCargo}
        />

        {estado ? (
          <>
            <div className="bg-surface rounded-xl p-4 mb-6">
              <p className="text-gray-400 text-sm mb-1">{estado.nm}</p>
              <p className="text-xs text-gray-500">
                Atualizado às {data.hor}
              </p>
            </div>
            <ProgressBar pst={data.pst} />
            <ResultadoChart candidatos={estado.c} />
            <CandidatosTable candidatos={estado.c} />
            <HistoricoChart historico={historico} />
          </>
        ) : (
          <div className="text-center text-gray-500 mt-20">
            <p className="text-4xl mb-4">🗳️</p>
            <p>Aguardando dados de apuração...</p>
          </div>
        )}
      </div>
    </div>
  );
}
