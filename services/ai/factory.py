from functools import lru_cache

import config
from services.ai.base import AIProvider
from services.ai.providers.ollama_provider import OllamaProvider
from services.ai.providers.openai_compatible_provider import OpenAICompatibleProvider

_PROVIDERS = {
    "ollama": OllamaProvider,
    "openai_compatible": OpenAICompatibleProvider,
}


@lru_cache(maxsize=1)
def get_ai_provider() -> AIProvider:
    """Ponto único de construção do provider de IA. Lê a configuração
    (config.AI_PROVIDER, AI_BASE_URL, AI_MODEL, ...) e instancia o
    provider correspondente. Trocar de mecanismo de inferência
    (Ollama -> vLLM -> outro servidor OpenAI compatible) é apenas uma
    mudança de variável de ambiente — nenhuma regra de negócio muda.
    """
    provider_cls = _PROVIDERS.get(config.AI_PROVIDER)
    if provider_cls is None:
        opcoes = ", ".join(_PROVIDERS.keys())
        raise ValueError(f"AI_PROVIDER inválido: '{config.AI_PROVIDER}'. Opções válidas: {opcoes}")

    return provider_cls(
        base_url=config.AI_BASE_URL,
        model=config.AI_MODEL,
        timeout=config.AI_TIMEOUT,
        max_tokens=config.AI_MAX_TOKENS,
        temperature=config.AI_TEMPERATURE,
    )
