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
