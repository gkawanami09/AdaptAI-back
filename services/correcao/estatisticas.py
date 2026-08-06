import re
from collections import Counter

from schemas.correcao_schema import AnaliseEstatisticas
from services.correcao.nlp_pipeline import carregar_pipeline

VOGAIS = "aeiouáéíóúâêîôûãõàyAEIOUÁÉÍÓÚÂÊÎÔÛÃÕÀY"


class AnalisadorEstatisticas:
    """Calcula métricas lexicais e de legibilidade.

    O índice de legibilidade usa a adaptação do Flesch Reading Ease para
    português (Martins et al., 1996), que reescala a fórmula original
    (pensada para o inglês) considerando a maior contagem média de
    sílabas por palavra do português:

        166 - (84.6 * silabas_por_palavra) - (1.015 * palavras_por_frase)

    Não existe um padrão único aceito universalmente para PT-BR; esta é
    a adaptação mais citada na literatura e serve como sinal aproximado,
    não como medida definitiva de legibilidade.
    """

    def analisar(self, texto: str) -> AnaliseEstatisticas:
        nlp = carregar_pipeline()
        doc = nlp(texto)

        tokens_palavras = [t for t in doc if t.is_alpha]
        lemas = [t.lemma_.lower() for t in tokens_palavras]
        frases = list(doc.sents)
        paragrafos = self._dividir_paragrafos(texto)

        diversidade_lexical = len(set(lemas)) / len(lemas) if lemas else 0.0

        total_silabas = sum(self._contar_silabas(t.text) for t in tokens_palavras)
        palavras_por_frase = len(tokens_palavras) / len(frases) if frases else 0.0
        silabas_por_palavra = total_silabas / len(tokens_palavras) if tokens_palavras else 0.0
        indice_legibilidade = 166 - (84.6 * silabas_por_palavra) - (1.015 * palavras_por_frase)

        tamanho_medio_paragrafo = (
            len(tokens_palavras) / len(paragrafos) if paragrafos else 0.0
        )

        frequencia = Counter(
            t.lemma_.lower() for t in tokens_palavras if not t.is_stop and len(t.text) > 2
        )

        return AnaliseEstatisticas(
            diversidade_lexical=round(diversidade_lexical, 3),
            indice_legibilidade=round(indice_legibilidade, 2),
            tamanho_medio_frase=round(palavras_por_frase, 2),
            tamanho_medio_paragrafo=round(tamanho_medio_paragrafo, 2),
            palavras_mais_frequentes=frequencia.most_common(10),
        )

    @staticmethod
    def _contar_silabas(palavra: str) -> int:
        grupos_vogais = re.findall(f"[{VOGAIS}]+", palavra)
        return max(1, len(grupos_vogais))

    @staticmethod
    def _dividir_paragrafos(texto: str) -> list[str]:
        blocos = re.split(r"\n\s*\n", texto.strip())
        return [bloco.strip() for bloco in blocos if bloco.strip()]
