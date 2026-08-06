from schemas.correcao_schema import AnaliseObjetiva, RedacaoInput
from services.correcao.coesao import AnalisadorCoesao
from services.correcao.estatisticas import AnalisadorEstatisticas
from services.correcao.estrutura import AnalisadorEstrutura
from services.correcao.gramatica import AnalisadorGramatica
from services.correcao.nota import CalculadoraNota

"""Motor de correção objetiva (fase 1 — determinística, sem IA).

Este orquestrador é o único ponto de entrada da análise objetiva.
Ele NÃO faz nenhuma chamada a LLM — toda a análise aqui é reproduzível
e computada localmente em Python. O relatório (AnaliseObjetiva) gerado
por este módulo é o que, numa fase futura, será entregue ao serviço de
IA (services/redacao_ai_service.py, hoje um stub) para que o modelo
avalie apenas argumentação, coerência e proposta de intervenção —
sem reprocessar gramática, estrutura ou estatísticas.

Limitações conhecidas:
- A detecção de introdução/desenvolvimento/conclusão é posicional
  (ver services/correcao/estrutura.py), não semântica.
- A checagem gramatical usa apenas spaCy (regras de concordância via
  POS/morfologia + padrões de pontuação), sem dependência de Java/
  serviço externo. Isso cobre menos casos que um corretor ortográfico
  dedicado — erros de ortografia pura (palavra errada mas
  gramaticalmente válida) não são detectados nesta fase
  (ver services/correcao/gramatica.py).
- O índice de legibilidade usa uma adaptação do Flesch para PT-BR que
  não é um padrão universalmente aceito (ver services/correcao/estatisticas.py).
"""


class CorrecaoOrquestrador:
    def __init__(self) -> None:
        self._analisador_estrutura = AnalisadorEstrutura()
        self._analisador_gramatica = AnalisadorGramatica()
        self._analisador_coesao = AnalisadorCoesao()
        self._analisador_estatisticas = AnalisadorEstatisticas()
        self._calculadora_nota = CalculadoraNota()

    def analisar(self, entrada: RedacaoInput) -> AnaliseObjetiva:
        texto = entrada.texto

        estrutura = self._analisador_estrutura.analisar(texto)
        gramatica = self._analisador_gramatica.analisar(texto)
        coesao = self._analisador_coesao.analisar(texto)
        estatisticas = self._analisador_estatisticas.analisar(texto)

        nota = self._calculadora_nota.calcular(
            estrutura=estrutura,
            gramatica=gramatica,
            coesao=coesao,
        )

        return AnaliseObjetiva(
            estrutura=estrutura,
            gramatica=gramatica,
            coesao=coesao,
            estatisticas=estatisticas,
            nota=nota,
        )
