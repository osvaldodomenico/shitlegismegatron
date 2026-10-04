/**
 * Tema claro/escuro. Prioridade: ?tema=light|dark na URL (util para abrir o
 * telao direto no tema certo) > escolha salva no navegador > escuro.
 * A troca e uma classe `light` no <html>; as cores vivem em index.css.
 */
const CHAVE = "megatron-tema";

export function lerTema(busca = window.location.search) {
  const q = new URLSearchParams(busca).get("tema");
  if (q === "light" || q === "dark") return q;
  try {
    const salvo = localStorage.getItem(CHAVE);
    if (salvo === "light" || salvo === "dark") return salvo;
  } catch { /* localStorage indisponivel: fica no padrao */ }
  return "dark";
}

export function aplicarTema(tema) {
  document.documentElement.classList.toggle("light", tema === "light");
  document.documentElement.style.colorScheme = tema;
  try { localStorage.setItem(CHAVE, tema); } catch { /* idem */ }
  return tema;
}

export function temaAtual() {
  return document.documentElement.classList.contains("light") ? "light" : "dark";
}
