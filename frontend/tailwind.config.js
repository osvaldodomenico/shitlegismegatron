/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        bg: "#0a0a1a",
        surface: "#12122a",
        primary: "#1565C0",
        success: "#2E7D32",
        muted: "#E8EAF6",
      },
    },
  },
  plugins: [],
};
