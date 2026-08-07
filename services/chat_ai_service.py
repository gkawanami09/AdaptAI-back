import logging
import time
from dataclasses import dataclass

from services.ai.base import AIIndisponivelError, AIRespostaInvalidaError
from services.ai.factory import get_ai_provider
from services.chat_context_builder import ChatContextBuilder

logger = logging.getLogger("chat_ai_service")


@dataclass
class ChatAIResultado:
    texto: str
    tempo_processamento_ms: int
    modelo: str | None


class ChatAIService:
    """Único ponto de contato entre o Chat da Ada e a camada de IA
    (services/ai/). Nenhum controller ou outro service deve chamar
    get_ai_provider() diretamente para o chat — sempre passar por aqui.
    """

    def __init__(self, context_builder: ChatContextBuilder | None = None):
        self._context_builder = context_builder or ChatContextBuilder()

    def gerar_resposta(self, historico: list[dict], nova_mensagem: str) -> ChatAIResultado:
        mensagens = self._context_builder.construir(historico, nova_mensagem)
        provider = get_ai_provider()
        modelo = getattr(provider, "_model", None)

        logger.info(
            "chat_ai_call_start model=%s mensagens_enviadas=%d",
            modelo,
            len(mensagens),
        )

        inicio = time.monotonic()
        try:
            texto = provider.responder_chat(mensagens)
        except (AIIndisponivelError, AIRespostaInvalidaError):
            duracao_ms = int((time.monotonic() - inicio) * 1000)
            logger.exception("chat_ai_call_error duracao_ms=%d", duracao_ms)
            raise

        duracao_ms = int((time.monotonic() - inicio) * 1000)
        logger.info("chat_ai_call_end model=%s duracao_ms=%d", modelo, duracao_ms)

        return ChatAIResultado(texto=texto, tempo_processamento_ms=duracao_ms, modelo=modelo)
