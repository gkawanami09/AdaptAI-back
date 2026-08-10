from datetime import date
from unittest.mock import patch

from services.gamificacao import missoes_service
from services.gamificacao.eventos import EventoGamificacao
from tests.services._supabase_mock import FakeSupabase, query_result


def test_periodo_diaria_e_o_proprio_dia():
    inicio, fim = missoes_service._periodo_para("diaria", date(2026, 8, 12))
    assert inicio == fim == date(2026, 8, 12)


def test_periodo_semanal_cobre_a_semana_inteira():
    quarta = date(2026, 8, 12)  # quarta-feira
    inicio, fim = missoes_service._periodo_para("semanal", quarta)
    assert inicio.weekday() == 0  # segunda
    assert fim.weekday() == 6  # domingo
    assert (fim - inicio).days == 6
    assert inicio <= quarta <= fim


def test_atualizar_missoes_incrementa_e_conclui_uma_vez_so():
    fake = FakeSupabase()
    fake.table("missoes").execute.return_value = query_result(data=[
        {"id": "missao-1", "tipo_missao": "diaria", "valor_alvo": 10, "xp_recompensa": 50},
    ])
    # primeira chamada: sem progresso existente ainda
    fake.table("progresso_missoes_usuario").execute.return_value = query_result(data=[])

    with patch("services.gamificacao.missoes_service.supabase_admin", fake), \
         patch("services.gamificacao.missoes_service.conceder_xp") as conceder_xp_mock:
        missoes_service.atualizar_missoes("usuario-1", EventoGamificacao.QUESTAO_RESPONDIDA)

    conceder_xp_mock.assert_not_called()  # 1 de 10, não concluiu ainda

    # segunda leva: já tem progresso 9/10, essa chamada completa (9+1=10)
    fake.table("progresso_missoes_usuario").execute.return_value = query_result(
        data=[{"id": "prog-1", "valor_atual": 9, "concluido_em": None}]
    )

    with patch("services.gamificacao.missoes_service.supabase_admin", fake), \
         patch("services.gamificacao.missoes_service.conceder_xp") as conceder_xp_mock:
        missoes_service.atualizar_missoes("usuario-1", EventoGamificacao.QUESTAO_RESPONDIDA)

    conceder_xp_mock.assert_called_once()
    assert conceder_xp_mock.call_args[0][:2] == ("usuario-1", 50)


def test_atualizar_missoes_nao_concede_xp_de_novo_se_ja_concluida():
    fake = FakeSupabase()
    fake.table("missoes").execute.return_value = query_result(data=[
        {"id": "missao-1", "tipo_missao": "diaria", "valor_alvo": 10, "xp_recompensa": 50},
    ])
    fake.table("progresso_missoes_usuario").execute.return_value = query_result(
        data=[{"id": "prog-1", "valor_atual": 10, "concluido_em": "2026-08-10T12:00:00+00:00"}]
    )

    with patch("services.gamificacao.missoes_service.supabase_admin", fake), \
         patch("services.gamificacao.missoes_service.conceder_xp") as conceder_xp_mock:
        missoes_service.atualizar_missoes("usuario-1", EventoGamificacao.QUESTAO_RESPONDIDA)

    conceder_xp_mock.assert_not_called()


def test_atualizar_missoes_evento_sem_metrica_nao_faz_nada():
    fake = FakeSupabase()

    with patch("services.gamificacao.missoes_service.supabase_admin", fake):
        missoes_service.atualizar_missoes("usuario-1", EventoGamificacao.QUESTAO_ACERTADA)

    fake.table("missoes").select.assert_not_called()


def test_incremento_de_sessao_estudo_usa_minutos_reais():
    fake = FakeSupabase()
    fake.table("missoes").execute.return_value = query_result(data=[
        {"id": "missao-2", "tipo_missao": "diaria", "valor_alvo": 90, "xp_recompensa": 80},
    ])
    fake.table("progresso_missoes_usuario").execute.return_value = query_result(data=[])

    with patch("services.gamificacao.missoes_service.supabase_admin", fake), \
         patch("services.gamificacao.missoes_service.conceder_xp"):
        missoes_service.atualizar_missoes(
            "usuario-1", EventoGamificacao.SESSAO_ESTUDO_CONCLUIDA, {"minutos": 45}
        )

    chamada_insert = fake.table("progresso_missoes_usuario").insert.call_args[0][0]
    assert chamada_insert["valor_atual"] == 45
