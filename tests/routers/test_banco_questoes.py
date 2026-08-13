from unittest.mock import patch
from uuid import uuid4

from routers import banco_questoes
from services.ai.base import AIIndisponivelError
from tests.services._supabase_mock import FakeSupabase, query_result

USUARIO_ID = str(uuid4())
MATERIA_ID = str(uuid4())
QUESTAO_ID = str(uuid4())
LISTA_ID = str(uuid4())


class _UsuarioFake:
    id = USUARIO_ID


def _preparar_fake_basico(fake: FakeSupabase):
    fake.table("tentativas_questoes").execute.return_value = query_result(
        data=[{"questao_id": QUESTAO_ID}], count=1
    )
    fake.table("questoes").execute.return_value = query_result(
        data=[{"id": QUESTAO_ID, "materia_id": MATERIA_ID}]
    )
    fake.table("materias").execute.return_value = query_result(
        data=[{"id": MATERIA_ID, "nome": "Matemática"}]
    )


def test_gerar_lista_ia_sem_tentativas_retorna_422():
    fake = FakeSupabase()
    fake.table("tentativas_questoes").execute.return_value = query_result(data=[], count=0)

    with patch("routers.banco_questoes.supabase_admin", fake):
        try:
            banco_questoes.gerar_lista_ia(usuario_atual=_UsuarioFake())
            assert False, "deveria levantar HTTPException"
        except Exception as erro:
            assert getattr(erro, "status_code", None) == 422


def test_gerar_lista_ia_provider_indisponivel_retorna_502():
    fake = FakeSupabase()
    _preparar_fake_basico(fake)

    def gerar_questoes_indisponivel(**kwargs):
        raise AIIndisponivelError("timeout")

    provider_mock = type("P", (), {"gerar_questoes": staticmethod(gerar_questoes_indisponivel)})()

    with patch("routers.banco_questoes.supabase_admin", fake), \
         patch("routers.banco_questoes.get_ai_provider", return_value=provider_mock):
        try:
            banco_questoes.gerar_lista_ia(usuario_atual=_UsuarioFake())
            assert False, "deveria levantar HTTPException"
        except Exception as erro:
            assert getattr(erro, "status_code", None) == 502


def test_gerar_lista_ia_persiste_lista_e_questoes():
    fake = FakeSupabase()
    _preparar_fake_basico(fake)

    # listas_questoes.execute() é chamado 3x: select (checagem de slug único,
    # em gerar_slug_unico_lista), insert (cria a lista) e select (recarrega a
    # lista criada) — side_effect diferencia por ordem.
    fake.table("listas_questoes").execute.side_effect = [
        query_result(data=[]),
        query_result(data=[{"id": LISTA_ID, "slug": "lista-personalizada-matematica"}]),
        query_result(data=[{"id": LISTA_ID, "slug": "lista-personalizada-matematica"}]),
    ]
    # questoes.execute() é chamado 3x: select (materia_com_mais_erros),
    # insert (nova questão) e update (alternativa_correta, não checa .data).
    fake.table("questoes").execute.side_effect = [
        query_result(data=[{"id": QUESTAO_ID, "materia_id": MATERIA_ID}]),
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
        resultado = banco_questoes.gerar_lista_ia(usuario_atual=_UsuarioFake())

    assert resultado["id"] == LISTA_ID
    fake.table("listas_questoes").insert.assert_called_once()
    payload_lista = fake.table("listas_questoes").insert.call_args[0][0]
    assert payload_lista["tipo_lista"] == "gerada_ia"
    assert payload_lista["materia_id"] == MATERIA_ID
    fake.table("questoes").insert.assert_called_once()
    fake.table("itens_lista_questoes").insert.assert_called_once()
