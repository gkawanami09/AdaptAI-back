from pydantic import BaseModel
from typing import Optional


class BancoQuestoesFiltroOpcao(BaseModel):
    value: str
    label: str


class BancoQuestoesFiltrosResponse(BaseModel):
    vestibulares: list[BancoQuestoesFiltroOpcao]
    dificuldades: list[BancoQuestoesFiltroOpcao]
    materias: list[BancoQuestoesFiltroOpcao]


class BancoQuestoesLista(BaseModel):
    id: str
    slug: Optional[str] = None
    icone: str
    icone_cor: str
    titulo: str
    dificuldade: str
    dificuldade_cor: str
    vestibular: str
    questoes_concluidas: int
    questoes_totais: int
    progresso_cor: str


class BancoQuestoesListasResponse(BaseModel):
    total: int
    listas: list[BancoQuestoesLista]


class GerarListaIAResponse(BaseModel):
    id: str
    slug: Optional[str] = None
