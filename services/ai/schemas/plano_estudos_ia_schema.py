from pydantic import BaseModel, Field
from typing import Literal


class SessaoPlanoIA(BaseModel):
    """A IA só referencia o id de uma aula real do catálogo enviado no
    prompt — título e duração nunca vêm da IA, sempre são resolvidos
    pelo backend a partir do banco. Isso evita qualquer alucinação de
    conteúdo que não existe.
    """

    aula_id: str
    tipo: Literal["teoria", "revisao"] = "teoria"


class DiaPlanoIA(BaseModel):
    data: str
    sessoes: list[SessaoPlanoIA] = Field(default_factory=list)


class PlanoEstudosIA(BaseModel):
    dias: list[DiaPlanoIA] = Field(default_factory=list)
