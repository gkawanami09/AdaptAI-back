from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from schemas.plano_estudos_schema import DiaSemana, PlanoEstudosGeradoStatus


class OnboardingPreferencias(BaseModel):
    tipo_prova_id: str
    objetivo_principal: str
    minutos_estudo_dia: int
    onboarding_concluido_em: datetime | None = None


class OnboardingMateriaDificuldade(BaseModel):
    id: str
    nome: str
    slug: str
    icone: str | None = None
    cor: str | None = None


class OnboardingPlano(BaseModel):
    id: str
    tipo_prova_id: str | None = None
    titulo: str
    data_inicio: date | None = None
    data_fim: date | None = None
    status: str
    status_geracao: PlanoEstudosGeradoStatus | None = None
    mensagem_erro: str | None = None
    criado_por: str


class OnboardingEstado(BaseModel):
    concluido: bool
    preferencias: OnboardingPreferencias | None = None
    materias_dificuldade: list[OnboardingMateriaDificuldade]
    plano: OnboardingPlano | None = None
    personalizacao_ia_ativa: bool


class OnboardingResponse(BaseModel):
    sucesso: bool
    onboarding: OnboardingEstado


class OnboardingConcluirResponse(BaseModel):
    sucesso: bool
    mensagem: str
    onboarding: OnboardingEstado


class OnboardingConcluir(BaseModel):
    objetivo: Literal[
        "enem",
        "fuvest",
        "unicamp",
        "vestibulares",
    ] = Field(alias="objective")

    tempo_estudo: Literal[
        "30-minutos",
        "1-hora",
        "2-horas",
        "3-horas-ou-mais",
    ] = Field(alias="studyTime")

    materias: list[Literal[
        "matematica",
        "fisica",
        "quimica",
        "biologia",
        "historia",
        "geografia",
        "portugues",
        "redacao",
        "ingles",
    ]] = Field(alias="subjects", min_length=1, max_length=9)

    meta_principal: Literal[
        "melhorar-nota",
        "universidade-publica",
        "estudar-do-zero",
        "revisar",
        "treinar-redacao",
    ] = Field(alias="mainGoal")

    dias_estudo: list[DiaSemana] = Field(alias="studyDays", min_length=1)

    @field_validator("materias")
    @classmethod
    def remover_materias_repetidas(cls, materias: list[str]):
        return list(dict.fromkeys(materias))

    @field_validator("dias_estudo")
    @classmethod
    def sem_dias_duplicados(cls, valor: list[str]) -> list[str]:
        if len(valor) != len(set(valor)):
            raise ValueError("Não pode haver dias de estudo duplicados")
        return valor
