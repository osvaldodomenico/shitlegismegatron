from fastapi import APIRouter, HTTPException

import apuracao
import consumer
import selecao as sel

router = APIRouter()


@router.get("/resultados/{uf}/{cargo}")
async def get_resultado(uf: str, cargo: str, selecionados: bool = False, perfil: str = sel.PERFIL_PADRAO):
    """
    Ultimo snapshot da corrida.

    `selecionados=true` recorta `cand` para os candidatos acompanhados. Em
    deputado federal de SP isso leva o payload de ~240 KB para ~2 KB — o
    filtro precisa ser aqui, no servidor; filtrar so no navegador economiza
    render, nao trafego.
    """
    stream = f"megatron:{uf}:{cargo}"
    snap = consumer.get_last_snapshot(stream)
    if snap is None:
        raise HTTPException(status_code=404, detail="Sem dados ainda")
    if selecionados:
        try:
            perfil = sel.validar_perfil(perfil)
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e))
        # preparar() calcula quociente e linha de corte sobre a corrida
        # inteira e so entao recorta — ver apuracao.preparar.
        return apuracao.preparar(snap, uf, sel.get(uf, cargo, perfil))
    return snap
