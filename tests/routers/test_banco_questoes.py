from unittest.mock import patch
from uuid import uuid4

from fastapi import BackgroundTasks

from routers import banco_questoes
from schemas.banco_questoes_schema import GerarListaIARequest
from services.ai.base import AIIndisponivelError
from tests.services._supabase_mock import FakeSupabase, query_result

USUARIO_ID = str(uuid4())
MATERIA_ID = str(uuid4())
QUESTAO_ID = str(uuid4())
LISTA_ID = str(uuid4())
JOB_ID = str(uuid4())


class _UsuarioFake:
    id = USUARIO_ID


# --- POST /listas/gerar-ia: só agenda o job, não gera nada de fato -----------

def test_gerar_lista_ia_agenda_job_e_retorna_202():
    fake = FakeSupabase()
    # geracoes_ia_listas.execute() é chamado 2x: select (checagem de cota,
    # só olha .count) e insert (cria o job, só olha .data).
    fake.table("geracoes_ia_listas").execute.return_value = query_result(
        data=[{"id": JOB_ID}], count=0
    )

    background_tasks = BackgroundTasks()
    dados = GerarListaIARequest(quantidade=5)

    with patch("routers.banco_questoes.supabase_admin", fake):
        resultado = banco_questoes.gerar_lista_ia(
            dados=dados, background_tasks=background_tasks, usuario_atual=_UsuarioFake()
        )

    assert resultado == {"job_id": JOB_ID, "status": "processando"}
    assert len(background_tasks.tasks) == 1
    fake.table("geracoes_ia_listas").insert.assert_called_once()
    payload = fake.table("geracoes_ia_listas").insert.call_args[0][0]
    assert payload["status"] == "gerando"
    assert payload["usuario_id"] == USUARIO_ID


def test_gerar_lista_ia_dificuldade_invalida_retorna_400():
    fake = FakeSupabase()
    dados = GerarListaIARequest(quantidade=5, dificuldades=["muito_dificil"])

    with patch("routers.banco_questoes.supabase_admin", fake):
        try:
            banco_questoes.gerar_lista_ia(
                dados=dados, background_tasks=BackgroundTasks(), usuario_atual=_UsuarioFake()
            )
            assert False, "deveria levantar HTTPException"
        except Exception as erro:
            assert getattr(erro, "status_code", None) == 400


def test_gerar_lista_ia_quota_excedida_retorna_429():
    fake = FakeSupabase()
    fake.table("geracoes_ia_listas").execute.return_value = query_result(
        data=[], count=banco_questoes.LIMITE_GERACOES_IA_POR_DIA
    )
    dados = GerarListaIARequest(quantidade=5)

    with patch("routers.banco_questoes.supabase_admin", fake):
        try:
            banco_questoes.gerar_lista_ia(
                dados=dados, background_tasks=BackgroundTasks(), usuario_atual=_UsuarioFake()
            )
            assert False, "deveria levantar HTTPException"
        except Exception as erro:
            assert getattr(erro, "status_code", None) == 429


# --- _gerar_lista_ia_em_background: roda fora do request, erros viram -------
# --- status="erro" na linha de geracoes_ia_listas em vez de HTTPException ---

def test_background_sem_materia_e_sem_historico_marca_erro():
    fake = FakeSupabase()
    fake.table("tentativas_questoes").execute.return_value = query_result(data=[], count=0)

    with patch("routers.banco_questoes.supabase_admin", fake):
        banco_questoes._gerar_lista_ia_em_background(
            JOB_ID, USUARIO_ID, 5, [], [], [], [], [], None, None
        )

    fake.table("geracoes_ia_listas").update.assert_called_once()
    payload = fake.table("geracoes_ia_listas").update.call_args[0][0]
    assert payload["status"] == "erro"


def test_background_provider_indisponivel_marca_erro():
    fake = FakeSupabase()
    materias_linhas = [{"id": MATERIA_ID, "nome": "Matemática", "slug": "matematica"}]

    def gerar_questoes_indisponivel(**kwargs):
        raise AIIndisponivelError("timeout")

    provider_mock = type("P", (), {"gerar_questoes": staticmethod(gerar_questoes_indisponivel)})()

    with patch("routers.banco_questoes.supabase_admin", fake), \
         patch("routers.banco_questoes.get_ai_provider", return_value=provider_mock):
        banco_questoes._gerar_lista_ia_em_background(
            JOB_ID, USUARIO_ID, 5, ["matematica"], materias_linhas, [], [], [], None, None
        )

    payload = fake.table("geracoes_ia_listas").update.call_args[0][0]
    assert payload["status"] == "erro"
    assert "IA" in payload["mensagem_erro"]


def test_background_persiste_lista_e_questoes():
    fake = FakeSupabase()
    materias_linhas = [{"id": MATERIA_ID, "nome": "Matemática", "slug": "matematica"}]

    # listas_questoes.execute() é chamado 3x: select (checagem de slug único),
    # insert (cria a lista) e select (recarrega id/slug pro job).
    fake.table("listas_questoes").execute.side_effect = [
        query_result(data=[]),
        query_result(data=[{"id": LISTA_ID, "slug": "lista-personalizada-matematica"}]),
        query_result(data=[{"id": LISTA_ID, "slug": "lista-personalizada-matematica"}]),
    ]
    # questoes.execute(): insert (nova questão) + update (alternativa_correta).
    # materia_com_mais_erros não é chamado aqui pois materias_linhas já veio preenchida.
    fake.table("questoes").execute.side_effect = [
        query_result(data=[{"id": QUESTAO_ID}]),
        query_result(data=None),
    ]
    fake.table("alternativas_questao").execute.return_value = query_result(
        data=[{"id": str(uuid4())}]
    )

    questoes_geradas = [
        {
            "enunciado": "Quanto é 2 + 2?",
            "alternativas": ["3", "4", "5"],
            "resposta_correta": "B",
            "explicacao": "2 + 2 = 4",
            "dificuldade": "facil",
        }
    ]
    provider_mock = type("P", (), {"gerar_questoes": staticmethod(lambda **kwargs: questoes_geradas)})()

    with patch("routers.banco_questoes.supabase_admin", fake), \
         patch("routers.banco_questoes.get_ai_provider", return_value=provider_mock):
        banco_questoes._gerar_lista_ia_em_background(
            JOB_ID, USUARIO_ID, 5, ["matematica"], materias_linhas, [], [], [], None, None
        )

    fake.table("listas_questoes").insert.assert_called_once()
    payload_lista = fake.table("listas_questoes").insert.call_args[0][0]
    assert payload_lista["tipo_lista"] == "gerada_ia"
    assert payload_lista["materia_id"] == MATERIA_ID

    fake.table("questoes").insert.assert_called_once()
    fake.table("itens_lista_questoes").insert.assert_called_once()

    fake.table("geracoes_ia_listas").update.assert_called_once()
    payload_job = fake.table("geracoes_ia_listas").update.call_args[0][0]
    assert payload_job == {"status": "concluido", "lista_questoes_id": LISTA_ID}
