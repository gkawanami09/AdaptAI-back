from unittest.mock import patch
from uuid import uuid4

from routers.admin import areas_conhecimento
from schemas.areas_conhecimento_schema import AreaConhecimentoCriar, AreaConhecimentoEditar
from tests.services._supabase_mock import FakeSupabase, query_result

AREA_ID = str(uuid4())


def test_criar_area_conhecimento_gera_slug_e_persiste():
    fake = FakeSupabase()
    fake.table("areas_conhecimento").execute.side_effect = [
        query_result(data=[]),  # checagem de slug duplicado
        query_result(data=[{
            "id": AREA_ID, "nome": "Ciências da Natureza", "slug": "ciencias-da-natureza",
            "descricao": "Física, Química e Biologia", "ativo": True, "criado_em": "2026-01-01T00:00:00Z",
        }]),
    ]

    dados = AreaConhecimentoCriar(nome="Ciências da Natureza", descricao="Física, Química e Biologia")

    with patch("routers.admin.areas_conhecimento.supabase_admin", fake):
        resultado = areas_conhecimento.criar_area_conhecimento(dados)

    assert resultado["sucesso"] is True
    assert resultado["area"]["slug"] == "ciencias-da-natureza"
    payload_inserido = fake.table("areas_conhecimento").insert.call_args[0][0]
    assert payload_inserido["slug"] == "ciencias-da-natureza"
    assert payload_inserido["nome"] == "Ciências da Natureza"


def test_criar_area_conhecimento_duplicada_retorna_422():
    fake = FakeSupabase()
    fake.table("areas_conhecimento").execute.return_value = query_result(data=[{"id": AREA_ID}])

    dados = AreaConhecimentoCriar(nome="Ciências da Natureza")

    with patch("routers.admin.areas_conhecimento.supabase_admin", fake):
        try:
            areas_conhecimento.criar_area_conhecimento(dados)
            assert False, "deveria levantar HTTPException"
        except Exception as erro:
            assert getattr(erro, "status_code", None) == 422


def test_buscar_area_conhecimento_inexistente_retorna_404():
    fake = FakeSupabase()
    fake.table("areas_conhecimento").execute.return_value = query_result(data=[])

    with patch("routers.admin.areas_conhecimento.supabase_admin", fake):
        try:
            areas_conhecimento.buscar_area_conhecimento(AREA_ID)
            assert False, "deveria levantar HTTPException"
        except Exception as erro:
            assert getattr(erro, "status_code", None) == 404


def test_editar_area_conhecimento_sem_alteracoes_retorna_422():
    fake = FakeSupabase()

    with patch("routers.admin.areas_conhecimento.supabase_admin", fake):
        try:
            areas_conhecimento.editar_area_conhecimento(AREA_ID, AreaConhecimentoEditar())
            assert False, "deveria levantar HTTPException"
        except Exception as erro:
            assert getattr(erro, "status_code", None) == 422


def test_excluir_area_conhecimento_chama_delete():
    fake = FakeSupabase()
    fake.table("areas_conhecimento").execute.return_value = query_result(data=[{"id": AREA_ID}])

    with patch("routers.admin.areas_conhecimento.supabase_admin", fake):
        resultado = areas_conhecimento.excluir_area_conhecimento(AREA_ID)

    assert resultado["sucesso"] is True
    fake.table("areas_conhecimento").delete.assert_called_once()
