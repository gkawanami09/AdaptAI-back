from pydantic import BaseModel, Field, field_validator
from typing import Literal, Optional
from uuid import UUID


DiaSemana = Literal[
    "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"
]
PlanoEstudosGeradoStatus = Literal["gerando", "concluido", "erro"]


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


# --- Wizard de criação de plano de estudos ------------------------------

class ProvaOpcao(BaseModel):
    slug: str
    nome: str
    descricao: Optional[str] = None
    data_prova: Optional[str] = None


class MateriaOpcao(BaseModel):
    slug: str
    nome: str


class GetPlanoEstudosOpcoesResponse(BaseModel):
    provas: list[ProvaOpcao]
    materias: list[MateriaOpcao]


class PostCriarPlanoEstudosParams(BaseModel):
    provas: list[str] = Field(min_length=1)
    materias: list[str] = Field(min_length=1)
    tempo_por_dia_minutos: int = Field(gt=0)
    dias_estudo: list[DiaSemana] = Field(min_length=1)

    @field_validator("dias_estudo")
    @classmethod
    def sem_dias_duplicados(cls, valor: list[str]) -> list[str]:
        if len(valor) != len(set(valor)):
            raise ValueError("Não pode haver dias de estudo duplicados")
        return valor


class PostCriarPlanoEstudosResponse(BaseModel):
    id: UUID
    status: PlanoEstudosGeradoStatus
    mensagem: Optional[str] = None


class PlanoEstudosGeradoSessao(BaseModel):
    materia: str
    aula_id: Optional[UUID] = None
    titulo: Optional[str] = None
    duracao_minutos: int
    tipo: str


class PlanoEstudosGeradoDia(BaseModel):
    dia: DiaSemana
    data: str
    sessoes: list[PlanoEstudosGeradoSessao]


class PlanoEstudosGeradoSemana(BaseModel):
    numero: int
    dias: list[PlanoEstudosGeradoDia]


class PeriodoPlano(BaseModel):
    inicio: str
    fim: str


class PlanoEstudosGerado(BaseModel):
    periodo: PeriodoPlano
    semanas: list[PlanoEstudosGeradoSemana]


class GetPlanoEstudosGeradoResponse(BaseModel):
    id: UUID
    status: PlanoEstudosGeradoStatus
    mensagem: Optional[str] = None
    plano: Optional[PlanoEstudosGerado] = None
