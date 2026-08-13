import time
from functools import lru_cache, wraps

import config
from services.ai.base import AIProvider
from services.ai.providers.ollama_provider import OllamaProvider
from services.ai.providers.openai_compatible_provider import OpenAICompatibleProvider
from services.monitoramento import monitor

_PROVIDERS = {
    "ollama": OllamaProvider,
    "openai_compatible": OpenAICompatibleProvider,
}

_METODOS_INSTRUMENTADOS = (
    "corrigir_redacao",
    "responder_chat",
    "gerar_feedback",
    "explicar_erro",
    "gerar_questoes",
)


def _instrumentar(provider: AIProvider) -> AIProvider:
    """Envolve cada método público do provider com telemetria de
    latência/erro (services/monitoramento.py), sem que os providers
    concretos precisem saber que estão sendo medidos.
    """
    for nome_metodo in _METODOS_INSTRUMENTADOS:
        metodo_original = getattr(provider, nome_metodo)

        def _wrapper(*args, _metodo=metodo_original, _nome=nome_metodo, **kwargs):
            inicio = time.perf_counter()
            sucesso = True
            try:
                return _metodo(*args, **kwargs)
            except Exception:
                sucesso = False
                raise
            finally:
                duracao_ms = (time.perf_counter() - inicio) * 1000
                monitor.registrar_chamada_ia(_nome, duracao_ms, sucesso)

        setattr(provider, nome_metodo, wraps(metodo_original)(_wrapper))

    return provider


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

    provider = provider_cls(
        base_url=config.AI_BASE_URL,
        model=config.AI_MODEL,
        timeout=config.AI_TIMEOUT,
        max_tokens=config.AI_MAX_TOKENS,
        temperature=config.AI_TEMPERATURE,
    )
    return _instrumentar(provider)
