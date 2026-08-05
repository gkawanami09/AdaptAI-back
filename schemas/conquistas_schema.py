from pydantic import BaseModel
from typing import Literal

ConquistaRaridade = Literal["comum", "incomum", "raro", "epico", "lendario"]


class ConquistaDesbloqueada(BaseModel):
    icone: str
    titulo: str
    descricao: str
    raridade: ConquistaRaridade
    xp: int


class ConquistaBloqueada(BaseModel):
    icone: str
    titulo: str
    descricao: str
    raridade: ConquistaRaridade


class MissaoDiaria(BaseModel):
    label: str
    xp: int
    completed: bool


class MissaoSemanal(BaseModel):
    label: str
    xp: int
    current: int
    target: int


class ConquistasResponse(BaseModel):
    subtitulo: str
    ofensiva_dias: int
    xp_total: int
    nivel_atual: int
    xp_proximo_nivel: int
    total_medalhas: int
    conquistas_desbloqueadas: list[ConquistaDesbloqueada]
    conquistas_bloqueadas: list[ConquistaBloqueada]
    missoes_diarias: list[MissaoDiaria]
    missoes_semanais: list[MissaoSemanal]
