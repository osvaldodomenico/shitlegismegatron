/**
 * Helpers para ler o payload real do TSE (dados-simplificados, sufixo -r).
 *
 * O TSE publica numeros como STRING com virgula decimal e ponto de milhar:
 *   pst  "100,00"      -> 100.00
 *   pvap "48,43"       -> 48.43
 *   vap  "57259504"    -> 57259504
 *
 * Aceita tambem o formato legado do simulador antigo ("73.45%"), para que
 * snapshots ja gravados no historico continuem renderizando.
 */

/** Converte numero do TSE (string com virgula) em Number. */
export function num(valor) {
  if (valor === null || valor === undefined) return 0;
  if (typeof valor === "number") return valor;
  let texto = String(valor).replace("%", "").trim();
  if (texto.includes(",")) {
    texto = texto.replace(/\./g, "").replace(",", ".");
  }
  const n = parseFloat(texto);
  return Number.isFinite(n) ? n : 0;
}

/**
 * Lista de candidatos do payload, independente do formato.
 * - TSE real:        data.cand
 * - simulador antigo: data.e[0].c
 */
export function candidatos(data) {
  if (!data) return [];
  if (Array.isArray(data.cand)) return data.cand;
  if (Array.isArray(data.e) && data.e[0] && Array.isArray(data.e[0].c)) {
    return data.e[0].c;
  }
  return [];
}

/** Hora de geracao do arquivo: `hg` no TSE real, `hor` no formato legado. */
export function horaAtualizacao(data) {
  return data?.hg || data?.hor || "";
}

/** Data de geracao do arquivo (`dg`, "dd/mm/aaaa"). Vazio no formato legado. */
export function dataAtualizacao(data) {
  return data?.dg || "";
}

/**
 * Frase do carimbo do boletim. `hoje` em "dd/mm/aaaa" (injetavel nos testes).
 *
 * O TSE regenera o arquivo dias antes da eleicao com 0% de secoes; mostrar so
 * a hora ("atualizados as 18:34") fazia parecer boletim do dia. Enquanto nada
 * foi totalizado a frase diz que estamos esperando o TSE; boletim de outro
 * dia sai com a data.
 */
export function legendaBoletim(data, hoje = new Date().toLocaleDateString("pt-BR")) {
  const hora = horaAtualizacao(data);
  if (!hora) return "Aguardando primeiro boletim";
  const dia = dataAtualizacao(data);
  const quando = dia && dia !== hoje ? `${dia} às ${hora}` : `às ${hora}`;
  if (num(data?.pst) === 0) return `Aguardando o TSE iniciar a apuração · último boletim ${quando}`;
  if (boletimFinal(data)) return `Totalização FINAL do TSE · boletim ${quando}`;
  return dia && dia !== hoje ? `Boletim do TSE de ${quando}` : `Dados do TSE, atualizados ${quando}`;
}

/** `tf` = "s" quando o TSE marca o boletim como totalizacao final. */
export function boletimFinal(data) {
  return String(data?.tf || "").toLowerCase() === "s";
}

const ORDEM_SITUACAO = { eleito: 0, segundo_turno: 1, suplente: 2, nao_eleito: 3, outro: 4 };

/**
 * Le a situacao publicada pelo TSE (`st`) e devolve um tipo estavel para a
 * interface. Textos reais: "Eleito", "Eleito por QP", "Eleito por média",
 * "2º turno", "Suplente", "Não eleito". Vazio enquanto nao esta definido.
 */
export function classificarSituacao(cand) {
  const texto = situacao(cand).trim();
  const t = texto.toLowerCase();
  if (!t) return { tipo: "", texto: "" };
  if (/2\s*[ºo°]?\s*turno/.test(t)) return { tipo: "segundo_turno", texto: "2º turno" };
  if (/n[aã]o\s+eleit/.test(t)) return { tipo: "nao_eleito", texto };
  if (/eleit/.test(t)) return { tipo: "eleito", texto };
  if (/suplente/.test(t)) return { tipo: "suplente", texto };
  return { tipo: "outro", texto };
}

/**
 * Contagem por situacao, para o resumo da legenda ("3 eleitos por QP · 1 por
 * média · 2 suplentes"). Lista vazia enquanto o TSE nao preencher nada.
 */
export function resumoSituacoes(cands) {
  const contagem = new Map();
  for (const c of cands || []) {
    const { tipo, texto } = classificarSituacao(c);
    if (!tipo) continue;
    const chave = texto.toLowerCase();
    const atual = contagem.get(chave) || { tipo, texto: chave, n: 0 };
    atual.n += 1;
    contagem.set(chave, atual);
  }
  return [...contagem.values()].sort((a, b) => ORDEM_SITUACAO[a.tipo] - ORDEM_SITUACAO[b.tipo] || b.n - a.n);
}

/** Foto oficial na CDN do TSE — mesmo esquema de api/apuracao.url_foto. */
export function urlFoto(uf, ele, sqcand) {
  if (!uf || !ele || !sqcand) return null;
  return `https://resultados.tse.jus.br/oficial/ele2026/${ele}/fotos/${String(uf).toLowerCase()}/${sqcand}.jpeg`;
}

/** Situacao do candidato: `st` no TSE real, `e` no formato legado. */
export function situacao(cand) {
  const st = cand?.st;
  if (st) return st;
  const legado = cand?.e;
  return legado === "s" || legado === "n" ? "" : legado || "";
}

/** Partido/coligacao: `cc` no TSE real, `sg` no formato legado. */
export function partido(cand) {
  return cand?.cc || cand?.sg || "";
}

/**
 * Ranking dentro de uma legenda: os `n` mais votados do partido, garantindo o
 * candidato `destaque` (numero de urna) na lista mesmo fora do top-n.
 * Cada item traz `posicao` (1-based na legenda) e `destaque` (bool).
 */
export function rankingDaLegenda(cands, sigla, destaque, n = 10) {
  const daLegenda = (cands || [])
    .filter((c) => partido(c).toUpperCase() === String(sigla).toUpperCase())
    .sort((a, b) => num(b.vap) - num(a.vap))
    .map((c, i) => ({ ...c, posicao: i + 1, destaque: String(c.n) === String(destaque) }));
  const top = daLegenda.slice(0, n);
  const alvo = daLegenda.find((c) => c.destaque);
  if (alvo && !top.includes(alvo)) {
    top.pop();
    top.push(alvo);
  }
  return { lista: top, total: daLegenda.length, todos: daLegenda };
}

/**
 * Votos do partido na corrida. Usa `partidos[]` (collector >= 04/10 19h:
 * nominais + legenda + vagas, direto do TSE). Sem esse campo, soma os
 * nominais dos candidatos — ai `legenda` e `vagas` ficam null e o total e
 * so o nominal.
 */
export function votosDoPartido(data, sigla) {
  const alvo = String(sigla || "").toUpperCase();
  const validos = num(data?.vv);
  const pct = (v) => (validos > 0 ? (v / validos) * 100 : 0);
  const p = (data?.partidos || []).find((x) => String(x.sg || "").toUpperCase() === alvo);
  if (p) {
    const nominais = num(p.tvtn), legenda = num(p.tvtl);
    const total = num(p.tvan) || nominais + legenda;
    return { total, nominais, legenda, vagas: p.vag === undefined || p.vag === null ? null : num(p.vag), pct: pct(total), completo: true };
  }
  const nominais = candidatos(data)
    .filter((c) => partido(c).toUpperCase() === alvo)
    .reduce((t, c) => t + num(c.vap), 0);
  return { total: nominais, nominais, legenda: null, vagas: null, pct: pct(nominais), completo: false };
}
