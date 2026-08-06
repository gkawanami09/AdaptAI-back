from typing import Literal
from pydantic import BaseModel, Field

TagCor = Literal['purple', 'green', 'blue', 'teal', 'gold', 'red', 'gray']
CompetenciaCor = Literal['blue', 'teal', 'purple', 'gold', 'red']


class RedacaoTemaResumo(BaseModel):
    id: str
    slug: str
    titulo: str
    tag: str
    tag_cor: TagCor
    descricao: str


class GetRedacaoTemasResponse(BaseModel):
    temas: list[RedacaoTemaResumo]


class CompetenciaItem(BaseModel):
    number: int
    title: str
    description: str
    color: CompetenciaCor


class GetRedacaoTemaResponse(BaseModel):
    slug: str
    titulo: str
    tag: str
    tag_cor: TagCor
    descricao: str
    competencias: list[CompetenciaItem]
    repertorios: list[str]
    dica_ada: str | None


class PostRedacaoEnvioParams(BaseModel):
    texto: str = Field(min_length=1)


class PostRedacaoEnvioResponse(BaseModel):
    id: str
    slug: str
    status: str
    texto: str


RedacaoCorrecaoStatus = Literal['pendente', 'processando', 'concluida', 'erro']
IconColor = Literal['purple', 'green', 'blue', 'gold', 'red']


class RedacaoCompetenciaNota(BaseModel):
    number: int
    title: str
    description: str
    color: CompetenciaCor
    nota: int
    notaMaxima: int


class RedacaoInsight(BaseModel):
    id: str
    icon: str
    iconColor: IconColor
    title: str
    description: str


class RedacaoPontoMelhoria(BaseModel):
    id: str
    icon: str
    iconColor: IconColor
    title: str
    description: str


class RedacaoRepertorioSugerido(BaseModel):
    id: str
    nome: str
    descricao: str


class GetRedacaoCorrecaoResponse(BaseModel):
    id: str
    slug: str
    status: RedacaoCorrecaoStatus
    notaTotal: int
    notaMaxima: int
    statusLabel: str
    mensagemMotivacional: str
    competencias: list[RedacaoCompetenciaNota]
    insights: list[RedacaoInsight]
    pontosMelhoria: list[RedacaoPontoMelhoria]
    repertoriosSugeridos: list[RedacaoRepertorioSugerido]
    resumoAda: str
