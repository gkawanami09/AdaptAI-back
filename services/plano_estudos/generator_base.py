from abc import ABC, abstractmethod

from services.plano_estudos.contexto import PlanoEstudosContexto, PlanoGerado


class PlanoEstudosGenerator(ABC):
    """Interface única que o service de plano de estudos conhece.
    Trocar o mecanismo de geração (determinístico hoje, IA no futuro)
    é apenas trocar a implementação injetada no service — nenhuma
    mudança em router ou endpoint é necessária.
    """

    @abstractmethod
    def gerar(self, contexto: PlanoEstudosContexto) -> PlanoGerado:
        raise NotImplementedError
