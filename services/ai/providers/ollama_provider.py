import httpx

from schemas.correcao_schema import AnaliseObjetiva
from services.ai.base import AIIndisponivelError, AIProvider
from services.ai.json_parsing import extrair_e_validar_json
from services.ai.prompts.correcao import SYSTEM_PROMPT, montar_prompt_correcao
from services.ai.schemas.correcao_ia_schema import AvaliacaoArgumentativaIA


class OllamaProvider(AIProvider):
    """Fala com a API nativa do Ollama (POST /api/chat), usando o
    parâmetro format="json" para forçar saída estruturada.
    """

    def __init__(self, base_url: str, model: str, timeout: float, max_tokens: int, temperature: float) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._timeout = timeout
        self._max_tokens = max_tokens
        self._temperature = temperature

    def corrigir_redacao(
        self, texto: str, analise_objetiva: AnaliseObjetiva
    ) -> AvaliacaoArgumentativaIA:
        prompt = montar_prompt_correcao(texto, analise_objetiva)

        try:
            resposta = httpx.post(
                f"{self._base_url}/api/chat",
                json={
                    "model": self._model,
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": prompt},
                    ],
                    "format": "json",
                    "stream": False,
                    "options": {
                        "temperature": self._temperature,
                        "num_predict": self._max_tokens,
                    },
                },
                timeout=self._timeout,
            )
            resposta.raise_for_status()
        except httpx.HTTPError as erro:
            raise AIIndisponivelError(f"Falha ao chamar o Ollama: {erro}") from erro

        conteudo = resposta.json()["message"]["content"]
        return extrair_e_validar_json(conteudo, AvaliacaoArgumentativaIA)

    def responder_chat(self, mensagens: list[dict], contexto: dict | None = None) -> str:
        raise NotImplementedError("IA ainda não implementada")

    def gerar_feedback(self, texto: str, contexto: dict | None = None) -> str:
        raise NotImplementedError("IA ainda não implementada")

    def explicar_erro(self, questao: dict, resposta_aluno: str) -> str:
        raise NotImplementedError("IA ainda não implementada")

    def gerar_questoes(self, materia: str, topico: str, quantidade: int) -> list[dict]:
        raise NotImplementedError("IA ainda não implementada")
