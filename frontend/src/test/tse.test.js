import { describe, it, expect } from "vitest";
import { legendaBoletim, urlFoto, rankingDaLegenda } from "../lib/tse";

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

describe("rankingDaLegenda", () => {
  const cands = [
    { n: "1010", cc: "REPUBLICANOS", vap: "900" },
    { n: "1300", cc: "PT", vap: "5000" },
    { n: "1022", cc: "REPUBLICANOS", vap: "800" },
    { n: "1033", cc: "REPUBLICANOS", vap: "700" },
    { n: "1055", cc: "REPUBLICANOS", vap: "10" },
    { n: "1044", cc: "Republicanos", vap: "600" },
  ];

  it("ordena so a legenda e numera a posicao", () => {
    const { lista, total } = rankingDaLegenda(cands, "REPUBLICANOS", "1055", 10);
    expect(total).toBe(5);
    expect(lista.map((c) => c.n)).toEqual(["1010", "1022", "1033", "1044", "1055"]);
    expect(lista.map((c) => c.posicao)).toEqual([1, 2, 3, 4, 5]);
    expect(lista.find((c) => c.n === "1055").destaque).toBe(true);
  });

  it("fora do top-n, o destaque entra no lugar do ultimo com a posicao real", () => {
    const { lista } = rankingDaLegenda(cands, "REPUBLICANOS", "1055", 3);
    expect(lista.map((c) => c.n)).toEqual(["1010", "1022", "1055"]);
    expect(lista[2].posicao).toBe(5);
  });

  it("sem o destaque na corrida, devolve so o top-n", () => {
    const { lista } = rankingDaLegenda(cands, "REPUBLICANOS", "9999", 2);
    expect(lista.map((c) => c.n)).toEqual(["1010", "1022"]);
  });
});
