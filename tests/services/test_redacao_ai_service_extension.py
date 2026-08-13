import json
from unittest.mock import MagicMock, patch

from services.redacao_ai_service import RedacaoAIService, SuggestedTheme, WritingProblems


def _mock_provider(**kwargs):
    provider = MagicMock()
    for nome, valor in kwargs.items():
        getattr(provider, nome).return_value = valor
    return provider


TEMAS_JSON = json.dumps(
    {
        "temas": [
            {
                "titulo": "Desafios da educação digital",
                "descricao": "Impactos da tecnologia no ensino",
                "motivo": "Aluno demonstrou interesse em tecnologia",
                "nivel": "medio",
            }
        ]
    }
)

PROBLEMAS_JSON = json.dumps(
    {
        "gramatica": ["erro de concordância"],
        "coesao": [],
        "coerencia": [],
        "argumentacao": ["falta repertório"],
        "repertorio": [],
        "intervencao": [],
        "introducao": [],
        "desenvolvimento": [],
        "conclusao": [],
        "pontuacao": [],
        "ortografia": [],
    }
)


class TestSugerirTemas:
    def test_retorna_lista_de_suggested_theme(self):
        provider = _mock_provider(responder_chat=TEMAS_JSON)
        with patch("services.redacao_ai_service.get_ai_provider", return_value=provider):
            temas = RedacaoAIService().sugerir_temas({"interesses": ["tecnologia"]})

        assert len(temas) == 1
        assert isinstance(temas[0], SuggestedTheme)
        assert temas[0].titulo == "Desafios da educação digital"


class TestAnalisarProblemas:
    def test_retorna_writing_problems(self):
        provider = _mock_provider(responder_chat=PROBLEMAS_JSON)
        with patch("services.redacao_ai_service.get_ai_provider", return_value=provider):
            problemas = RedacaoAIService().analisar_problemas("texto qualquer")

        assert isinstance(problemas, WritingProblems)
        assert problemas.gramatica == ["erro de concordância"]
        assert problemas.coesao == []


class TestGerarFeedback:
    def test_delega_para_provider_gerar_feedback(self):
        provider = _mock_provider(gerar_feedback="Bom texto, mas revise a conclusão.")
        with patch("services.redacao_ai_service.get_ai_provider", return_value=provider):
            resultado = RedacaoAIService().gerar_feedback("meu texto", "tema-1")

        assert resultado == "Bom texto, mas revise a conclusão."
        provider.gerar_feedback.assert_called_once_with("meu texto", contexto={"tema_id": "tema-1"})


class TestGerarNotaEExtrairCompetencias:
    def _service_com_corrigir_mockado(self, nota_total, competencias):
        service = RedacaoAIService()
        resultado_mock = MagicMock()
        resultado_mock.nota_total = nota_total
        for chave, valor in competencias.items():
            setattr(resultado_mock, chave, valor)
        service.corrigir_redacao = MagicMock(return_value=resultado_mock)
        return service

    def test_gerar_nota_retorna_nota_total_da_correcao(self):
        service = self._service_com_corrigir_mockado(720, {})
        nota = service.gerar_nota("texto", "tema-1")
        assert nota == 720
        service.corrigir_redacao.assert_called_once_with("texto", "tema-1")

    def test_extrair_competencias_retorna_dict_das_5_competencias(self):
        competencias = {
            "competencia_1": 160,
            "competencia_2": 140,
            "competencia_3": 180,
            "competencia_4": 150,
            "competencia_5": 170,
        }
        service = self._service_com_corrigir_mockado(800, competencias)
        resultado = service.extrair_competencias("texto", "tema-1")
        assert resultado == competencias
