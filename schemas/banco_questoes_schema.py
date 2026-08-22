from pydantic import BaseModel, Field
from typing import Optional


class BancoQuestoesFiltroOpcao(BaseModel):
    value: str
    label: str


class BancoQuestoesFiltrosResponse(BaseModel):
    vestibulares: list[BancoQuestoesFiltroOpcao]
    dificuldades: list[BancoQuestoesFiltroOpcao]
    materias: list[BancoQuestoesFiltroOpcao]
    assuntos: list[BancoQuestoesFiltroOpcao]


class BancoQuestoesLista(BaseModel):
    id: str
    slug: Optional[str] = None
    icone: str
    icone_cor: str
    titulo: str
    descricao: Optional[str] = None
    dificuldade: str
    dificuldade_cor: str
    vestibular: str
    status: str
    questoes_concluidas: int
    questoes_totais: int
    questoes_corretas: Optional[int] = None
    progresso_cor: str
    ultima_execucao_id: Optional[str] = None
    personalizada: bool = False


class BancoQuestoesListasResponse(BaseModel):
    total: int
    listas: list[BancoQuestoesLista]


class GerarListaIARequest(BaseModel):
    """Filtros opcionais pra geração de lista por IA. Só `quantidade` é
    obrigatório — os demais, quando omitidos, deixam a IA/o backend decidir
    (ex.: sem `materias`, cai no comportamento antigo de usar a matéria com
    mais erros do aluno).

    Os limites abaixo (10 questões, 5 itens por filtro) vêm de medição real
    com o modelo em produção (qwen2.5:1.5b, ~80 tokens/s gerados): 10
    questões giram em ~35-55s; passar disso facilmente estoura 1 minuto
    de resposta. Não é limite de custo/negócio, é orçamento de tempo."""

    quantidade: int = Field(ge=1, le=10)
    materias: list[str] = Field(default_factory=list, max_length=5)
    assuntos: list[str] = Field(default_factory=list, max_length=5)
    dificuldades: list[str] = Field(default_factory=list, max_length=5)
    vestibulares: list[str] = Field(default_factory=list, max_length=5)
    instrucao: Optional[str] = None


class GerarListaIAJobResponse(BaseModel):
    job_id: str
    status: str


class GeracaoIAStatusResponse(BaseModel):
    job_id: str
    status: str
    lista_id: Optional[str] = None
    slug: Optional[str] = None
    erro_mensagem: Optional[str] = None


class RefazerListaResponse(BaseModel):
    execucao_id: str
    lista_id: str
    slug: Optional[str] = None
    status: str


class BancoQuestoesQuestaoRespondida(BaseModel):
    id: str
    lista_id: Optional[str] = None
    lista_slug: Optional[str] = None
    lista_titulo: Optional[str] = None
    subject: str
    subjectColor: str
    assunto: Optional[str] = None
    question: str
    vestibular: str
    dificuldade: str
    dificuldade_cor: str
    correta: bool
    resposta_aluno: Optional[str] = None
    resposta_correta: Optional[str] = None
    respondida_em: Optional[str] = None


class BancoQuestoesPaginacao(BaseModel):
    pagina: int
    limite: int
    total: int
    total_paginas: int


class BancoQuestoesQuestoesRespondidasResponse(BaseModel):
    questoes: list[BancoQuestoesQuestaoRespondida]
    paginacao: BancoQuestoesPaginacao


class RevisaoExecucaoInfo(BaseModel):
    id: str
    lista_id: str
    lista_titulo: str
    status: str
    questoes_totais: int
    respondidas: int
    acertadas: int
    percentual_acerto: Optional[int] = None


class RevisaoAlternativa(BaseModel):
    letra: str
    texto: Optional[str] = None


class RevisaoQuestao(BaseModel):
    id: str
    enunciado: str
    materia: str
    materia_cor: str
    assunto: Optional[str] = None
    dificuldade: Optional[str] = None
    dificuldade_cor: Optional[str] = None
    alternativas: list[RevisaoAlternativa]
    resposta_aluno: Optional[str] = None
    resposta_correta: Optional[str] = None
    acertou: bool


class RevisaoExecucaoResponse(BaseModel):
    execucao: RevisaoExecucaoInfo
    questoes: list[RevisaoQuestao]
    paginacao: BancoQuestoesPaginacao
