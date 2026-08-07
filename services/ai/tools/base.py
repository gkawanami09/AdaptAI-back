from abc import ABC, abstractmethod
from typing import Any


class AITool(ABC):
    """Interface para uma ferramenta que a Ada pode executar dentro de
    uma conversa (gerar questões, montar plano de estudos, etc.).

    Nenhuma ferramenta concreta está implementada ainda — esta interface
    só existe para que os endpoints de tools (routers/chat.py,
    /aluno/chat/tools/*) tenham um contrato estável para implementar
    quando cada ferramenta for construída.
    """

    #: Identificador usado em ChatSugestaoAcao.tipo e no path do endpoint.
    nome: str

    @abstractmethod
    def executar(self, aluno_id: str, payload: dict) -> Any:
        raise NotImplementedError


class ToolExecutor:
    """Registro central de AITool disponíveis. Resolve uma ferramenta
    pelo nome e delega a execução — ponto único que o chat (ou uma
    futura chamada de function-calling do modelo) usa para acionar
    ferramentas, sem acoplar o controller a cada ferramenta concreta.
    """

    def __init__(self):
        self._tools: dict[str, AITool] = {}

    def registrar(self, tool: AITool) -> None:
        self._tools[tool.nome] = tool

    def executar(self, nome_tool: str, aluno_id: str, payload: dict) -> Any:
        tool = self._tools.get(nome_tool)
        if tool is None:
            raise ValueError(f"Ferramenta '{nome_tool}' não registrada")
        return tool.executar(aluno_id, payload)
