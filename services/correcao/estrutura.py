import re

from schemas.correcao_schema import AnaliseEstrutura
from services.correcao.nlp_pipeline import carregar_pipeline


class AnalisadorEstrutura:
    """Extrai métricas estruturais (parágrafos, frases, palavras) do texto.

    A detecção de introdução/desenvolvimento/conclusão é posicional
    (primeiro parágrafo = introdução, último = conclusão, meio =
    desenvolvimento), não semântica. É um sinal aproximado, não uma
    verdade absoluta sobre a qualidade da estrutura.
    """

    def analisar(self, texto: str) -> AnaliseEstrutura:
        paragrafos = self._dividir_paragrafos(texto)
        nlp = carregar_pipeline()
        doc = nlp(texto)

        frases = list(doc.sents)
        palavras = [token for token in doc if token.is_alpha]

        palavras_por_paragrafo = [
            len([t for t in nlp(paragrafo) if t.is_alpha])
            for paragrafo in paragrafos
        ]

        return AnaliseEstrutura(
            total_palavras=len(palavras),
            total_frases=len(frases),
            total_paragrafos=len(paragrafos),
            tem_introducao=len(paragrafos) >= 1,
            tem_desenvolvimento=len(paragrafos) >= 3,
            tem_conclusao=len(paragrafos) >= 2,
            palavras_por_paragrafo=palavras_por_paragrafo,
        )

    @staticmethod
    def _dividir_paragrafos(texto: str) -> list[str]:
        blocos = re.split(r"\n\s*\n", texto.strip())
        return [bloco.strip() for bloco in blocos if bloco.strip()]
