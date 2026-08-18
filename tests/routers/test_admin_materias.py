from unittest.mock import patch
from uuid import uuid4

from routers.admin import materias
from tests.services._supabase_mock import FakeSupabase, query_result

MATERIA_ID = str(uuid4())


def test_buscar_materias_usa_chave_sem_acento():
    fake = FakeSupabase()
    fake.table("materias").execute.return_value = query_result(data=[{
        "id": MATERIA_ID, "nome": "Matemática", "slug": "matematica",
        "descricao": "Álgebra, geometria e estatística.",
    }])

    with patch("routers.admin.materias.supabase_admin", fake):
        resultado = materias.buscar_materias(MATERIA_ID)

    assert "materia" in resultado
    assert "matéria" not in resultado
    assert resultado["materia"]["slug"] == "matematica"
    assert resultado["materia"]["descricao"] == "Álgebra, geometria e estatística."


def test_excluir_materia_sem_dependencias_deleta():
    fake = FakeSupabase()
    fake.table("materias").execute.return_value = query_result(data=[{"id": MATERIA_ID}])
    for tabela in ("aulas", "topicos", "questoes", "listas_questoes"):
        fake.table(tabela).execute.return_value = query_result(data=[], count=0)

    with patch("routers.admin.materias.supabase_admin", fake):
        resultado = materias.excluir_materia(MATERIA_ID)

    assert resultado["sucesso"] is True
    fake.table("materias").delete.assert_called_once()


def test_excluir_materia_com_aulas_vinculadas_retorna_409():
    fake = FakeSupabase()
    fake.table("materias").execute.return_value = query_result(data=[{"id": MATERIA_ID}])
    fake.table("aulas").execute.return_value = query_result(data=[], count=3)
    for tabela in ("topicos", "questoes", "listas_questoes"):
        fake.table(tabela).execute.return_value = query_result(data=[], count=0)

    with patch("routers.admin.materias.supabase_admin", fake):
        try:
            materias.excluir_materia(MATERIA_ID)
            assert False, "deveria levantar HTTPException"
        except Exception as erro:
            assert getattr(erro, "status_code", None) == 409
            assert "3 aula" in erro.detail

    fake.table("materias").delete.assert_not_called()


def test_excluir_materia_inexistente_retorna_404():
    fake = FakeSupabase()
    fake.table("materias").execute.return_value = query_result(data=[])

    with patch("routers.admin.materias.supabase_admin", fake):
        try:
            materias.excluir_materia(MATERIA_ID)
            assert False, "deveria levantar HTTPException"
        except Exception as erro:
            assert getattr(erro, "status_code", None) == 404
