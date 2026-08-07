import httpx

from schemas.correcao_schema import AnaliseObjetiva
from services.ai.base import AIIndisponivelError, AIProvider
from services.ai.json_parsing import extrair_e_validar_json
from services.ai.prompts.correcao import SYSTEM_PROMPT, montar_prompt_correcao
from services.ai.schemas.correcao_ia_schema import AvaliacaoArgumentativaIA


class OpenAICompatibleProvider(AIProvider):
    """Fala com qualquer servidor que implemente a API
    POST /v1/chat/completions no formato da OpenAI — cobre vLLM,
    Ollama em modo compatível, ou um futuro servidor de outro provedor
    (GPT, Gemma, Llama, etc.), sem precisar de um provider novo.
    """

    def __init__(
        self,
        base_url: str,
        model: str,
        timeout: float,
        max_tokens: int,
        temperature: float,
        api_key: str | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._timeout = timeout
        self._max_tokens = max_tokens
        self._temperature = temperature
        self._api_key = api_key

    def corrigir_redacao(
        self, texto: str, analise_objetiva: AnaliseObjetiva
    ) -> AvaliacaoArgumentativaIA:
        prompt = montar_prompt_correcao(texto, analise_objetiva)

        headers = {"Authorization": f"Bearer {self._api_key}"} if self._api_key else {}

        try:
            resposta = httpx.post(
                f"{self._base_url}/v1/chat/completions",
                json={
                    "model": self._model,
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": prompt},
                    ],
                    "response_format": {"type": "json_object"},
                    "max_tokens": self._max_tokens,
                    "temperature": self._temperature,
                },
                headers=headers,
                timeout=self._timeout,
            )
            resposta.raise_for_status()
        except httpx.HTTPError as erro:
            raise AIIndisponivelError(f"Falha ao chamar o servidor de inferência: {erro}") from erro

        conteudo = resposta.json()["choices"][0]["message"]["content"]
        return extrair_e_validar_json(conteudo, AvaliacaoArgumentativaIA)

    def responder_chat(self, mensagens: list[dict], contexto: dict | None = None) -> str:
        headers = {"Authorization": f"Bearer {self._api_key}"} if self._api_key else {}

        try:
            resposta = httpx.post(
                f"{self._base_url}/v1/chat/completions",
                json={
                    "model": self._model,
                    "messages": mensagens,
                    "max_tokens": self._max_tokens,
                    "temperature": self._temperature,
                },
                headers=headers,
                timeout=self._timeout,
            )
            resposta.raise_for_status()
        except httpx.HTTPError as erro:
            raise AIIndisponivelError(f"Falha ao chamar o servidor de inferência: {erro}") from erro

        return resposta.json()["choices"][0]["message"]["content"]

    def gerar_feedback(self, texto: str, contexto: dict | None = None) -> str:
        raise NotImplementedError("IA ainda não implementada")

    def explicar_erro(self, questao: dict, resposta_aluno: str) -> str:
        raise NotImplementedError("IA ainda não implementada")

    def gerar_questoes(self, materia: str, topico: str, quantidade: int) -> list[dict]:
        raise NotImplementedError("IA ainda não implementada")
