import { useState, useEffect } from "react";
import { useElectionSocket } from "./hooks/useElectionSocket";
import { candidatos as lerCandidatos, horaAtualizacao } from "./lib/tse";
import { Header } from "./components/Header";
import { ProgressBar } from "./components/ProgressBar";
import { CandidatosTable } from "./components/CandidatosTable";
import { ResultadoChart } from "./components/ResultadoChart";
import { HistoricoChart } from "./components/HistoricoChart";

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

const UF_NOMES = {
  br: "Brasil", sp: "São Paulo", rj: "Rio de Janeiro", mg: "Minas Gerais",
  rs: "Rio Grande do Sul", ba: "Bahia", pr: "Paraná", pe: "Pernambuco",
  ce: "Ceará", pa: "Pará", sc: "Santa Catarina",
};

export default function App() {
  const [uf, setUf] = useState("sp");
  const [cargo, setCargo] = useState("governador");
  const [historico, setHistorico] = useState([]);

  // Presidente so existe na abrangencia nacional ("br"); os demais cargos
  // so existem por UF. Manter o par coerente evita pedir um stream que o
  // TSE nunca publica.
  function trocarCargo(novo) {
    setCargo(novo);
    if (novo === "presidente") setUf("br");
    else if (uf === "br") setUf("sp");
  }

  function trocarUf(nova) {
    setUf(nova);
    if (nova === "br") setCargo("presidente");
    else if (cargo === "presidente") setCargo("governador");
  }

  const { data, connected } = useElectionSocket(uf, cargo);
  const cands = lerCandidatos(data);
  const hora = horaAtualizacao(data);

  useEffect(() => {
    fetch(`${API_URL}/historico/${uf}/${cargo}?ultimas=30`)
      .then((r) => r.json())
      .then((d) => setHistorico(Array.isArray(d) ? d : []))
      .catch(() => {});
  }, [uf, cargo, hora]);

  return (
    <div className="min-h-screen bg-bg">
      <div className="max-w-4xl mx-auto px-4 py-6">
        <Header
          uf={uf}
          cargo={cargo}
          connected={connected}
          onUfChange={trocarUf}
          onCargoChange={trocarCargo}
        />

        {cands.length > 0 ? (
          <>
            <div className="bg-surface rounded-xl p-4 mb-6">
              <p className="text-gray-400 text-sm mb-1">
                {UF_NOMES[uf] || uf.toUpperCase()}
              </p>
              <p className="text-xs text-gray-500">Atualizado às {hora}</p>
            </div>
            <ProgressBar pst={data.pst} />
            <ResultadoChart candidatos={cands} />
            <CandidatosTable candidatos={cands} />
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
