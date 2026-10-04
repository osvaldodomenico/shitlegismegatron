import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { Selo, Final } from "../components/Telao";

describe("Selo", () => {
  it("eleito sai verde com trofeu e o texto do TSE", () => {
    const { container } = render(<Selo cand={{ st: "Eleito por QP" }} />);
    expect(screen.getByText("Eleito por QP")).toBeInTheDocument();
    expect(container.querySelector("svg")).not.toBeNull();
    expect(container.firstChild.className).toContain("text-successLit");
  });

  it("2o turno tem selo proprio, nao a etiqueta cinza", () => {
    const { container } = render(<Selo cand={{ st: "2º turno" }} />);
    expect(screen.getByText("2º turno")).toBeInTheDocument();
    expect(container.firstChild.className).toContain("text-accent");
  });

  it("suplente e nao eleito ficam neutros; vazio nao renderiza", () => {
    const { container: a } = render(<Selo cand={{ st: "Suplente" }} />);
    expect(a.firstChild.className).toContain("bg-elevated");
    const { container: b } = render(<Selo cand={{ st: "" }} />);
    expect(b.firstChild).toBeNull();
  });
});

describe("Final", () => {
  it("so aparece quando tf = s", () => {
    const { container: a } = render(<Final data={{ tf: "n" }} />);
    expect(a.firstChild).toBeNull();
    render(<Final data={{ tf: "s" }} />);
    expect(screen.getByText("Totalização final")).toBeInTheDocument();
  });
});
