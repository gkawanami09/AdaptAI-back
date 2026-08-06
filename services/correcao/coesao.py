import re

from schemas.correcao_schema import AnaliseCoesao
from services.correcao.conectivos import CONECTIVOS


class AnalisadorCoesao:
    """Mede o uso de conectivos textuais por parágrafo, como sinal
    aproximado de coesão. Não avalia se o conectivo foi usado com
    sentido lógico correto — apenas sua presença.
    """

    def analisar(self, texto: str) -> AnaliseCoesao:
        paragrafos = self._dividir_paragrafos(texto)
        texto_lower = texto.lower()

        conectivos_encontrados: list[str] = []
        paragrafos_sem_conectivo = 0

        for paragrafo in paragrafos:
            paragrafo_lower = paragrafo.lower()
            encontrados_no_paragrafo = [
                conectivo for conectivo in CONECTIVOS
                if self._contem_conectivo(paragrafo_lower, conectivo)
            ]
            if not encontrados_no_paragrafo:
                paragrafos_sem_conectivo += 1
            conectivos_encontrados.extend(encontrados_no_paragrafo)

        total_conectivos = len(conectivos_encontrados)
        conectivos_unicos = set(conectivos_encontrados)
        diversidade = (
            len(conectivos_unicos) / total_conectivos if total_conectivos > 0 else 0.0
        )

        return AnaliseCoesao(
            conectivos_utilizados=sorted(conectivos_unicos),
            total_conectivos=total_conectivos,
            paragrafos_sem_conectivo=paragrafos_sem_conectivo,
            diversidade_conectivos=round(diversidade, 3),
        )

    @staticmethod
    def _contem_conectivo(texto_lower: str, conectivo: str) -> bool:
        padrao = r"\b" + re.escape(conectivo) + r"\b"
        return re.search(padrao, texto_lower) is not None

    @staticmethod
    def _dividir_paragrafos(texto: str) -> list[str]:
        blocos = re.split(r"\n\s*\n", texto.strip())
        return [bloco.strip() for bloco in blocos if bloco.strip()]
