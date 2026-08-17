from unittest.mock import patch
from uuid import uuid4

from routers import banco_questoes
from tests.services._supabase_mock import FakeSupabase, query_result

USUARIO_ID = str(uuid4())
MATERIA_ID = str(uuid4())
TIPO_PROVA_ID = str(uuid4())
LISTA_ID = str(uuid4())
QUESTAO_1 = str(uuid4())
QUESTAO_2 = str(uuid4())


class _UsuarioFake:
    id = USUARIO_ID


def _preparar_fake(fake: FakeSupabase, respostas, progresso):
    fake.table("tipos_prova").execute.return_value = query_result(
        data=[{"id": TIPO_PROVA_ID, "slug": "enem", "nome": "ENEM"}]
    )
    fake.table("materias").execute.return_value = query_result(
        data=[{"id": MATERIA_ID, "slug": "matematica", "nome": "Matemática", "cor": "purple", "icone": "book"}]
    )
    fake.table("listas_questoes").execute.return_value = query_result(
        data=[{
            "id": LISTA_ID,
            "slug": "lista-teste",
            "titulo": "Lista de teste",
            "descricao": "Descrição de teste",
            "materia_id": MATERIA_ID,
            "tipo_prova_id": TIPO_PROVA_ID,
            "dificuldade": "medio",
        }]
    )
    fake.table("itens_lista_questoes").execute.return_value = query_result(
        data=[
            {"lista_questoes_id": LISTA_ID, "questao_id": QUESTAO_1},
            {"lista_questoes_id": LISTA_ID, "questao_id": QUESTAO_2},
        ]
    )
    fake.table("progresso_lista_questoes_aluno").execute.return_value = query_result(data=progresso)
    fake.table("respostas_lista_questoes_aluno").execute.return_value = query_result(data=respostas)


def test_lista_nao_iniciada_quando_aluno_nunca_respondeu():
    fake = FakeSupabase()
    _preparar_fake(fake, respostas=[], progresso=[])

    with patch("routers.banco_questoes.supabase_admin", fake):
        listas = banco_questoes.montar_listas(USUARIO_ID, None, None, None, False, False)

    assert listas[0]["status"] == "nao_iniciado"
    assert listas[0]["questoes_concluidas"] == 0
    assert listas[0]["questoes_corretas"] == 0
    assert listas[0]["descricao"] == "Descrição de teste"


def test_lista_em_andamento_conta_so_respostas_da_execucao_atual():
    fake = FakeSupabase()
    _preparar_fake(
        fake,
        respostas=[
            {
                "lista_questoes_id": LISTA_ID, "questao_id": QUESTAO_1,
                "correta": True, "respondido_em": "2026-01-02T10:00:00+00:00",
            },
        ],
        progresso=[{
            "id": str(uuid4()), "lista_questoes_id": LISTA_ID, "status": "em_andamento",
            "iniciado_em": "2026-01-02T09:00:00+00:00",
        }],
    )

    with patch("routers.banco_questoes.supabase_admin", fake):
        listas = banco_questoes.montar_listas(USUARIO_ID, None, None, None, False, False)

    assert listas[0]["status"] == "em_andamento"
    assert listas[0]["questoes_concluidas"] == 1
    assert listas[0]["questoes_corretas"] == 1
    assert listas[0]["questoes_totais"] == 2
    assert listas[0]["ultima_execucao_id"] is not None


def test_refazer_ignora_respostas_de_execucoes_anteriores():
    """Resposta dada ANTES do início da execução atual (ex.: de uma
    tentativa anterior, antes de um refazer) não deve contar no progresso
    exibido — é exatamente o que o /refazer promete "zerar"."""
    fake = FakeSupabase()
    _preparar_fake(
        fake,
        respostas=[
            {
                "lista_questoes_id": LISTA_ID, "questao_id": QUESTAO_1,
                "correta": False, "respondido_em": "2026-01-01T10:00:00+00:00",
            },
        ],
        progresso=[{
            "id": str(uuid4()), "lista_questoes_id": LISTA_ID, "status": "em_andamento",
            "iniciado_em": "2026-01-02T09:00:00+00:00",
        }],
    )

    with patch("routers.banco_questoes.supabase_admin", fake):
        listas = banco_questoes.montar_listas(USUARIO_ID, None, None, None, False, False)

    assert listas[0]["status"] == "nao_iniciado"
    assert listas[0]["questoes_concluidas"] == 0


