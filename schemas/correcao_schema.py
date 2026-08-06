from pydantic import BaseModel


class RedacaoInput(BaseModel):
    texto: str
    tema_titulo: str | None = None


class ErroGramatical(BaseModel):
    tipo: str
    mensagem: str
    trecho: str
    sugestoes: list[str]
    posicao_inicio: int
    posicao_fim: int


class AnaliseEstrutura(BaseModel):
    total_palavras: int
    total_frases: int
    total_paragrafos: int
    tem_introducao: bool
    tem_desenvolvimento: bool
    tem_conclusao: bool
    palavras_por_paragrafo: list[int]


class AnaliseGramatica(BaseModel):
    erros: list[ErroGramatical]
    total_erros: int
    frases_muito_longas: int
    frases_muito_curtas: int
    palavras_repetidas: dict[str, int]


class AnaliseCoesao(BaseModel):
    conectivos_utilizados: list[str]
    total_conectivos: int
    paragrafos_sem_conectivo: int
    diversidade_conectivos: float


class AnaliseEstatisticas(BaseModel):
    diversidade_lexical: float
    indice_legibilidade: float
    tamanho_medio_frase: float
    tamanho_medio_paragrafo: float
    palavras_mais_frequentes: list[tuple[str, int]]


class NotaObjetiva(BaseModel):
    gramatica: int
    estrutura: int
    coesao: int
    total: int


class AnaliseObjetiva(BaseModel):
    estrutura: AnaliseEstrutura
    gramatica: AnaliseGramatica
    coesao: AnaliseCoesao
    estatisticas: AnaliseEstatisticas
    nota: NotaObjetiva
