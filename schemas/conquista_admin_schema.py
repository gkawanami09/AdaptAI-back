from pydantic import BaseModel, Field, field_validator
from typing import Literal
from uuid import UUID

from services.gamificacao.metricas import MEDIDORES

RaridadeConquista = Literal["comum", "incomum", "raro", "epico", "lendario"]


def _validar_tipo_condicao(valor: str) -> str:
    if valor not in MEDIDORES:
        opcoes = ", ".join(sorted(MEDIDORES.keys()))
        raise ValueError(f"tipo_condicao inválido: '{valor}'. Opções válidas: {opcoes}")
    return valor


class ConquistaCriar(BaseModel):
    titulo: str = Field(min_length=2, max_length=150)
    descricao: str | None = None
    icone: str | None = None
    raridade: RaridadeConquista = "comum"
    xp_recompensa: int = Field(default=0, ge=0)
    tipo_condicao: str
    valor_condicao: int = Field(gt=0)
    materia_id: UUID | None = None
    ativo: bool = True

    @field_validator("tipo_condicao")
    @classmethod
    def tipo_condicao_valido(cls, valor: str) -> str:
        return _validar_tipo_condicao(valor)


class ConquistaEditar(BaseModel):
    titulo: str | None = Field(default=None, min_length=2, max_length=150)
    descricao: str | None = None
    icone: str | None = None
    raridade: RaridadeConquista | None = None
    xp_recompensa: int | None = Field(default=None, ge=0)
    tipo_condicao: str | None = None
    valor_condicao: int | None = Field(default=None, gt=0)
    materia_id: UUID | None = None
    ativo: bool | None = None

    @field_validator("tipo_condicao")
    @classmethod
    def tipo_condicao_valido(cls, valor: str | None) -> str | None:
        if valor is None:
            return valor
        return _validar_tipo_condicao(valor)
