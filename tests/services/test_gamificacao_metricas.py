from unittest.mock import patch

from services.gamificacao import metricas
from tests.services._supabase_mock import FakeSupabase, query_result


def test_questoes_respondidas_conta_linhas_de_resposta():
    fake = FakeSupabase()
    fake.table("respostas_lista_questoes_aluno").execute.return_value = query_result(count=137)

    with patch("services.gamificacao.metricas.supabase_admin", fake):
        assert metricas.questoes_respondidas("usuario-1", {}) == 137


def test_minutos_estudo_dia_pega_o_maior_dia_unico():
    fake = FakeSupabase()
    fake.table("atividade_diaria").execute.return_value = query_result(
        data=[{"minutos_estudo": 60}, {"minutos_estudo": 320}, {"minutos_estudo": 90}]
    )

    with patch("services.gamificacao.metricas.supabase_admin", fake):
        assert metricas.minutos_estudo_dia("usuario-1", {}) == 320


def test_percentual_acerto_materia_abaixo_do_minimo_retorna_zero():
    fake = FakeSupabase()
    fake.table("questoes").execute.return_value = query_result(data=[{"id": "q1"}, {"id": "q2"}])
    fake.table("respostas_lista_questoes_aluno").execute.return_value = query_result(
        data=[{"correta": True}, {"correta": True}]  # 2 respostas, abaixo do MIN (20)
    )

    with patch("services.gamificacao.metricas.supabase_admin", fake):
        conquista = {"materia_id": "materia-1"}
        assert metricas.percentual_acerto_materia("usuario-1", conquista) == 0


def test_percentual_acerto_materia_calcula_correto_acima_do_minimo():
    fake = FakeSupabase()
    fake.table("questoes").execute.return_value = query_result(
        data=[{"id": f"q{i}"} for i in range(25)]
    )
    respostas = [{"correta": True}] * 20 + [{"correta": False}] * 5  # 25 respostas, 80% acerto
    fake.table("respostas_lista_questoes_aluno").execute.return_value = query_result(data=respostas)

    with patch("services.gamificacao.metricas.supabase_admin", fake):
        conquista = {"materia_id": "materia-1"}
        assert metricas.percentual_acerto_materia("usuario-1", conquista) == 80


def test_questoes_erradas_revisadas_usa_apenas_listas_de_revisao():
    fake = FakeSupabase()
    fake.table("listas_questoes").execute.return_value = query_result(data=[{"id": "lista-revisao-1"}])
    fake.table("respostas_lista_questoes_aluno").execute.return_value = query_result(count=42)

    with patch("services.gamificacao.metricas.supabase_admin", fake):
        assert metricas.questoes_erradas_revisadas("usuario-1", {}) == 42


def test_maior_ofensiva_usada_para_dias_estudo_e_ofensiva_dias():
    fake = FakeSupabase()
    fake.table("estatisticas_usuario").execute.return_value = query_result(
        data=[{"maior_ofensiva_dias": 9}]
    )

    with patch("services.gamificacao.metricas.supabase_admin", fake):
        assert metricas.dias_estudo("usuario-1", {}) == 9
        assert metricas.ofensiva_dias("usuario-1", {}) == 9
