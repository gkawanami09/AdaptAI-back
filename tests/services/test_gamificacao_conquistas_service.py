from unittest.mock import MagicMock, patch

from postgrest.exceptions import APIError

from services.gamificacao import conquistas_service
from services.gamificacao.eventos import EventoGamificacao
from tests.services._supabase_mock import FakeSupabase, query_result


def test_desbloquear_conquista_concede_xp_uma_vez():
    fake = FakeSupabase()
    fake.table("conquistas_usuario").insert.return_value.execute.return_value = query_result(data=[{"id": "x"}])

    conquista = {"id": "conquista-1", "titulo": "100 Questões", "descricao": "Resolva 100 questões", "xp_recompensa": 200}

    with patch("services.gamificacao.conquistas_service.supabase_admin", fake), \
         patch("services.gamificacao.conquistas_service.conceder_xp") as conceder_xp_mock:
        resultado = conquistas_service.desbloquear_conquista("usuario-1", conquista)

    assert resultado is True
    conceder_xp_mock.assert_called_once_with("usuario-1", 200)


def test_desbloquear_conquista_cria_notificacao():
    fake = FakeSupabase()
    fake.table("conquistas_usuario").insert.return_value.execute.return_value = query_result(data=[{"id": "x"}])

    conquista = {"id": "conquista-1", "titulo": "100 Questões", "descricao": "Resolva 100 questões", "xp_recompensa": 200}

    with patch("services.gamificacao.conquistas_service.supabase_admin", fake), \
         patch("services.gamificacao.conquistas_service.conceder_xp"):
        conquistas_service.desbloquear_conquista("usuario-1", conquista)

    notificacao_insert = fake.table("notificacoes").insert.call_args[0][0]
    assert notificacao_insert["usuario_id"] == "usuario-1"
    assert notificacao_insert["tipo"] == "conquista"
    assert "100 Questões" in notificacao_insert["titulo"]


def test_falha_ao_notificar_nao_impede_desbloqueio():
    fake = FakeSupabase()
    fake.table("conquistas_usuario").insert.return_value.execute.return_value = query_result(data=[{"id": "x"}])
    fake.table("notificacoes").insert.return_value.execute.side_effect = Exception("boom")

    conquista = {"id": "conquista-1", "titulo": "100 Questões", "descricao": None, "xp_recompensa": 200}

    with patch("services.gamificacao.conquistas_service.supabase_admin", fake), \
         patch("services.gamificacao.conquistas_service.conceder_xp") as conceder_xp_mock:
        resultado = conquistas_service.desbloquear_conquista("usuario-1", conquista)

    assert resultado is True
    conceder_xp_mock.assert_called_once_with("usuario-1", 200)


def test_desbloquear_conquista_ja_existente_nao_concede_xp_de_novo():
    fake = FakeSupabase()
    erro_unique = APIError({"code": "23505", "message": "duplicate key"})
    fake.table("conquistas_usuario").insert.return_value.execute.side_effect = erro_unique

    conquista = {"id": "conquista-1", "xp_recompensa": 200}

    with patch("services.gamificacao.conquistas_service.supabase_admin", fake), \
         patch("services.gamificacao.conquistas_service.conceder_xp") as conceder_xp_mock:
        resultado = conquistas_service.desbloquear_conquista("usuario-1", conquista)

    assert resultado is False
    conceder_xp_mock.assert_not_called()


def test_desbloquear_conquista_repropaga_erro_que_nao_e_conflito():
    fake = FakeSupabase()
    outro_erro = APIError({"code": "23503", "message": "fk violation"})
    fake.table("conquistas_usuario").insert.return_value.execute.side_effect = outro_erro

    conquista = {"id": "conquista-1", "xp_recompensa": 100}

    with patch("services.gamificacao.conquistas_service.supabase_admin", fake):
        try:
            conquistas_service.desbloquear_conquista("usuario-1", conquista)
            assert False, "deveria ter propagado o erro"
        except APIError as erro:
            assert erro.code == "23503"


def test_avaliar_conquistas_desbloqueia_quando_metrica_atinge_valor():
    fake = FakeSupabase()
    fake.table("conquistas").execute.return_value = query_result(data=[
        {"id": "c1", "xp_recompensa": 150, "tipo_condicao": "questoes_respondidas", "valor_condicao": 100, "materia_id": None},
    ])
    fake.table("conquistas_usuario").execute.return_value = query_result(data=[])

    medidor_falso = MagicMock(return_value=101)

    with patch("services.gamificacao.conquistas_service.supabase_admin", fake), \
         patch.dict(conquistas_service.MEDIDORES, {"questoes_respondidas": medidor_falso}), \
         patch("services.gamificacao.conquistas_service.desbloquear_conquista", return_value=True) as desbloquear_mock:
        desbloqueadas = conquistas_service.avaliar_conquistas(
            "usuario-1", EventoGamificacao.QUESTAO_RESPONDIDA
        )

    assert desbloqueadas == ["c1"]
    desbloquear_mock.assert_called_once()


def test_avaliar_conquistas_nao_desbloqueia_se_ja_desbloqueada():
    fake = FakeSupabase()
    fake.table("conquistas").execute.return_value = query_result(data=[
        {"id": "c1", "xp_recompensa": 150, "tipo_condicao": "questoes_respondidas", "valor_condicao": 100, "materia_id": None},
    ])
    fake.table("conquistas_usuario").execute.return_value = query_result(data=[{"conquista_id": "c1"}])

    with patch("services.gamificacao.conquistas_service.supabase_admin", fake), \
         patch("services.gamificacao.conquistas_service.desbloquear_conquista") as desbloquear_mock:
        desbloqueadas = conquistas_service.avaliar_conquistas(
            "usuario-1", EventoGamificacao.QUESTAO_RESPONDIDA
        )

    assert desbloqueadas == []
    desbloquear_mock.assert_not_called()


def test_avaliar_conquistas_ignora_evento_sem_condicoes_mapeadas():
    fake = FakeSupabase()

    with patch("services.gamificacao.conquistas_service.supabase_admin", fake):
        desbloqueadas = conquistas_service.avaliar_conquistas("usuario-1", EventoGamificacao.QUESTAO_ERRADA)

    assert desbloqueadas == []
    fake.table("conquistas").select.assert_not_called()
