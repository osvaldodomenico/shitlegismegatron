import { describe, it, expect } from "vitest";
import { legendaBoletim, urlFoto } from "../lib/tse";

const HOJE = "04/10/2026";

describe("legendaBoletim", () => {
  it("sem boletim nenhum", () => {
    expect(legendaBoletim(null, HOJE)).toBe("Aguardando primeiro boletim");
  });

  it("arquivo de dias antes com 0% nao passa por boletim do dia", () => {
    const d = { dg: "02/10/2026", hg: "18:34:48", pst: "0,00" };
    expect(legendaBoletim(d, HOJE)).toBe(
      "Aguardando o TSE iniciar a apuração · último boletim 02/10/2026 às 18:34:48"
    );
  });

  it("boletim de hoje com apuracao em curso", () => {
    const d = { dg: "04/10/2026", hg: "17:25:58", pst: "1,68" };
    expect(legendaBoletim(d, HOJE)).toBe("Dados do TSE, atualizados às 17:25:58");
  });

  it("boletim fechado de outro dia mostra a data", () => {
    const d = { dg: "04/10/2026", hg: "23:59:00", pst: "100,00" };
    expect(legendaBoletim(d, "05/10/2026")).toBe("Boletim do TSE de 04/10/2026 às 23:59:00");
  });
});

describe("urlFoto", () => {
  it("segue o esquema da CDN do TSE", () => {
    expect(urlFoto("BR", "6257", "280002551544")).toBe(
      "https://resultados.tse.jus.br/oficial/ele2026/6257/fotos/br/280002551544.jpeg"
    );
    expect(urlFoto("br", "", "1")).toBeNull();
  });
});
