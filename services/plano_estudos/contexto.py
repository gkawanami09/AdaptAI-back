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
    mais_cobrado: bool = False
    dificuldade: str = "medio"
    topico_id: str | None = None


@dataclass(frozen=True)
class ListaContexto:
    id: str
    materia_slug: str


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
    # Desempenho real do aluno em tentativas_questoes (0=nunca erra,
    # 1=sempre erra), usado para priorizar matérias/tópicos onde ele mais
    # erra. Vazio por padrão (ex.: aluno sem tentativas ainda, ou testes
    # que não se importam com esse aspecto) — nesse caso o gerador se
    # comporta exatamente como antes, sem nenhum boost por erro.
    taxa_erro_por_materia: dict[str, float] = field(default_factory=dict)
    taxa_erro_por_topico: dict[str, float] = field(default_factory=dict)
    # Uma lista de questões candidata por matéria, para sessões extras de
    # prática nas matérias em que o aluno mais erra.
    listas_por_materia: dict[str, ListaContexto] = field(default_factory=dict)


@dataclass(frozen=True)
class SessaoGerada:
    materia: str
    aula_id: str | None
    titulo: str
    duracao_minutos: int
    tipo: str
    lista_questoes_id: str | None = None


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
