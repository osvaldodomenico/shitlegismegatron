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
      // Os valores vivem em src/index.css (:root = escuro, .light = claro) como
      // triplas RGB, para que bg-primary/20 etc. continuem funcionando.
      colors: {
        bg: "rgb(var(--c-bg) / <alpha-value>)",
        surface: "rgb(var(--c-surface) / <alpha-value>)",
        elevated: "rgb(var(--c-elevated) / <alpha-value>)",
        line: "rgb(var(--c-line) / <alpha-value>)",
        primary: "rgb(var(--c-primary) / <alpha-value>)",
        primaryLit: "rgb(var(--c-primaryLit) / <alpha-value>)",
        accent: "rgb(var(--c-accent) / <alpha-value>)",
        success: "rgb(var(--c-success) / <alpha-value>)",
        successLit: "rgb(var(--c-successLit) / <alpha-value>)",
        muted: "rgb(var(--c-muted) / <alpha-value>)",
        subtle: "rgb(var(--c-subtle) / <alpha-value>)",
        faint: "rgb(var(--c-faint) / <alpha-value>)",
        s1: "rgb(var(--c-s1) / <alpha-value>)",
        s2: "rgb(var(--c-s2) / <alpha-value>)",
        s3: "rgb(var(--c-s3) / <alpha-value>)",
        s4: "rgb(var(--c-s4) / <alpha-value>)",
        s5: "rgb(var(--c-s5) / <alpha-value>)",
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
