from unittest.mock import patch
from uuid import uuid4

from routers import banco_questoes
from tests.services._supabase_mock import FakeSupabase, query_result

USUARIO_ID = str(uuid4())
OUTRO_USUARIO_ID = str(uuid4())
MATERIA_ID = str(uuid4())
LISTA_ID = str(uuid4())
EXECUCAO_ID = str(uuid4())
QUESTAO_1 = str(uuid4())
QUESTAO_2 = str(uuid4())
ALT_A = str(uuid4())
ALT_B = str(uuid4())


class _UsuarioFake:
    id = USUARIO_ID


def _preparar_fake_basico(fake: FakeSupabase, status_execucao="em_andamento"):
    fake.table("progresso_lista_questoes_aluno").execute.side_effect = [
        query_result(data=[{
            "id": EXECUCAO_ID, "usuario_id": USUARIO_ID, "lista_questoes_id": LISTA_ID,
            "status": status_execucao, "iniciado_em": "2026-01-02T09:00:00+00:00",
        }]),  # busca da execução (ownership check)
        query_result(data=[  # _janela_da_execucao: só essa execução existe
            {"id": EXECUCAO_ID, "iniciado_em": "2026-01-02T09:00:00+00:00"},
        ]),
    ]
    fake.table("listas_questoes").execute.return_value = query_result(
        data=[{"id": LISTA_ID, "titulo": "Lista de teste"}]
    )
    fake.table("itens_lista_questoes").execute.return_value = query_result(
        data=[
            {"questao_id": QUESTAO_1},
            {"questao_id": QUESTAO_2},
        ]
    )
    fake.table("respostas_lista_questoes_aluno").execute.return_value = query_result(data=[
        {
            "questao_id": QUESTAO_1, "alternativa_selecionada_id": ALT_B,
            "correta": False, "respondido_em": "2026-01-02T10:00:00+00:00",
        },
        {
            "questao_id": QUESTAO_2, "alternativa_selecionada_id": ALT_A,
            "correta": True, "respondido_em": "2026-01-02T10:05:00+00:00",
        },
    ])
    fake.table("materias").execute.return_value = query_result(
        data=[{"id": MATERIA_ID, "slug": "matematica", "nome": "Matemática", "cor": "purple"}]
    )
    fake.table("topicos").execute.return_value = query_result(data=[])
    fake.table("questoes").execute.return_value = query_result(data=[
        {
            "id": QUESTAO_1, "materia_id": MATERIA_ID, "topico_id": None,
            "dificuldade": "medio", "enunciado": "Questão 1", "alternativa_correta": ALT_A,
        },
        {
            "id": QUESTAO_2, "materia_id": MATERIA_ID, "topico_id": None,
            "dificuldade": "facil", "enunciado": "Questão 2", "alternativa_correta": ALT_A,
        },
    ])
    fake.table("alternativas_questao").execute.return_value = query_result(data=[
        {"id": ALT_A, "questao_id": QUESTAO_1, "letra": "A", "conteudo": "opção A", "ordem": 0},
        {"id": ALT_B, "questao_id": QUESTAO_1, "letra": "B", "conteudo": "opção B", "ordem": 1},
        {"id": ALT_A, "questao_id": QUESTAO_2, "letra": "A", "conteudo": "opção A", "ordem": 0},
    ])


def test_revisar_execucao_traz_resumo_e_questoes():
    fake = FakeSupabase()
    _preparar_fake_basico(fake, status_execucao="finalizada")

    with patch("routers.banco_questoes.supabase_admin", fake):
        resultado = banco_questoes.revisar_execucao(
            execucao_id=EXECUCAO_ID, status=None, materia=None, assunto=None,
            dificuldade=None, pagina=1, limite=20, usuario_atual=_UsuarioFake(),
        )

    assert resultado["execucao"]["status"] == "concluido"
    assert resultado["execucao"]["respondidas"] == 2
    assert resultado["execucao"]["acertadas"] == 1
    assert resultado["execucao"]["percentual_acerto"] == 50
    assert resultado["paginacao"]["total"] == 2

    questao_1 = next(q for q in resultado["questoes"] if q["id"] == QUESTAO_1)
    assert questao_1["resposta_aluno"] == "B"
    assert questao_1["resposta_correta"] == "A"
    assert questao_1["acertou"] is False
    assert {alt["letra"] for alt in questao_1["alternativas"]} == {"A", "B"}


def test_revisar_execucao_filtra_por_status():
    fake = FakeSupabase()
    _preparar_fake_basico(fake)

    with patch("routers.banco_questoes.supabase_admin", fake):
        resultado = banco_questoes.revisar_execucao(
            execucao_id=EXECUCAO_ID, status="errada", materia=None, assunto=None,
            dificuldade=None, pagina=1, limite=20, usuario_atual=_UsuarioFake(),
        )

    assert resultado["paginacao"]["total"] == 1
    assert resultado["questoes"][0]["id"] == QUESTAO_1
    # o resumo da execução continua contando tudo, não só o filtrado
    assert resultado["execucao"]["respondidas"] == 2


def test_revisar_execucao_de_outro_aluno_retorna_404():
    fake = FakeSupabase()
    fake.table("progresso_lista_questoes_aluno").execute.return_value = query_result(data=[{
        "id": EXECUCAO_ID, "usuario_id": OUTRO_USUARIO_ID, "lista_questoes_id": LISTA_ID,
        "status": "em_andamento", "iniciado_em": "2026-01-02T09:00:00+00:00",
    }])

    with patch("routers.banco_questoes.supabase_admin", fake):
        try:
            banco_questoes.revisar_execucao(
                execucao_id=EXECUCAO_ID, status=None, materia=None, assunto=None,
                dificuldade=None, pagina=1, limite=20, usuario_atual=_UsuarioFake(),
            )
            assert False, "deveria levantar HTTPException"
        except Exception as erro:
            assert getattr(erro, "status_code", None) == 404


def test_revisar_execucao_inexistente_retorna_404():
    fake = FakeSupabase()
    fake.table("progresso_lista_questoes_aluno").execute.return_value = query_result(data=[])

    with patch("routers.banco_questoes.supabase_admin", fake):
        try:
            banco_questoes.revisar_execucao(
                execucao_id=EXECUCAO_ID, status=None, materia=None, assunto=None,
                dificuldade=None, pagina=1, limite=20, usuario_atual=_UsuarioFake(),
            )
            assert False, "deveria levantar HTTPException"
        except Exception as erro:
            assert getattr(erro, "status_code", None) == 404
