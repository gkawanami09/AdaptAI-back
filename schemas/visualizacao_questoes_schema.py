from pydantic import BaseModel
from typing import Literal, Optional


class QuestaoVisualizacao(BaseModel):
    id: str
    subject: str
    subjectColor: str
    examInfo: str
    question: str
    options: list[str]
    hint: Optional[str] = None
    respondida: bool
    opcaoSelecionada: Optional[int] = None
    correta: Optional[bool] = None
    favorita: bool


class ListaQuestoesVisualizacaoResponse(BaseModel):
    slug: str
    titulo: str
    materia: str
    dificuldade: str
    vestibular: str
    status: Literal["em_andamento", "finalizada"]
    questoes_totais: int
    questoes_concluidas: int
    progresso_percentual: int
    questoes: list[QuestaoVisualizacao]


class ResponderQuestaoPayload(BaseModel):
    opcao_selecionada: int


class ResponderQuestaoResponse(BaseModel):
    id: str
    respondida: bool
    opcaoSelecionada: Optional[int] = None
    correta: Optional[bool] = None
    questoes_concluidas: int
    progresso_percentual: int


class FavoritarQuestaoResponse(BaseModel):
    id: str
    favorita: bool


class FinalizarListaResponse(BaseModel):
    status: Literal["em_andamento", "finalizada"]
    progresso_percentual: int
    questoes_concluidas: int
    questoes_totais: int
