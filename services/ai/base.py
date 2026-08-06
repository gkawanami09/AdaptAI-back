from abc import ABC, abstractmethod

from schemas.correcao_schema import AnaliseObjetiva
from services.ai.schemas.correcao_ia_schema import AvaliacaoArgumentativaIA


class AIRespostaInvalidaError(Exception):
    """A IA respondeu, mas o conteúdo não é um JSON válido ou não
    corresponde ao schema esperado."""


class AIIndisponivelError(Exception):
    """Não foi possível se comunicar com o servidor de inferência
    (timeout, conexão recusada, erro HTTP, etc.)."""


class AIProvider(ABC):
    """Interface única que o resto da aplicação conhece. Nenhum código
    fora de services/ai/ deve importar um provider concreto ou saber
    que modelo/mecanismo de inferência está por trás — só esta interface.

    Apenas `corrigir_redacao` está implementada nos providers concretos
    nesta fase; os demais métodos são pontos de extensão preparados
    para funcionalidades futuras (chat pedagógico, geração de questões).
    """

    @abstractmethod
    def corrigir_redacao(
        self, texto: str, analise_objetiva: AnaliseObjetiva
    ) -> AvaliacaoArgumentativaIA:
        """Avalia argumentação, coerência e proposta de intervenção.

        Recebe o texto completo e o relatório já produzido pelo motor
        determinístico (services/correcao). Nunca deve recalcular o que
        já está em analise_objetiva — apenas interpretar o que só um
        modelo de linguagem consegue avaliar.
        """
        raise NotImplementedError

    @abstractmethod
    def responder_chat(self, mensagens: list[dict], contexto: dict | None = None) -> str:
        raise NotImplementedError

    @abstractmethod
    def gerar_feedback(self, texto: str, contexto: dict | None = None) -> str:
        raise NotImplementedError

    @abstractmethod
    def explicar_erro(self, questao: dict, resposta_aluno: str) -> str:
        raise NotImplementedError

    @abstractmethod
    def gerar_questoes(self, materia: str, topico: str, quantidade: int) -> list[dict]:
        raise NotImplementedError
