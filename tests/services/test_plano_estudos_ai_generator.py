import json
from datetime import date, timedelta
from unittest.mock import MagicMock, patch

from services.ai.base import AIIndisponivelError
from services.plano_estudos.ai_generator import AIPlanGenerator
from services.plano_estudos.contexto import AulaContexto, PlanoEstudosContexto, ProvaContexto

HOJE = date(2026, 1, 5)  # segunda-feira


def _aula(id_, materia, titulo, duracao, ordem_topico=0, ordem_aula=0):
    return AulaContexto(
        id=id_,
        materia_slug=materia,
        titulo=titulo,
        duracao_minutos=duracao,
        ordem_topico=ordem_topico,
        ordem_aula=ordem_aula,
    )


def _contexto():
    return PlanoEstudosContexto(
        data_inicio=HOJE,
        provas=[ProvaContexto("enem", "ENEM", HOJE + timedelta(days=90))],
        materias_selecionadas=["matematica"],
        materias_por_prova={"enem": {"matematica"}},
        aulas_por_materia={
            "matematica": [
                _aula("a1", "matematica", "Aula 1", 30, ordem_aula=1),
                _aula("a2", "matematica", "Aula 2", 30, ordem_aula=2),
            ]
        },
        tempo_por_dia_minutos=60,
        dias_estudo=["monday", "tuesday", "wednesday", "thursday", "friday"],
    )


def _mock_provider(resposta_texto):
    provider = MagicMock()
    provider.responder_chat.return_value = resposta_texto
    return provider


def test_usa_apenas_aulas_reais_do_catalogo_e_ignora_id_inexistente():
    resposta_ia = json.dumps({
        "dias": [
            {
                "data": (HOJE + timedelta(days=1)).isoformat(),
                "sessoes": [
                    {"aula_id": "a1", "tipo": "teoria"},
                    {"aula_id": "id-inventado-pela-ia", "tipo": "teoria"},
                ],
            }
        ]
    })

    with patch("services.plano_estudos.ai_generator.get_ai_provider", return_value=_mock_provider(resposta_ia)):
        plano = AIPlanGenerator().gerar(_contexto())

    todas_sessoes = [s for dia in plano.dias for s in dia.sessoes]
    assert len(todas_sessoes) == 1
    assert todas_sessoes[0].aula_id == "a1"
    assert todas_sessoes[0].titulo == "Aula 1"  # veio do catálogo, não da IA


def test_nunca_ultrapassa_tempo_diario_mesmo_se_ia_mandar_mais():
    resposta_ia = json.dumps({
        "dias": [
            {
                "data": (HOJE + timedelta(days=1)).isoformat(),
                "sessoes": [
                    {"aula_id": "a1", "tipo": "teoria"},
                    {"aula_id": "a2", "tipo": "teoria"},
                    {"aula_id": "a1", "tipo": "revisao"},  # estouraria 60min (30+30+30=90)
                ],
            }
        ]
    })

    with patch("services.plano_estudos.ai_generator.get_ai_provider", return_value=_mock_provider(resposta_ia)):
        plano = AIPlanGenerator().gerar(_contexto())

    for dia in plano.dias:
        assert sum(s.duracao_minutos for s in dia.sessoes) <= 60


def test_ignora_data_fora_do_periodo_ou_dia_nao_selecionado():
    resposta_ia = json.dumps({
        "dias": [
            {"data": (HOJE + timedelta(days=200)).isoformat(), "sessoes": [{"aula_id": "a1", "tipo": "teoria"}]},
            {"data": (HOJE + timedelta(days=5)).isoformat(), "sessoes": [{"aula_id": "a1", "tipo": "teoria"}]},  # sábado
        ]
    })

    with patch("services.plano_estudos.ai_generator.get_ai_provider", return_value=_mock_provider(resposta_ia)):
        plano = AIPlanGenerator().gerar(_contexto())

    assert plano.dias == []


def test_fallback_para_determinístico_quando_ia_indisponivel():
    provider = MagicMock()
    provider.responder_chat.side_effect = AIIndisponivelError("timeout")

    with patch("services.plano_estudos.ai_generator.get_ai_provider", return_value=provider):
        plano = AIPlanGenerator().gerar(_contexto())

    assert plano.dias, "fallback determinístico deveria gerar sessões"
    assert any("motor determinístico" in aviso for aviso in plano.avisos)


def test_repete_a_chamada_quando_resposta_vem_vazia_e_acerta_na_segunda():
    resposta_valida = json.dumps({
        "dias": [{"data": (HOJE + timedelta(days=1)).isoformat(), "sessoes": [{"aula_id": "a1", "tipo": "teoria"}]}]
    })
    provider = MagicMock()
    provider.responder_chat.side_effect = ["", resposta_valida]

    with patch("services.plano_estudos.ai_generator.get_ai_provider", return_value=provider):
        plano = AIPlanGenerator().gerar(_contexto())

    assert provider.responder_chat.call_count == 2
    todas_sessoes = [s for dia in plano.dias for s in dia.sessoes]
    assert len(todas_sessoes) == 1
    assert todas_sessoes[0].aula_id == "a1"
