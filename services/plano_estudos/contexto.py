from dataclasses import dataclass, field
from datetime import date


@dataclass(frozen=True)
class ProvaContexto:
    slug: str
    nome: str
    data_prova: date | None


@dataclass(frozen=True)
class AulaContexto:
    id: str
    materia_slug: str
    titulo: str
    duracao_minutos: int
    ordem_topico: int
    ordem_aula: int


@dataclass(frozen=True)
class PlanoEstudosContexto:
    """Tudo que o gerador precisa para montar o cronograma. Já vem
    inteiramente resolvido do banco pelo service — o gerador não faz
    nenhuma consulta, o que permite testá-lo com dados fixos e trocar
    a implementação (determinística, IA, etc.) sem tocar no service.
    """

    data_inicio: date
    provas: list[ProvaContexto]
    materias_selecionadas: list[str]
    materias_por_prova: dict[str, set[str]]
    aulas_por_materia: dict[str, list[AulaContexto]]
    tempo_por_dia_minutos: int
    dias_estudo: list[str]
    duracao_maxima_semanas: int = 12


@dataclass(frozen=True)
class SessaoGerada:
    materia: str
    aula_id: str | None
    titulo: str
    duracao_minutos: int
    tipo: str


@dataclass(frozen=True)
class DiaGerado:
    data: date
    sessoes: list[SessaoGerada] = field(default_factory=list)


@dataclass(frozen=True)
class PlanoGerado:
    periodo_inicio: date
    periodo_fim: date
    dias: list[DiaGerado] = field(default_factory=list)
    avisos: list[str] = field(default_factory=list)
