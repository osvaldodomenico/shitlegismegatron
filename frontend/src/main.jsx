import React from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import { Painel } from "./Painel";
import { Dashboard } from "./Dashboard";
import { lerTema, aplicarTema } from "./lib/tema";
import "./index.css";

aplicarTema(lerTema());

// Sem roteador: tres telas. /painel e o telao 1920x1080 (3 corridas);
// /dashboard e o vertical 1080x1920 (os 5 pleitos).
const TELAS = { "/painel": Painel, "/dashboard": Dashboard };
const Tela = TELAS[window.location.pathname.replace(/\/+$/, "")] || App;

createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <Tela />
  </React.StrictMode>
);
