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


QUESTAO_ID_2 = str(uuid4())
EXECUCAO_ID = str(uuid4())


def _preparar_fake_finalizar(fake: FakeSupabase, respostas_dadas: list[dict]):
    fake.table("listas_questoes").execute.return_value = query_result(data=[
        {"id": LISTA_ID, "usuario_id": USUARIO_ID, "slug": "lista-x", "titulo": "Lista X",
         "materia_id": None, "tipo_prova_id": None, "dificuldade": None, "tipo_lista": "fixa"},
    ])
    fake.table("itens_lista_questoes").execute.return_value = query_result(data=[
        {"questao_id": QUESTAO_ID, "ordem": 0},
        {"questao_id": QUESTAO_ID_2, "ordem": 1},
    ])
    fake.table("progresso_lista_questoes_aluno").execute.side_effect = [
        query_result(data=[{"id": EXECUCAO_ID, "status": "em_andamento", "iniciado_em": "2026-01-01T00:00:00+00:00"}]),
        query_result(data=[{"id": EXECUCAO_ID}]),  # update
    ]
    fake.table("respostas_lista_questoes_aluno").execute.return_value = query_result(data=respostas_dadas)


def test_finalizar_lista_com_questao_em_branco_nao_bloqueia_mais():
    """Regressão: finalizar não pode mais exigir 100% respondido — o aluno
    fecha a lista com questão em branco e ela conta como não respondida
    no resultado, sem travar a chamada (antes levantava 422)."""
    fake = FakeSupabase()
    _preparar_fake_finalizar(fake, respostas_dadas=[{"questao_id": QUESTAO_ID}])  # só 1 de 2 respondida

    with patch("routers.visualizacao_questoes.supabase_admin", fake):
        resultado = vq.finalizar_lista(slug="lista-x", usuario_atual=_UsuarioFake())

    assert resultado["status"] == "finalizada"
    assert resultado["questoes_concluidas"] == 1
    assert resultado["questoes_totais"] == 2
    fake.table("progresso_lista_questoes_aluno").update.assert_called_once()
    payload = fake.table("progresso_lista_questoes_aluno").update.call_args[0][0]
    assert payload["status"] == "finalizada"
