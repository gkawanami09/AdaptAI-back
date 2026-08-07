from services.ai.prompts.chat import SYSTEM_PROMPT

# Quantidade máxima de mensagens do histórico (usuário + assistente)
# incluídas no contexto enviado à IA. Limite simples por contagem de
# mensagens; preparado para evoluir para um limite por quantidade de
# tokens quando necessário (ver TODO em _limitar_historico).
MAX_MENSAGENS_HISTORICO = 20


class ChatContextBuilder:
    """Monta a lista de mensagens (formato {"role", "content"}) enviada
    ao provider de IA: prompt de sistema + histórico da conversa + nova
    mensagem do usuário.

    Isolar essa montagem aqui evita duplicar a lógica de limite de
    histórico e prompt de sistema em cada lugar que chama a IA.
    """

    def __init__(self, max_mensagens_historico: int = MAX_MENSAGENS_HISTORICO):
        self._max_mensagens_historico = max_mensagens_historico

    def construir(self, historico: list[dict], nova_mensagem: str) -> list[dict]:
        mensagens = [{"role": "system", "content": SYSTEM_PROMPT}]
        mensagens.extend(self._limitar_historico(historico))
        mensagens.append({"role": "user", "content": nova_mensagem})
        return mensagens

    def _limitar_historico(self, historico: list[dict]) -> list[dict]:
        # TODO: trocar para limite por quantidade de tokens (tiktoken ou
        # estimativa por caracteres) quando o histórico de conversas
        # longas começar a estourar a janela de contexto do modelo.
        historico_relevante = [msg for msg in historico if msg["role"] in ("user", "assistant")]
        return historico_relevante[-self._max_mensagens_historico :]
