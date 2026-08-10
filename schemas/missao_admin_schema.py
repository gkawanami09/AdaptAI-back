from pydantic import BaseModel, Field
from typing import Literal

TipoMissao = Literal["diaria", "semanal"]

MetricaMissao = Literal[
    "questoes_respondidas",
    "aulas_concluidas",
    "minutos_estudo",
    "anotacoes_revisadas",
    "plano_semanal_concluido",
    "redacoes_enviadas",
    "simulados_concluidos",
]


class MissaoCriar(BaseModel):
    titulo: str = Field(min_length=2, max_length=150)
    tipo_missao: TipoMissao
    metrica: MetricaMissao
    valor_alvo: int = Field(gt=0)
    xp_recompensa: int = Field(default=0, ge=0)
    ativo: bool = True


class MissaoEditar(BaseModel):
    titulo: str | None = Field(default=None, min_length=2, max_length=150)
    tipo_missao: TipoMissao | None = None
    metrica: MetricaMissao | None = None
    valor_alvo: int | None = Field(default=None, gt=0)
    xp_recompensa: int | None = Field(default=None, ge=0)
    ativo: bool | None = None
