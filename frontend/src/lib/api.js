/**
 * Chamadas a API do MEGATRON.
 *
 * O recorte de candidatos acontece NO SERVIDOR: em deputado federal de SP o
 * payload cai de ~235 KB para ~1,7 KB. Buscar tudo e filtrar aqui economizaria
 * render, nao trafego.
 */
const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

async function json(caminho, opcoes) {
  const r = await fetch(`${API_URL}${caminho}`, opcoes);
  if (!r.ok) throw new Error(`${r.status} em ${caminho}`);
  return r.json();
}

/** Lista enxuta para o seletor: {sqcand, nm, cc, n}. */
export function buscarCandidatos(uf, cargo) {
  return json(`/candidatos/${uf}/${cargo}`);
}

/** Query do perfil de selecao; o padrao nao vai na URL. */
const qPerfil = (perfil) => (perfil && perfil !== "padrao" ? `perfil=${encodeURIComponent(perfil)}` : "");
const comQuery = (caminho, ...partes) => {
  const q = partes.filter(Boolean).join("&");
  return q ? `${caminho}?${q}` : caminho;
};

/** Selecao compartilhada atual do perfil: {sqcands, maximo}. */
export function buscarSelecao(uf, cargo, perfil) {
  return json(comQuery(`/selecao/${uf}/${cargo}`, qPerfil(perfil)));
}

/** Grava a selecao do perfil. Lanca com a mensagem do servidor se passar do maximo. */
export async function salvarSelecao(uf, cargo, sqcands, perfil) {
  const r = await fetch(`${API_URL}${comQuery(`/selecao/${uf}/${cargo}`, qPerfil(perfil))}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ sqcands }),
  });
  const corpo = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(corpo.detail || `falha ao salvar (${r.status})`);
  return corpo;
}

export function buscarHistorico(uf, cargo, ultimas = 30) {
  return json(`/historico/${uf}/${cargo}?ultimas=${ultimas}`);
}

/**
 * Ultimo snapshot via REST. Necessario para a primeira pintura: o WebSocket so
 * empurra quando o collector republica, e o collector so republica quando o
 * payload MUDA (diff-hash). Sobre fonte estatica isso nunca ocorre.
 */
export function buscarResultado(uf, cargo, apenasSelecionados = false, perfil) {
  if (!apenasSelecionados) return json(`/resultados/${uf}/${cargo}`);
  return json(comQuery(`/resultados/${uf}/${cargo}`, "selecionados=true", qPerfil(perfil)));
}

/** Corridas que o backend realmente coleta — fonte dos seletores. */
export function buscarCorridas() {
  return json("/corridas");
}

/** Votacao de um candidato por cidade ou zona (coletor de municipios, 5 em 5 min). */
export function buscarCidades(uf, cargo, sqcand, nivel = "municipio") {
  return json(`/candidatos/${uf}/${cargo}/${sqcand}/cidades?nivel=${nivel}`);
}
