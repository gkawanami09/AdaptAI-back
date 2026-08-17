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
    duracao_minutos: Optional[int] = None
    total_questoes: Optional[int] = None
    materias: Optional[list[str]] = None


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


# --- Tentativas de simulado ------------------------------------------

StatusTentativa = Literal["em_andamento", "concluida", "expirada", "cancelada"]


class SimuladoRef(BaseModel):
    slug: str
    nome: str


class AlternativaTentativa(BaseModel):
    id: str
    texto: Optional[str] = None


class QuestaoTentativaItem(BaseModel):
    id: str
    numero: int
    materia: str
    materia_cor: Optional[str] = None
    enunciado: str
    alternativas: list[AlternativaTentativa]
    alternativa_marcada: Optional[str] = None


class IniciarTentativaResponse(BaseModel):
    id: str
    simulado: SimuladoRef
    status: StatusTentativa
    iniciado_em: str
    tempo_limite_segundos: int
    total_questoes: int
    questao_atual: int
    questoes: list[QuestaoTentativaItem]


class RecuperarTentativaResponse(BaseModel):
    id: str
    simulado: SimuladoRef
    status: StatusTentativa
    iniciado_em: str
    tempo_limite_segundos: int
    tempo_gasto_segundos: int
    total_questoes: int
    respondidas: int
    questoes: list[QuestaoTentativaItem]


class ResponderTentativaPayload(BaseModel):
    questao_id: str
    alternativa_id: str


class ResponderTentativaResponse(BaseModel):
    questao_id: str
    alternativa_id: str
    salva: bool


class DesempenhoMateriaTentativa(BaseModel):
    materia: str
    total: int
    acertos: int
    erros: int
    percentual_acerto: float


class FinalizarTentativaResponse(BaseModel):
    id: str
    status: StatusTentativa
    total_questoes: int
    respondidas: int
    acertos: int
    erros: int
    nao_respondidas: int
    percentual_acerto: float
    tempo_gasto_segundos: int
    desempenho_materias: list[DesempenhoMateriaTentativa]


class ResultadoTentativaResponse(BaseModel):
    id: str
    simulado: SimuladoRef
    status: StatusTentativa
    total_questoes: int
    respondidas: int
    acertos: int
    erros: int
    nao_respondidas: int
    percentual_acerto: float
    tempo_gasto_segundos: int
    desempenho_materias: list[DesempenhoMateriaTentativa]
    iniciado_em: str
    finalizado_em: Optional[str] = None


class RevisaoAlternativaTentativa(BaseModel):
    id: str
    texto: Optional[str] = None


class RevisaoQuestaoTentativa(BaseModel):
    numero: int
    questao_id: str
    materia: str
    enunciado: str
    alternativas: list[RevisaoAlternativaTentativa]
    alternativa_correta: Optional[str] = None
    alternativa_marcada: Optional[str] = None
    acertou: bool
    explicacao: Optional[str] = None


class RevisaoTentativaResponse(BaseModel):
    id: str
    questoes: list[RevisaoQuestaoTentativa]


class HistoricoTentativaItem(BaseModel):
    id: str
    simulado_slug: str
    simulado_nome: str
    status: StatusTentativa
    data: str
    total_questoes: int
    acertos: int
    percentual_acerto: float
    tempo_gasto_segundos: int


class HistoricoTentativasResponse(BaseModel):
    tentativas: list[HistoricoTentativaItem]
