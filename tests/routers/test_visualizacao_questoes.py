from unittest.mock import patch
from uuid import uuid4

from routers import visualizacao_questoes as vq
from tests.services._supabase_mock import FakeSupabase, query_result

USUARIO_ID = str(uuid4())
LISTA_ID = str(uuid4())
QUESTAO_ID = str(uuid4())


class _UsuarioFake:
    id = USUARIO_ID


def test_calcular_progresso_ignora_respostas_anteriores_a_desde():
    fake = FakeSupabase()
    fake.table("respostas_lista_questoes_aluno").execute.return_value = query_result(data=[
        {"questao_id": QUESTAO_ID},
    ])

    with patch("routers.visualizacao_questoes.supabase_admin", fake):
        concluidas, percentual = vq.calcular_progresso(
            USUARIO_ID, LISTA_ID, [QUESTAO_ID], desde="2026-01-02T09:00:00+00:00"
        )

    # A query em si é mockada pra devolver 1 resposta independente do filtro
    # (o FakeSupabase não simula filtragem de verdade) — o que este teste
    # garante é que o `.gte()` é de fato chamado quando `desde` é passado,
    # que é a parte fácil de esquecer numa consulta encadeada.
    assert concluidas == 1
    assert percentual == 100
    fake.table("respostas_lista_questoes_aluno").gte.assert_called_once_with(
        "respondido_em", "2026-01-02T09:00:00+00:00"
    )


def test_calcular_progresso_sem_desde_nao_filtra_por_data():
    fake = FakeSupabase()
    fake.table("respostas_lista_questoes_aluno").execute.return_value = query_result(data=[])

    with patch("routers.visualizacao_questoes.supabase_admin", fake):
        vq.calcular_progresso(USUARIO_ID, LISTA_ID, [QUESTAO_ID], desde=None)

    fake.table("respostas_lista_questoes_aluno").gte.assert_not_called()


def test_obter_progresso_pega_execucao_mais_recente():
    fake = FakeSupabase()
    fake.table("progresso_lista_questoes_aluno").execute.return_value = query_result(data=[
        {"id": "execucao-2", "status": "em_andamento", "iniciado_em": "2026-01-02T09:00:00+00:00"},
    ])

    with patch("routers.visualizacao_questoes.supabase_admin", fake):
        progresso = vq.obter_progresso(USUARIO_ID, LISTA_ID)

    assert progresso["id"] == "execucao-2"
    fake.table("progresso_lista_questoes_aluno").order.assert_called_once_with("iniciado_em", desc=True)


def test_garantir_progresso_cria_primeira_execucao_quando_nao_existe():
    fake = FakeSupabase()
    fake.table("progresso_lista_questoes_aluno").execute.side_effect = [
        query_result(data=[]),  # obter_progresso: nunca começou
        query_result(data=[{"id": "execucao-1", "status": "em_andamento"}]),  # insert
    ]

    with patch("routers.visualizacao_questoes.supabase_admin", fake):
        progresso = vq.garantir_progresso(USUARIO_ID, LISTA_ID)

    assert progresso["id"] == "execucao-1"
    fake.table("progresso_lista_questoes_aluno").insert.assert_called_once()
