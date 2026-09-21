import { useCallback, useEffect, useState } from "react";
import { useElectionSocket } from "./hooks/useElectionSocket";
import { candidatos as lerCandidatos, horaAtualizacao } from "./lib/tse";
import * as api from "./lib/api";
import { Header, CARGO_LABELS } from "./components/Header";
import { Hero } from "./components/Hero";
import { ComparacaoPainel } from "./components/ComparacaoPainel";
import { SeletorCandidatos } from "./components/SeletorCandidatos";
import { CandidatosTable } from "./components/CandidatosTable";
import { ResultadoChart } from "./components/ResultadoChart";
import { HistoricoChart } from "./components/HistoricoChart";
import { IconAlert } from "./components/icons";

const UF_NOMES = {
  br: "Brasil", sp: "São Paulo", rj: "Rio de Janeiro", mg: "Minas Gerais",
  rs: "Rio Grande do Sul", ba: "Bahia", pr: "Paraná", pe: "Pernambuco",
  ce: "Ceará", pa: "Pará", sc: "Santa Catarina",
};

export default function App() {
  const [uf, setUf] = useState("sp");
  const [cargo, setCargo] = useState("governador");
  const [historico, setHistorico] = useState([]);

  const [selecao, setSelecao] = useState([]);
  const [maximo, setMaximo] = useState(5);
  const [listaCandidatos, setListaCandidatos] = useState([]);
  const [seletorAberto, setSeletorAberto] = useState(false);
  const [salvando, setSalvando] = useState(false);
  const [erro, setErro] = useState("");
  const [carregando, setCarregando] = useState(true);

  // Com selecao ativa o socket entra na room filtrada: o servidor manda so os
  // acompanhados, em vez dos 1429 candidatos da corrida.
  const filtrando = selecao.length > 0;
  const { data, connected, setData } = useElectionSocket(uf, cargo, {
    selecionados: filtrando,
  });

  const cands = lerCandidatos(data);
  const hora = horaAtualizacao(data);

  // Presidente so existe em "br"; os demais cargos so existem por UF.
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

  // Selecao vigente da corrida (compartilhada entre todos).
  useEffect(() => {
    let vivo = true;
    api.buscarSelecao(uf, cargo)
      .then((s) => { if (vivo) { setSelecao(s.sqcands || []); setMaximo(s.maximo || 5); } })
      .catch(() => { if (vivo) setSelecao([]); });
    return () => { vivo = false; };
  }, [uf, cargo]);

  // Primeira pintura via REST — ver comentario em api.buscarResultado.
  useEffect(() => {
    let vivo = true;
    setCarregando(true);
    api.buscarResultado(uf, cargo, filtrando)
      .then((d) => { if (vivo) setData(d); })
      .catch(() => { if (vivo) setData(null); })
      .finally(() => { if (vivo) setCarregando(false); });
    return () => { vivo = false; };
  }, [uf, cargo, filtrando, setData]);

  useEffect(() => {
    api.buscarHistorico(uf, cargo, 30)
      .then((d) => setHistorico(Array.isArray(d) ? d : []))
      .catch(() => setHistorico([]));
  }, [uf, cargo, hora]);

  const abrirSeletor = useCallback(async () => {
    setErro("");
    setSeletorAberto(true);
    try {
      const r = await api.buscarCandidatos(uf, cargo);
      setListaCandidatos(r.candidatos || []);
    } catch {
      setListaCandidatos([]);
      setErro("Não foi possível carregar a lista de candidatos desta corrida.");
    }
  }, [uf, cargo]);

  // Remocao direta pelo card: mesma gravacao da selecao, sem abrir o seletor.
  async function removerCandidato(sqcand) {
    const restantes = selecao.filter((s) => s !== sqcand);
    setSelecao(restantes);                 // resposta imediata na tela
    try {
      await api.salvarSelecao(uf, cargo, restantes);
    } catch (e) {
      setSelecao(selecao);                 // desfaz se o servidor recusar
      setErro(e.message);
    }
  }

  async function confirmarSelecao(sqcands) {
    setSalvando(true);
    setErro("");
    try {
      const r = await api.salvarSelecao(uf, cargo, sqcands);
      setSelecao(r.sqcands);
      setSeletorAberto(false);
    } catch (e) {
      setErro(e.message);
    } finally {
      setSalvando(false);
    }
  }

  const ufNome = UF_NOMES[uf] || uf.toUpperCase();
  const cargoNome = CARGO_LABELS[cargo] || cargo;
  const semDados = !carregando && cands.length === 0 && !filtrando;

  return (
    <div className="min-h-dvh bg-bg">
      <Header
        uf={uf}
        cargo={cargo}
        connected={connected}
        onUfChange={trocarUf}
        onCargoChange={trocarCargo}
      />

      <Hero
        data={data}
        uf={uf}
        ufNome={ufNome}
        cargoNome={cargoNome}
        connected={connected}
        hora={hora}
      />

      <main className="mx-auto max-w-6xl px-4 py-8">
        {semDados ? (
          <div className="rounded-2xl border border-dashed border-line bg-surface/50 px-6 py-16 text-center">
            <IconAlert className="mx-auto h-10 w-10 text-faint" />
            <h2 className="mt-3 text-base font-semibold text-muted">
              Sem boletim para {cargoNome} em {ufNome}
            </h2>
            <p className="mx-auto mt-1 max-w-md text-sm text-subtle">
              Esta corrida ainda não está sendo coletada. Escolha outra combinação
              de estado e cargo no topo da página.
            </p>
          </div>
        ) : (
          <div className="grid gap-8 lg:grid-cols-5">
            <div className="lg:col-span-3">
              <ComparacaoPainel
                candidatos={filtrando ? cands : []}
                indicadores={data?.indicadores}
                cargoNome={cargoNome}
                aoAbrirSeletor={abrirSeletor}
                aoRemover={removerCandidato}
                carregando={carregando}
                maximo={maximo}
              />
            </div>

            <div className="lg:col-span-2">
              {/* Corrida inteira so aparece sem selecao: com 1429 candidatos
                  filtrados, mostrar o ranking completo traria de volta os
                  235 KB que o filtro acabou de eliminar. */}
              {!filtrando && cands.length > 0 && (
                <>
                  <ResultadoChart candidatos={cands} />
                  <CandidatosTable candidatos={cands} />
                </>
              )}
              <HistoricoChart historico={historico} />
            </div>
          </div>
        )}
      </main>

      <SeletorCandidatos
        aberto={seletorAberto}
        aoFechar={() => setSeletorAberto(false)}
        candidatos={listaCandidatos}
        selecionados={selecao}
        maximo={maximo}
        aoConfirmar={confirmarSelecao}
        salvando={salvando}
        erro={erro}
      />
    </div>
  );
}
