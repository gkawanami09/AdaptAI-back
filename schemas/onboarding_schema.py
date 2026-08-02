from typing import Literal

from pydantic import BaseModel, Field, field_validator


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

    @field_validator("materias")
    @classmethod
    def remover_materias_repetidas(cls, materias: list[str]):
        return list(dict.fromkeys(materias))
