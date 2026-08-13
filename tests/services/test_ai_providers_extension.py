import json
from unittest.mock import MagicMock, patch

import httpx
import pytest

from services.ai.base import AIIndisponivelError
from services.ai.providers.ollama_provider import OllamaProvider
from services.ai.providers.openai_compatible_provider import OpenAICompatibleProvider


def _ollama():
    return OllamaProvider(
        base_url="http://localhost:11434",
        model="test-model",
        timeout=5.0,
        max_tokens=512,
        temperature=0.2,
    )


def _openai_compat():
    return OpenAICompatibleProvider(
        base_url="http://localhost:8000",
        model="test-model",
        timeout=5.0,
        max_tokens=512,
        temperature=0.2,
    )


def _mock_response_ollama(content: str):
    resposta = MagicMock()
    resposta.raise_for_status.return_value = None
    resposta.json.return_value = {"message": {"content": content}}
    return resposta


def _mock_response_openai(content: str):
    resposta = MagicMock()
    resposta.raise_for_status.return_value = None
    resposta.json.return_value = {"choices": [{"message": {"content": content}}]}
    return resposta


QUESTOES_JSON = json.dumps(
    {
        "questoes": [
            {
                "enunciado": "Quanto é 2+2?",
                "alternativas": ["3", "4", "5"],
                "resposta_correta": "4",
                "explicacao": "Soma simples.",
                "dificuldade": "facil",
            }
        ]
    }
)


class TestOllamaProviderExtension:
    def test_gerar_feedback_retorna_texto(self):
        with patch("httpx.post", return_value=_mock_response_ollama("Ótimo trabalho!")):
            resultado = _ollama().gerar_feedback("meu texto")
        assert resultado == "Ótimo trabalho!"

    def test_explicar_erro_retorna_texto(self):
        with patch("httpx.post", return_value=_mock_response_ollama("Você errou porque...")):
            resultado = _ollama().explicar_erro(
                {"enunciado": "2+2?", "alternativas": ["3", "4"], "resposta_correta": "4"}, "3"
            )
        assert resultado == "Você errou porque..."

    def test_gerar_questoes_retorna_lista_de_dicts(self):
        with patch("httpx.post", return_value=_mock_response_ollama(QUESTOES_JSON)):
            resultado = _ollama().gerar_questoes("matematica", "aritmetica", 1)
        assert resultado == [
            {
                "enunciado": "Quanto é 2+2?",
                "alternativas": ["3", "4", "5"],
                "resposta_correta": "4",
                "explicacao": "Soma simples.",
                "dificuldade": "facil",
            }
        ]

    def test_gerar_feedback_levanta_erro_quando_indisponivel(self):
        with patch("httpx.post", side_effect=httpx.ConnectError("boom")):
            with pytest.raises(AIIndisponivelError):
                _ollama().gerar_feedback("meu texto")

    def test_gerar_questoes_levanta_erro_quando_indisponivel(self):
        with patch("httpx.post", side_effect=httpx.ConnectError("boom")):
            with pytest.raises(AIIndisponivelError):
                _ollama().gerar_questoes("matematica", "aritmetica", 1)


class TestOpenAICompatibleProviderExtension:
    def test_gerar_feedback_retorna_texto(self):
        with patch("httpx.post", return_value=_mock_response_openai("Bom trabalho!")):
            resultado = _openai_compat().gerar_feedback("meu texto")
        assert resultado == "Bom trabalho!"

    def test_explicar_erro_retorna_texto(self):
        with patch("httpx.post", return_value=_mock_response_openai("O erro foi...")):
            resultado = _openai_compat().explicar_erro(
                {"enunciado": "2+2?", "alternativas": ["3", "4"], "resposta_correta": "4"}, "3"
            )
        assert resultado == "O erro foi..."

    def test_gerar_questoes_retorna_lista_de_dicts(self):
        with patch("httpx.post", return_value=_mock_response_openai(QUESTOES_JSON)):
            resultado = _openai_compat().gerar_questoes("matematica", "aritmetica", 1)
        assert resultado[0]["resposta_correta"] == "4"

    def test_explicar_erro_levanta_erro_quando_indisponivel(self):
        with patch("httpx.post", side_effect=httpx.ConnectError("boom")):
            with pytest.raises(AIIndisponivelError):
                _openai_compat().explicar_erro({"enunciado": "x"}, "y")
