from schemas.correcao_schema import AnaliseCoesao, AnaliseEstrutura, AnaliseGramatica, NotaObjetiva

# Cada bloco vale no máximo 200 pontos (escala compatível com as 5
# competências do ENEM, onde cada competência vale até 200). A nota
# objetiva cobre 3 dos 5 blocos (gramática, estrutura, coesão);
# argumentação e proposta de intervenção ficam para a análise de IA
# (fase futura), totalizando até 1000 ao final.
PONTOS_MAXIMOS_POR_BLOCO = 200

PENALIDADE_POR_ERRO_GRAMATICAL = 8
PENALIDADE_POR_FRASE_LONGA = 5
PENALIDADE_POR_FRASE_CURTA = 3
PENALIDADE_POR_PALAVRA_REPETIDA = 4

PALAVRAS_MINIMAS_ESPERADAS = 200
PALAVRAS_MAXIMAS_ESPERADAS = 400
PENALIDADE_FORA_DA_FAIXA_IDEAL = 20

PONTOS_POR_PARTE_ESTRUTURAL = PONTOS_MAXIMOS_POR_BLOCO // 3

PENALIDADE_POR_PARAGRAFO_SEM_CONECTIVO = 15
BONUS_MAXIMO_DIVERSIDADE_CONECTIVOS = 40


class CalculadoraNota:
    """Converte os relatórios de cada analisador em uma nota objetiva
    parcial (0-600), usando pesos determinísticos e documentados.

    Os pesos abaixo são um ponto de partida razoável, não uma calibração
    definitiva — podem (e devem) ser ajustados com base em redações
    reais corrigidas por professores, comparando a nota objetiva com a
    nota humana.
    """

    def calcular(
        self,
        estrutura: AnaliseEstrutura,
        gramatica: AnaliseGramatica,
        coesao: AnaliseCoesao,
    ) -> NotaObjetiva:
        nota_gramatica = self._calcular_gramatica(gramatica)
        nota_estrutura = self._calcular_estrutura(estrutura)
        nota_coesao = self._calcular_coesao(coesao)

        return NotaObjetiva(
            gramatica=nota_gramatica,
            estrutura=nota_estrutura,
            coesao=nota_coesao,
            total=nota_gramatica + nota_estrutura + nota_coesao,
        )

    def _calcular_gramatica(self, gramatica: AnaliseGramatica) -> int:
        penalidade = (
            gramatica.total_erros * PENALIDADE_POR_ERRO_GRAMATICAL
            + gramatica.frases_muito_longas * PENALIDADE_POR_FRASE_LONGA
            + gramatica.frases_muito_curtas * PENALIDADE_POR_FRASE_CURTA
            + len(gramatica.palavras_repetidas) * PENALIDADE_POR_PALAVRA_REPETIDA
        )
        return self._limitar(PONTOS_MAXIMOS_POR_BLOCO - penalidade)

    def _calcular_estrutura(self, estrutura: AnaliseEstrutura) -> int:
        pontos = 0
        if estrutura.tem_introducao:
            pontos += PONTOS_POR_PARTE_ESTRUTURAL
        if estrutura.tem_desenvolvimento:
            pontos += PONTOS_POR_PARTE_ESTRUTURAL
        if estrutura.tem_conclusao:
            pontos += PONTOS_POR_PARTE_ESTRUTURAL

        if not (PALAVRAS_MINIMAS_ESPERADAS <= estrutura.total_palavras <= PALAVRAS_MAXIMAS_ESPERADAS):
            pontos -= PENALIDADE_FORA_DA_FAIXA_IDEAL

        return self._limitar(pontos)

    def _calcular_coesao(self, coesao: AnaliseCoesao) -> int:
        penalidade = coesao.paragrafos_sem_conectivo * PENALIDADE_POR_PARAGRAFO_SEM_CONECTIVO
        bonus = coesao.diversidade_conectivos * BONUS_MAXIMO_DIVERSIDADE_CONECTIVOS
        base = PONTOS_MAXIMOS_POR_BLOCO - PENALIDADE_POR_PARAGRAFO_SEM_CONECTIVO * 2
        return self._limitar(base - penalidade + bonus)

    @staticmethod
    def _limitar(pontos: float) -> int:
        return max(0, min(PONTOS_MAXIMOS_POR_BLOCO, round(pontos)))