def test_lista_concluida_quando_execucao_finalizada():
    fake = FakeSupabase()
    _preparar_fake(
        fake,
        respostas=[
            {
                "lista_questoes_id": LISTA_ID, "questao_id": QUESTAO_1,
                "correta": True, "respondido_em": "2026-01-02T10:00:00+00:00",
            },
            {
                "lista_questoes_id": LISTA_ID, "questao_id": QUESTAO_2,
                "correta": False, "respondido_em": "2026-01-02T10:05:00+00:00",
            },
        ],
        progresso=[{
            "id": str(uuid4()), "lista_questoes_id": LISTA_ID, "status": "finalizada",
            "iniciado_em": "2026-01-02T09:00:00+00:00",
        }],
    )

    with patch("routers.banco_questoes.supabase_admin", fake):
        listas = banco_questoes.montar_listas(USUARIO_ID, None, None, None, False, False)

    assert listas[0]["status"] == "concluido"
    assert listas[0]["questoes_concluidas"] == 2
    assert listas[0]["questoes_corretas"] == 1


def test_refazer_lista_cria_nova_execucao():
    fake = FakeSupabase()
    fake.table("listas_questoes").execute.return_value = query_result(
        data=[{"id": LISTA_ID, "slug": "lista-teste", "usuario_id": None}]
    )
    fake.table("progresso_lista_questoes_aluno").execute.return_value = query_result(
        data=[{"id": str(uuid4())}]
    )

    with patch("routers.banco_questoes.supabase_admin", fake):
        resultado = banco_questoes.refazer_lista(lista_id=LISTA_ID, usuario_atual=_UsuarioFake())

    assert resultado["lista_id"] == LISTA_ID
    assert resultado["status"] == "em_andamento"
    fake.table("progresso_lista_questoes_aluno").insert.assert_called_once()
    payload = fake.table("progresso_lista_questoes_aluno").insert.call_args[0][0]
    assert payload["status"] == "em_andamento"
    assert payload["lista_questoes_id"] == LISTA_ID


def test_refazer_lista_inexistente_retorna_404():
    fake = FakeSupabase()
    fake.table("listas_questoes").execute.return_value = query_result(data=[])

    with patch("routers.banco_questoes.supabase_admin", fake):
        try:
            banco_questoes.refazer_lista(lista_id=LISTA_ID, usuario_atual=_UsuarioFake())
            assert False, "deveria levantar HTTPException"
        except Exception as erro:
            assert getattr(erro, "status_code", None) == 404


def test_questoes_respondidas_filtra_por_status_e_pagina():
    fake = FakeSupabase()
    fake.table("tipos_prova").execute.return_value = query_result(
        data=[{"id": TIPO_PROVA_ID, "slug": "enem", "nome": "ENEM"}]
    )
    fake.table("materias").execute.return_value = query_result(
        data=[{"id": MATERIA_ID, "slug": "matematica", "nome": "Matemática", "cor": "purple"}]
    )
    fake.table("topicos").execute.return_value = query_result(data=[])
    fake.table("questoes").execute.return_value = query_result(data=[
        {
            "id": QUESTAO_1, "materia_id": MATERIA_ID, "tipo_prova_id": TIPO_PROVA_ID,
            "topico_id": None, "dificuldade": "dificil", "enunciado": "Questão 1",
            "alternativa_correta": "alt-correta-1",
        },
        {
            "id": QUESTAO_2, "materia_id": MATERIA_ID, "tipo_prova_id": TIPO_PROVA_ID,
            "topico_id": None, "dificuldade": "facil", "enunciado": "Questão 2",
            "alternativa_correta": "alt-correta-2",
        },
    ])
    fake.table("respostas_lista_questoes_aluno").execute.return_value = query_result(data=[
        {
            "lista_questoes_id": LISTA_ID, "questao_id": QUESTAO_1,
            "alternativa_selecionada_id": "alt-errada-1", "correta": False,
            "respondido_em": "2026-01-02T10:00:00+00:00",
        },
        {
            "lista_questoes_id": LISTA_ID, "questao_id": QUESTAO_2,
            "alternativa_selecionada_id": "alt-correta-2", "correta": True,
            "respondido_em": "2026-01-02T11:00:00+00:00",
        },
    ])
    fake.table("listas_questoes").execute.return_value = query_result(
        data=[{"id": LISTA_ID, "slug": "lista-teste", "titulo": "Lista de teste"}]
    )
    fake.table("alternativas_questao").execute.return_value = query_result(data=[
        {"id": "alt-errada-1", "letra": "B"},
        {"id": "alt-correta-1", "letra": "A"},
    ])

    with patch("routers.banco_questoes.supabase_admin", fake):
        resultado = banco_questoes.listar_questoes_respondidas(
            status="erradas",
            vestibulares=None,
            dificuldades=None,
            materias=None,
            assuntos=None,
            apenas_favoritas=False,
            pagina=1,
            limite=20,
            usuario_atual=_UsuarioFake(),
        )

    assert resultado["paginacao"]["total"] == 1
    assert len(resultado["questoes"]) == 1
    questao = resultado["questoes"][0]
    assert questao["id"] == QUESTAO_1
    assert questao["correta"] is False
    assert questao["resposta_aluno"] == "B"
    assert questao["resposta_correta"] == "A"
    assert questao["lista_titulo"] == "Lista de teste"
