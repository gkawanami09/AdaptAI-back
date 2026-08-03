from pydantic import BaseModel, Field
from typing import Literal, Optional
from uuid import UUID


class ProgressoPlano(BaseModel):
    percentual: int
    label: str


class DiaSemanaPlano(BaseModel):
    label: Literal["Dom", "Seg", "Ter", "Qua", "Qui", "Sex", "Sáb"]
    data: int
    data_iso: str
    tem_tarefas: bool


class TarefaDoDia(BaseModel):
    id: UUID
    icone: str
    icone_cor: str
    titulo: str
    materia: str
    materia_cor: str
    duracao_min: int
    concluida: bool
    progresso: Optional[int] = None
    tipo: Literal["aula", "questoes", "lista", "prova", "redacao", "revisao"]


class BadgeVisaoGeral(BaseModel):
    label: str
    color: str


class VisaoGeralDia(BaseModel):
    dia: Literal["Dom", "Seg", "Ter", "Qua", "Qui", "Sex", "Sáb"]
    badges: list[BadgeVisaoGeral]
    descanso_label: Optional[str] = None
    concluidas: int
    total: int


class PrioridadeSemana(BaseModel):
    materia: str
    descricao: str
    prioridade: Literal["alta", "media", "baixa"]
    tom: str
    icone: Optional[str] = None


class EstatisticaPlano(BaseModel):
    label: str
    valor: str
    cor: str


class PlanoEstudosResponse(BaseModel):
    intervalo_label: str
    tarefas_concluidas_total: int
    tarefas_totais: int
    progresso: ProgressoPlano
    dias_da_semana: list[DiaSemanaPlano]
    tarefas_do_dia: list[TarefaDoDia]
    visao_geral_semana: list[VisaoGeralDia]
    prioridades_da_semana: list[PrioridadeSemana]
    estatisticas: list[EstatisticaPlano]


class ReorganizarIAResponse(BaseModel):
    sucesso: bool


class ConcluirTarefaResponse(BaseModel):
    sucesso: bool


class TarefaPlanoCriar(BaseModel):
    materia_id: UUID
    titulo: str = Field(min_length=2, max_length=200)
    tipo: Literal["aula", "questoes", "lista", "prova", "redacao", "revisao"]
    duracao_min: int = Field(gt=0)
    data: str


class TarefaPlanoCriarResponse(BaseModel):
    id: UUID
    sucesso: bool
