from datetime import date, timedelta
from unittest.mock import patch
from uuid import uuid4

from routers import plano_estudos
from tests.services._supabase_mock import FakeSupabase, query_result

USUARIO_ID = str(uuid4())
PLANO_ID = str(uuid4())


class _UsuarioFake:
    id = USUARIO_ID


def test_reorganizar_sem_plano_ativo_retorna_422():
    fake = FakeSupabase()
    fake.table("planos_estudo").execute.return_value = query_result(data=[])

    with patch("routers.plano_estudos.supabase_admin", fake):
        try:
            plano_estudos.reorganizar_plano_ia(usuario_atual=_UsuarioFake())
            assert False, "deveria levantar HTTPException"
        except Exception as erro:
            assert getattr(erro, "status_code", None) == 422


def test_reorganizar_sem_tarefas_pendentes_retorna_422():
    fake = FakeSupabase()
    hoje = date.today()
    fake.table("planos_estudo").execute.return_value = query_result(
        data=[{
            "id": PLANO_ID,
            "data_fim": (hoje + timedelta(days=14)).isoformat(),
            "dias_estudo": ["monday", "tuesday", "wednesday", "thursday", "friday"],
        }]
    )
    fake.table("tarefas_estudo").execute.return_value = query_result(data=[])

    with patch("routers.plano_estudos.supabase_admin", fake):
        try:
            plano_estudos.reorganizar_plano_ia(usuario_atual=_UsuarioFake())
            assert False, "deveria levantar HTTPException"
        except Exception as erro:
            assert getattr(erro, "status_code", None) == 422


def test_reorganizar_redistribui_tarefas_pendentes():
    fake = FakeSupabase()
    hoje = date.today()

    fake.table("planos_estudo").execute.return_value = query_result(
        data=[{
            "id": PLANO_ID,
            "data_fim": (hoje + timedelta(days=14)).isoformat(),
            "dias_estudo": ["monday", "tuesday", "wednesday", "thursday", "friday"],
        }]
    )

    tarefas = [{"id": str(uuid4()), "ordem": 0}, {"id": str(uuid4()), "ordem": 1}]
    fake.table("tarefas_estudo").execute.return_value = query_result(data=tarefas)

    with patch("routers.plano_estudos.supabase_admin", fake):
        resultado = plano_estudos.reorganizar_plano_ia(usuario_atual=_UsuarioFake())

    assert resultado == {"sucesso": True}
    assert fake.table("tarefas_estudo").update.call_count == len(tarefas)
