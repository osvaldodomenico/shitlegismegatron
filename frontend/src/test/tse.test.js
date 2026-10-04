import { describe, it, expect } from "vitest";
import { legendaBoletim, urlFoto, rankingDaLegenda, classificarSituacao, resumoSituacoes, boletimFinal, votosDoPartido, eleitosMatematicos, corProgresso } from "../lib/tse";

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

describe("situacao do TSE", () => {
  it("classifica os textos reais do TSE", () => {
    expect(classificarSituacao({ st: "Eleito" }).tipo).toBe("eleito");
    expect(classificarSituacao({ st: "Eleito por QP" }).tipo).toBe("eleito");
    expect(classificarSituacao({ st: "Eleito por média" }).tipo).toBe("eleito");
    expect(classificarSituacao({ st: "Não eleito" }).tipo).toBe("nao_eleito");
    expect(classificarSituacao({ st: "2º turno" })).toEqual({ tipo: "segundo_turno", texto: "2º turno" });
    expect(classificarSituacao({ st: "2o Turno" }).tipo).toBe("segundo_turno");
    expect(classificarSituacao({ st: "Suplente" }).tipo).toBe("suplente");
    expect(classificarSituacao({ st: "" }).tipo).toBe("");
    expect(classificarSituacao({ e: "n" }).tipo).toBe("");
  });

  it("resume a legenda com eleitos primeiro e vazio enquanto o TSE nao preenche", () => {
    expect(resumoSituacoes([{ st: "" }, { st: "" }])).toEqual([]);
    const r = resumoSituacoes([
      { st: "Suplente" }, { st: "Eleito por QP" }, { st: "Eleito por média" },
      { st: "Eleito por QP" }, { st: "Não eleito" }, { st: "Suplente" }, { st: "Eleito por QP" },
    ]);
    expect(r.map((x) => `${x.n} ${x.texto}`)).toEqual([
      "3 eleito por qp", "1 eleito por média", "2 suplente", "1 não eleito",
    ]);
  });

  it("boletim final muda o carimbo", () => {
    expect(boletimFinal({ tf: "n" })).toBe(false);
    expect(boletimFinal({ tf: "s" })).toBe(true);
    expect(legendaBoletim({ dg: "04/10/2026", hg: "23:10:00", pst: "100,00", tf: "s" }, "04/10/2026"))
      .toBe("Totalização FINAL do TSE · boletim às 23:10:00");
  });
});

describe("votosDoPartido", () => {
  const cand = [
    { cc: "REPUBLICANOS", vap: "600" }, { cc: "PT", vap: "900" }, { cc: "Republicanos", vap: "400" },
  ];

  it("com partidos[] do TSE: nominais + legenda, vagas e % dos validos", () => {
    const d = { vv: "10000", cand, partidos: [{ sg: "REPUBLICANOS", tvtn: "1000", tvtl: "50", tvan: "1050", vag: "6" }] };
    expect(votosDoPartido(d, "republicanos")).toEqual({ total: 1050, nominais: 1000, legenda: 50, vagas: 6, pct: 10.5, completo: true });
  });

  it("sem partidos[]: soma os nominais dos candidatos e avisa que esta incompleto", () => {
    const r = votosDoPartido({ vv: "10000", cand }, "REPUBLICANOS");
    expect(r).toEqual({ total: 1000, nominais: 1000, legenda: null, vagas: null, pct: 10, completo: false });
  });

  it("partido sem votos nao divide por zero", () => {
    expect(votosDoPartido({ vv: "0", cand: [] }, "X").pct).toBe(0);
  });
});

describe("eleitosMatematicos", () => {
  it("1 vaga: so com mais da metade dos validos projetados", () => {
    // 80% apurado, vv 800 -> restam 200, projetado 1000: precisa de > 500
    const d = { pst: "80,00", vv: "800", cand: [
      { sqcand: "A", vap: "520" }, { sqcand: "B", vap: "280" },
    ] };
    expect([...eleitosMatematicos(d, 1)]).toEqual(["A"]);
    d.cand[0].vap = "480";
    expect(eleitosMatematicos(d, 1).size).toBe(0);
  });

  it("2 vagas (senador): eleito quem o 3o nao alcanca nem levando todo o resto", () => {
    // 90% apurado, vv 900 -> restam 100
    const d = { pst: "90,00", vv: "900", cand: [
      { sqcand: "A", vap: "300" }, { sqcand: "B", vap: "260" }, { sqcand: "C", vap: "190" },
    ] };
    expect([...eleitosMatematicos(d, 2)]).toEqual(["A"]);      // B: 260 <= 190 + 100
    d.cand[1].vap = "295";
    expect([...eleitosMatematicos(d, 2)].sort()).toEqual(["A", "B"]);
  });

  it("sem apuracao ou com 100% nao projeta (ai e o TSE quem fala)", () => {
    const d = { pst: "0,00", vv: "0", cand: [{ sqcand: "A", vap: "0" }] };
    expect(eleitosMatematicos(d, 1).size).toBe(0);
    expect(eleitosMatematicos({ ...d, pst: "100,00", vv: "10", cand: [{ sqcand: "A", vap: "10" }] }, 1).size).toBe(0);
  });
});

describe("corProgresso", () => {
  it("vai do vermelho ao verde conforme as secoes fecham", () => {
    expect(corProgresso("0,00")).toBe("hsl(0 80% 48%)");
    expect(corProgresso("50,00")).toBe("hsl(60 80% 48%)");
    expect(corProgresso("100,00")).toBe("hsl(120 80% 48%)");
    expect(corProgresso("150")).toBe("hsl(120 80% 48%)");
  });
});
