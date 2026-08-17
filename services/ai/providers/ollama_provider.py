import httpx

from schemas.correcao_schema import AnaliseObjetiva
from services.ai.base import AIIndisponivelError, AIProvider
from services.ai.json_parsing import extrair_e_validar_json
from services.ai.prompts.correcao import SYSTEM_PROMPT, montar_prompt_correcao
from services.ai.prompts.explicacao import SYSTEM_PROMPT as EXPLICACAO_SYSTEM_PROMPT
from services.ai.prompts.explicacao import montar_prompt_explicacao_erro
from services.ai.prompts.feedback import SYSTEM_PROMPT as FEEDBACK_SYSTEM_PROMPT
from services.ai.prompts.feedback import montar_prompt_feedback
from services.ai.prompts.questoes import SYSTEM_PROMPT as QUESTOES_SYSTEM_PROMPT
from services.ai.prompts.questoes import montar_prompt_gerar_questoes
from services.ai.schemas.correcao_ia_schema import AvaliacaoArgumentativaIA
from services.ai.schemas.questoes_geradas_schema import QuestoesGeradasIA


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

        conteudo = self._extrair_conteudo(resposta)
        return extrair_e_validar_json(conteudo, AvaliacaoArgumentativaIA)

    def responder_chat(self, mensagens: list[dict], contexto: dict | None = None) -> str:
        try:
            resposta = httpx.post(
                f"{self._base_url}/api/chat",
                json={
                    "model": self._model,
                    "messages": mensagens,
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

        return self._extrair_conteudo(resposta)

    def gerar_feedback(self, texto: str, contexto: dict | None = None) -> str:
        prompt = montar_prompt_feedback(texto, contexto)
        mensagens = [
            {"role": "system", "content": FEEDBACK_SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ]
        return self.responder_chat(mensagens)

    def explicar_erro(self, questao: dict, resposta_aluno: str) -> str:
        prompt = montar_prompt_explicacao_erro(questao, resposta_aluno)
        mensagens = [
            {"role": "system", "content": EXPLICACAO_SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ]
        return self.responder_chat(mensagens)

    def gerar_questoes(self, materia: str, topico: str, quantidade: int) -> list[dict]:
        prompt = montar_prompt_gerar_questoes(materia, topico, quantidade)

        try:
            resposta = httpx.post(
                f"{self._base_url}/api/chat",
                json={
                    "model": self._model,
                    "messages": [
                        {"role": "system", "content": QUESTOES_SYSTEM_PROMPT},
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

        conteudo = self._extrair_conteudo(resposta)
        resultado = extrair_e_validar_json(conteudo, QuestoesGeradasIA)
        return [q.model_dump() for q in resultado.questoes]

    @staticmethod
    def _extrair_conteudo(resposta: httpx.Response) -> str:
        """Um HTTP 200 do Ollama não garante um corpo bem formado — sob
        carga, ou com o modelo errado carregado, ele pode responder com um
        JSON sem a chave "message"/"content". Tratamos isso como
        indisponibilidade (mesmo caminho de erro de conexão/timeout) para
        que o gerador de plano caia no fallback determinístico em vez de
        estourar um KeyError não tratado.
        """
        corpo = resposta.json()
        conteudo = corpo.get("message", {}).get("content")
        if not conteudo:
            raise AIIndisponivelError(f"Resposta do Ollama sem conteúdo utilizável: {corpo}")
        return conteudo
