import re
from collections import Counter

from schemas.correcao_schema import AnaliseGramatica, ErroGramatical
from services.correcao.nlp_pipeline import carregar_pipeline

FRASE_LONGA_TOKENS = 40
FRASE_CURTA_TOKENS = 3
MIN_OCORRENCIAS_REPETICAO = 4

PONTUACAO_REPETIDA = re.compile(r"([!?.,;:]){2,}")
ESPACO_DUPLO = re.compile(r"[ \t]{2,}")
ESPACO_ANTES_PONTUACAO = re.compile(r"\s+([!?.,;:])")


class AnalisadorGramatica:
    """Detecta sinais gramaticais/de pontuação usando apenas spaCy (sem
    dependências externas de infraestrutura, como um runtime Java).

    A checagem é baseada em regras determinísticas sobre POS/morfologia
    (concordância verbal/nominal dentro de sintagmas próximos) e em
    padrões de pontuação (pontuação repetida, espaçamento incorreto).
    Isto NÃO substitui um corretor ortográfico completo: erros de
    ortografia pura (palavras escritas errado mas gramaticalmente
    válidas) não são detectados nesta fase — cobertura menor que um
    corretor dedicado, mas sem dependência de infraestrutura externa.
    """

    def analisar(self, texto: str) -> AnaliseGramatica:
        nlp = carregar_pipeline()
        doc = nlp(texto)
        frases = list(doc.sents)

        erros = self._detectar_erros_pontuacao(texto)
        erros.extend(self._detectar_erros_concordancia(doc))

        frases_muito_longas = sum(
            1 for frase in frases if len([t for t in frase if t.is_alpha]) > FRASE_LONGA_TOKENS
        )
        frases_muito_curtas = sum(
            1 for frase in frases if 0 < len([t for t in frase if t.is_alpha]) < FRASE_CURTA_TOKENS
        )

        palavras_repetidas = self._contar_repeticoes(doc)

        return AnaliseGramatica(
            erros=erros,
            total_erros=len(erros),
            frases_muito_longas=frases_muito_longas,
            frases_muito_curtas=frases_muito_curtas,
            palavras_repetidas=palavras_repetidas,
        )

    @staticmethod
    def _detectar_erros_pontuacao(texto: str) -> list[ErroGramatical]:
        erros: list[ErroGramatical] = []

        for match in PONTUACAO_REPETIDA.finditer(texto):
            erros.append(ErroGramatical(
                tipo="pontuacao",
                mensagem="Pontuação repetida sem necessidade.",
                trecho=match.group(0),
                sugestoes=[match.group(1)],
                posicao_inicio=match.start(),
                posicao_fim=match.end(),
            ))

        for match in ESPACO_ANTES_PONTUACAO.finditer(texto):
            erros.append(ErroGramatical(
                tipo="pontuacao",
                mensagem="Não deve haver espaço antes de pontuação.",
                trecho=match.group(0),
                sugestoes=[match.group(1)],
                posicao_inicio=match.start(),
                posicao_fim=match.end(),
            ))

        for match in ESPACO_DUPLO.finditer(texto):
            erros.append(ErroGramatical(
                tipo="pontuacao",
                mensagem="Espaçamento duplo entre palavras.",
                trecho=match.group(0),
                sugestoes=[" "],
                posicao_inicio=match.start(),
                posicao_fim=match.end(),
            ))

        return erros

    @staticmethod
    def _detectar_erros_concordancia(doc) -> list[ErroGramatical]:
        """Verifica concordância de número/gênero entre substantivo e
        adjetivo/determinante quando ligados por dependência sintática
        direta (amod, det) dentro do mesmo sintagma nominal.
        """
        erros: list[ErroGramatical] = []

        for token in doc:
            if token.pos_ != "NOUN":
                continue

            genero_nucleo = token.morph.get("Gender")
            numero_nucleo = token.morph.get("Number")
            if not genero_nucleo or not numero_nucleo:
                continue

            for filho in token.children:
                if filho.pos_ not in ("ADJ", "DET"):
                    continue

                genero_filho = filho.morph.get("Gender")
                numero_filho = filho.morph.get("Number")
                if not genero_filho or not numero_filho:
                    continue

                discorda_genero = genero_filho[0] != genero_nucleo[0]
                discorda_numero = numero_filho[0] != numero_nucleo[0]

                if discorda_genero or discorda_numero:
                    trecho = f"{filho.text} {token.text}" if filho.i < token.i else f"{token.text} {filho.text}"
                    inicio = min(filho.idx, token.idx)
                    fim = max(filho.idx + len(filho.text), token.idx + len(token.text))
                    erros.append(ErroGramatical(
                        tipo="concordancia",
                        mensagem=(
                            f"Possível falta de concordância entre \"{filho.text}\" e \"{token.text}\"."
                        ),
                        trecho=trecho,
                        sugestoes=[],
                        posicao_inicio=inicio,
                        posicao_fim=fim,
                    ))

        return erros

    @staticmethod
    def _contar_repeticoes(doc) -> dict[str, int]:
        lemas = [
            token.lemma_.lower()
            for token in doc
            if token.is_alpha and not token.is_stop and len(token.text) > 2
        ]
        contagem = Counter(lemas)
        return {
            palavra: total
            for palavra, total in contagem.most_common(10)
            if total >= MIN_OCORRENCIAS_REPETICAO
        }
