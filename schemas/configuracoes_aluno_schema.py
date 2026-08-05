from pydantic import BaseModel
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
    metas: ConfiguracoesAlunoMetas
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
