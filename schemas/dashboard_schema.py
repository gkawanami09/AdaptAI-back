from pydantic import BaseModel
from typing import Literal, Optional
from uuid import UUID


class DashboardKpis(BaseModel):
    total_usuarios: int
    total_usuarios_variacao_pct: float
    questoes_respondidas: int
    questoes_respondidas_variacao_pct: float
    provas_realizadas: int
    provas_realizadas_variacao_pct: float
    ofensiva_media_dias: int
    ofensiva_media_variacao_dias: int


class DashboardCrescimentoPonto(BaseModel):
    data: str
    usuarios: int
    questoes_respondidas: int
    listas_concluidas: int
    provas_realizadas: int


class DashboardAtividadeHoje(BaseModel):
    usuarios_online: int
    questoes_respondidas: int
    novos_cadastros: int
    provas_iniciadas: int
    tempo_medio_estudo_min: int


class DashboardAtividadeRecente(BaseModel):
    id: UUID
    tipo: Literal[
        "materia_criada",
        "questao_editada",
        "usuario_suspenso",
        "prova_criada",
        "lista_publicada",
    ]
    titulo: str
    descricao: str
    criado_em: str


class DashboardConteudo(BaseModel):
    questoes: int
    aulas: int
    topicos: int
    materias: int
    provas: int
    listas: int


class DashboardAlerta(BaseModel):
    id: UUID
    tipo: Literal[
        "storage",
        "provas_sem_questoes",
        "aulas_sem_conteudo",
        "usuarios_denunciados",
        "integracoes_desconectadas",
    ]
    severidade: Literal["alta", "media"]
    descricao: str
    detalhe: Optional[str] = None
    link: str


class ResumoAlunoDashboard(BaseModel):
    tempo_estudado_min: int
    tarefas_concluidas: int
    tarefas_totais: int
    xp_semana: int
    ofensiva_dias: int


class EvolucaoSemanalDia(BaseModel):
    dia_semana: Literal["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]
    percentual: int


class DesempenhoMateriaAluno(BaseModel):
    materia_id: UUID
    materia: str
    percentual: int
    cor: Literal["teal", "gold", "red", "blue", "green", "purple"]


class PlanoDoDiaItem(BaseModel):
    id: UUID
    icone: str
    materia: str
    materia_cor: str
    status: Literal["concluido", "em-andamento", "nao-iniciado"]
    titulo: str
    duracao_min: int
    progresso: Optional[int] = None


class AlertaAlunoDashboard(BaseModel):
    id: UUID
    titulo: str
    mensagem: str


class AlunoDashboardResponse(BaseModel):
    resumo: ResumoAlunoDashboard
    evolucao_semanal: list[EvolucaoSemanalDia]
    desempenho_por_materia: list[DesempenhoMateriaAluno]
    plano_do_dia: list[PlanoDoDiaItem]
    alertas: list[AlertaAlunoDashboard]
