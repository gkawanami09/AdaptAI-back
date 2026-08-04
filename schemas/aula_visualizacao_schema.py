from pydantic import BaseModel, Field
from typing import Literal, Optional


class ConceitoAula(BaseModel):
    id: str
    label: str
    concluido: bool


class AulaModuloItem(BaseModel):
    ordem: int
    titulo: str
    status: Literal["concluida", "atual", "bloqueada"]


class ModuloAula(BaseModel):
    titulo: str
    aulas: list[AulaModuloItem]


class ProximaAula(BaseModel):
    slug: str
    titulo: str
    duracao_min: int
    dificuldade: str


class AulaVisualizacaoResponse(BaseModel):
    slug: str
    titulo: str
    materia: str
    materia_cor: str
    duracao_min: int
    dificuldade: str
    progresso: int
    status: Literal["concluida", "em-andamento", "nao-iniciada"]
    video_url: Optional[str] = None
    resumo: list[str]
    conceitos: list[ConceitoAula]
    modulo: Optional[ModuloAula] = None
    proxima_aula: Optional[ProximaAula] = None
    dica_ada: Optional[str] = None


class AtualizarProgressoAula(BaseModel):
    progresso: int = Field(ge=0, le=100)


class AtualizarProgressoAulaResponse(BaseModel):
    slug: str
    progresso: int
    status: Literal["concluida", "em-andamento", "nao-iniciada"]


class AtualizarConceitoAula(BaseModel):
    concluido: bool


class AtualizarConceitoAulaResponse(BaseModel):
    id: str
    label: str
    concluido: bool
