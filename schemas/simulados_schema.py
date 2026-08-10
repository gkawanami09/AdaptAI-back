from pydantic import BaseModel
from typing import Literal, Optional


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


# --- Fluxo de realização do simulado -------------------------------------

class QuestaoSimuladoItem(BaseModel):
    id: str
    area: str
    subject: str
    subjectColor: str
    question: str
    options: list[str]
    respondida: bool
    opcaoSelecionada: Optional[int] = None


class IniciarSimuladoResponse(BaseModel):
    sessao_id: str
    slug: str
    titulo: str
    duracao_minutos: int
    total_questoes: int
    questoes: list[QuestaoSimuladoItem]


class ResponderQuestaoSimuladoPayload(BaseModel):
    opcao_selecionada: int


class ResponderQuestaoSimuladoResponse(BaseModel):
    id: str
    respondida: bool
    correta: bool
    questoes_respondidas: int
    total_questoes: int


class ResultadoAreaSimulado(BaseModel):
    area: str
    total_questoes: int
    respostas_corretas: int
    percentual_acerto: int
    nota: int


class FinalizarSimuladoResponse(BaseModel):
    id: str
    status: Literal["em_andamento", "concluido"]
    total_questoes: int
    respostas_corretas: int
    percentual_acerto: int
    nota_estimada: int
    duracao: str
    resultados_por_area: list[ResultadoAreaSimulado]
