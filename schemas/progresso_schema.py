from pydantic import BaseModel
from typing import Literal


class ProgressoResumo(BaseModel):
    meta_mensal_percentual: int
    horas_estudadas: str
    ofensiva_dias: int
    xp_total: int


class ProgressoEvolucaoSerie(BaseModel):
    name: str
    color: Literal["blue", "green", "red"]
    values: list[int]


class ProgressoEvolucaoAcertos(BaseModel):
    categories: list[str]
    series: list[ProgressoEvolucaoSerie]


class ProgressoHorasPorDia(BaseModel):
    label: str
    value: float


class ProgressoRankingMateria(BaseModel):
    label: str
    percent: int
    color: str


class ProgressoHeatmap(BaseModel):
    weekday_labels: list[str]
    weeks: list[list[int]]


class ProgressoMetaMensal(BaseModel):
    label: str
    value: int
    target: int
    color: str


class ProgressoResponse(BaseModel):
    resumo: ProgressoResumo
    evolucao_acertos: ProgressoEvolucaoAcertos
    horas_por_dia: list[ProgressoHorasPorDia]
    ranking_materias: list[ProgressoRankingMateria]
    heatmap: ProgressoHeatmap
    metas_mensais: list[ProgressoMetaMensal]
