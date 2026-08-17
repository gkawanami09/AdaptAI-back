from pydantic import BaseModel
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


class BancoQuestoesListasResponse(BaseModel):
    total: int
    listas: list[BancoQuestoesLista]


class GerarListaIAResponse(BaseModel):
    id: str
    slug: Optional[str] = None


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
