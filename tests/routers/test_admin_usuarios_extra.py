from unittest.mock import patch
from uuid import uuid4

from routers.admin import usuarios
from tests.services._supabase_mock import FakeSupabase, query_result

USUARIO_ID = str(uuid4())


def test_montar_usuario_detalhe_inclui_nivel_escola_ano_enem():
    fake = FakeSupabase()
    fake.table("estatisticas_usuario").execute.return_value = query_result(data=[{
        "ofensiva_atual_dias": 5, "maior_ofensiva_dias": 10, "xp_total": 500, "nivel": 7,
    }])
    fake.table("preferencias_aluno").execute.return_value = query_result(data=[{"ano_alvo": 2026}])
    fake.table("respostas_lista_questoes_aluno").execute.return_value = query_result(data=[])
    fake.table("atividade_diaria").execute.return_value = query_result(data=[])
    fake.table("progresso_lista_questoes_aluno").execute.return_value = query_result(data=[], count=0)
    fake.table("sessoes_simulado").execute.return_value = query_result(data=[], count=0)

    perfil = {"id": USUARIO_ID, "nome": "Maria", "escola_nome": "Colégio Exemplo", "tipo_usuario": "aluno", "situacao": "ativo"}

    with patch("routers.admin.usuarios.supabase_admin", fake):
        detalhe = usuarios.montar_usuario_detalhe(perfil, usuario_auth=None)

    assert detalhe["nivel"] == 7
    assert detalhe["escola"] == "Colégio Exemplo"
    assert detalhe["ano_enem"] == "2026"


def test_montar_usuario_detalhe_sem_preferencias_ano_enem_none():
    fake = FakeSupabase()
    fake.table("estatisticas_usuario").execute.return_value = query_result(data=[])
    fake.table("preferencias_aluno").execute.return_value = query_result(data=[])
    fake.table("respostas_lista_questoes_aluno").execute.return_value = query_result(data=[])
    fake.table("atividade_diaria").execute.return_value = query_result(data=[])
    fake.table("progresso_lista_questoes_aluno").execute.return_value = query_result(data=[], count=0)
    fake.table("sessoes_simulado").execute.return_value = query_result(data=[], count=0)

    perfil = {"id": USUARIO_ID, "nome": "João", "escola_nome": None, "tipo_usuario": "aluno", "situacao": "ativo"}

    with patch("routers.admin.usuarios.supabase_admin", fake):
        detalhe = usuarios.montar_usuario_detalhe(perfil, usuario_auth=None)

    assert detalhe["nivel"] == 1
    assert detalhe["escola"] is None
    assert detalhe["ano_enem"] is None
