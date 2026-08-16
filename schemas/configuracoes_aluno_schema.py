from pydantic import BaseModel, Field
from typing import Literal

ConfiguracoesAlunoTema = Literal["claro", "escuro", "sistema"]


class ConfiguracoesAlunoPerfil(BaseModel):
    nome: str
    email: str
    nivel: int
    xp_total: int
    escola: str
    ano_enem: str


class ConfiguracoesAlunoNotificacao(BaseModel):
    id: str
    label: str
    description: str
    enabled: bool


class ConfiguracoesAlunoMetas(BaseModel):
    objetivo: str
    tempo_estudo: str
    nota_alvo: str


class ConfiguracoesAlunoAparencia(BaseModel):
    tema: ConfiguracoesAlunoTema


class ConfiguracoesAlunoResponse(BaseModel):
    perfil: ConfiguracoesAlunoPerfil
    notificacoes: list[ConfiguracoesAlunoNotificacao]
    aparencia: ConfiguracoesAlunoAparencia


class PatchNotificacaoAlunoPayload(BaseModel):
    id: str
    enabled: bool


class PatchNotificacaoAlunoResponse(BaseModel):
    id: str
    enabled: bool


class PatchMetasAlunoPayload(BaseModel):
    objetivo: str | None = None
    tempo_estudo: str | None = None
    nota_alvo: str | None = None


class PatchAparenciaAlunoPayload(BaseModel):
    tema: ConfiguracoesAlunoTema


class PatchAparenciaAlunoResponse(BaseModel):
    tema: ConfiguracoesAlunoTema


class PatchPerfilAlunoPayload(BaseModel):
    nome: str = Field(min_length=2, max_length=120)
    escola: str | None = Field(default=None, max_length=120)
    ano_enem: str | None = Field(default=None, max_length=4)


class AlterarSenhaAlunoPayload(BaseModel):
    senha_atual: str
    nova_senha: str


class AlterarSenhaAlunoResponse(BaseModel):
    sucesso: bool


class ExcluirContaAlunoPayload(BaseModel):
    senha: str


class ExcluirContaAlunoResponse(BaseModel):
    sucesso: bool


class DadosIACategoria(BaseModel):
    id: str
    nome: str
    descricao: str
    categoria: str
    utilizado: bool


class InsightIA(BaseModel):
    id: str
    titulo: str
    descricao: str
    materia: str | None = None
    tipo: str


class DadosIAResponse(BaseModel):
    dados: list[DadosIACategoria]
    insights: list[InsightIA]


class PatchDadosIAPayload(BaseModel):
    id: str
    utilizado: bool


class PatchDadosIAResponse(BaseModel):
    id: str
    utilizado: bool
