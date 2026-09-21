/**
 * Icones SVG do painel (traco 1.5, grade 24) — substituem os emojis, que
 * dependem da fonte do sistema e nao aceitam token de cor.
 * Sempre decorativos: quem descreve a acao e o aria-label do botao.
 */
const base = {
  viewBox: "0 0 24 24", fill: "none", stroke: "currentColor",
  strokeWidth: 1.5, strokeLinecap: "round", strokeLinejoin: "round",
  "aria-hidden": "true", focusable: "false",
};

export const IconBallot = (p) => (
  <svg {...base} {...p}><path d="M5 21h14a1 1 0 0 0 1-1v-7H4v7a1 1 0 0 0 1 1Z"/><path d="M4 13 6 4h12l2 9"/><path d="M9 17h6"/></svg>
);
export const IconSearch = (p) => (
  <svg {...base} {...p}><circle cx="11" cy="11" r="7"/><path d="m20 20-3.2-3.2"/></svg>
);
export const IconClose = (p) => (
  <svg {...base} {...p}><path d="M18 6 6 18M6 6l12 12"/></svg>
);
export const IconCheck = (p) => (
  <svg {...base} {...p}><path d="m20 6-11 11-5-5"/></svg>
);
export const IconUsers = (p) => (
  <svg {...base} {...p}><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13A4 4 0 0 1 16 11"/></svg>
);
export const IconPlus = (p) => (
  <svg {...base} {...p}><path d="M12 5v14M5 12h14"/></svg>
);
export const IconAlert = (p) => (
  <svg {...base} {...p}><path d="M12 9v4M12 17h.01"/><path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0Z"/></svg>
);
