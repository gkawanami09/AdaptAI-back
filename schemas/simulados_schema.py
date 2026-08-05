from pydantic import BaseModel


class SimuladosResumo(BaseModel):
    nota_estimada: int
    tempo_medio: str
    taxa_acerto_percentual: int


class SimuladoCatalogoItem(BaseModel):
    slug: str
    titulo: str
    descricao: str
    icone: str
    icone_cor: str
    tag: str
    tag_cor: str
    duracao: str


class SimuladoHistoricoItem(BaseModel):
    id: str
    dia: str
    titulo: str
    tempo: str
    nota: int
    acertos_percentual: int


class SimuladosResponse(BaseModel):
    resumo: SimuladosResumo
    catalogo: list[SimuladoCatalogoItem]
    historico: list[SimuladoHistoricoItem]
