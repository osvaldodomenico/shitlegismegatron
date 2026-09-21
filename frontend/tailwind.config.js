/** @type {import('tailwindcss').Config} */
//
// Paleta: os tons do projeto (bg/surface/primary/success/muted) foram mantidos
// — o padrao do projeto vence. Foram ACRESCENTADOS os tokens que faltavam para
// hierarquia em dark: superficies elevadas, bordas, texto secundario, acento
// de destaque e a escala de series do painel de comparacao.
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        bg: "#0a0a1a",
        surface: "#12122a",
        elevated: "#1a1a38",      // cards sobre surface (escala de elevacao)
        line: "#262650",          // bordas e divisores, visiveis no escuro
        primary: "#1565C0",
        primaryLit: "#3B82F6",    // hover/foco: o primary puro fica escuro demais
        accent: "#F97316",        // "ao vivo", CTA — contraste >=3:1 no bg
        success: "#2E7D32",
        successLit: "#4ADE80",
        muted: "#E8EAF6",         // texto principal
        subtle: "#9FA8DA",        // texto secundario (>=4.5:1 sobre bg)
        faint: "#6B7299",         // texto terciario, so para rotulos curtos
        // Series do comparativo: distinguiveis entre si e sem depender de
        // par vermelho/verde (daltonismo). Sempre acompanhadas de nome/numero.
        s1: "#38BDF8",
        s2: "#FBBF24",
        s3: "#34D399",
        s4: "#F472B6",
        s5: "#A78BFA",
      },
      fontFamily: {
        sans: ["'Fira Sans'", "system-ui", "sans-serif"],
        mono: ["'Fira Code'", "ui-monospace", "monospace"],
      },
      // Numeros tabulares evitam o layout "pulando" a cada atualizacao de voto.
      fontVariantNumeric: { tabular: "tabular-nums" },
      keyframes: {
        pulseSoft: { "0%,100%": { opacity: "1" }, "50%": { opacity: ".45" } },
        slideUp: { from: { opacity: "0", transform: "translateY(8px)" }, to: { opacity: "1", transform: "none" } },
      },
      animation: {
        pulseSoft: "pulseSoft 2s ease-in-out infinite",
        slideUp: "slideUp 220ms ease-out both",
      },
    },
  },
  plugins: [],
};
