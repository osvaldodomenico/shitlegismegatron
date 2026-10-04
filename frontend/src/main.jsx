import React from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import { Painel } from "./Painel";
import "./index.css";

// Sem roteador: so existem duas telas. /painel e a visao de telao (1920x1080).
const Tela = window.location.pathname.replace(/\/+$/, "") === "/painel" ? Painel : App;

createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <Tela />
  </React.StrictMode>
);
