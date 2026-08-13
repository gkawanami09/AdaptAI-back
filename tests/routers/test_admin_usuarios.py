from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from routers.admin import usuarios as usuarios_router
from utils.autenticacao import exigir_administrador, pegar_usuario_atual


def query_result(data=None, count=None):
    resultado = MagicMock()
    resultado.data = data
    resultado.count = count
    return resultado


class FakeSupabase:
    """Mock mínimo de supabase_admin (mesmo padrão de tests/services/_supabase_mock.py):
    toda tabela devolve o mesmo mock encadeável (select/eq/in_/neq/limit/order/range...
    retornam self), e `.execute()` é configurado por teste via
    `tabela(nome).execute.side_effect` ou `.return_value`.
    """

    def __init__(self):
        self._tabelas: dict[str, MagicMock] = {}

    def table(self, nome: str) -> MagicMock:
        if nome not in self._tabelas:
            mock = MagicMock(name=f"tabela_{nome}")
            for metodo in ("select", "eq", "neq", "in_", "order", "limit", "range", "gte", "lt", "insert", "update", "delete"):
                getattr(mock, metodo).return_value = mock
            self._tabelas[nome] = mock
        return self._tabelas[nome]

ADMIN_ID = str(uuid4())
USUARIO_ID = str(uuid4())


@pytest.fixture
def app_cliente(monkeypatch):
    fake = FakeSupabase()
    fake.auth = MagicMock()
    fake.auth.admin.get_user_by_id.return_value = SimpleNamespace(
        user=SimpleNamespace(email="usuario@teste.com", email_confirmed_at=None)
    )
    monkeypatch.setattr(usuarios_router, "supabase_admin", fake)

    # montar_usuario_detalhe faz consultas auxiliares (estatísticas, respostas,
    # atividades, listas, provas) que precisam devolver dados vazios em vez do
    # MagicMock truthy padrão, senão `sum(... for r in respostas)` explode.
    for tabela in (
        "estatisticas_usuario",
        "respostas_lista_questoes_aluno",
        "atividade_diaria",
        "progresso_lista_questoes_aluno",
        "sessoes_simulado",
    ):
        fake.table(tabela).execute.return_value = query_result(data=[], count=0)

    app = FastAPI()
    app.include_router(usuarios_router.router)
    app.dependency_overrides[exigir_administrador] = lambda: SimpleNamespace(id=ADMIN_ID)
    app.dependency_overrides[pegar_usuario_atual] = lambda: SimpleNamespace(id=ADMIN_ID)

    cliente = TestClient(app)
    return cliente, fake


def _mock_usuario_existe(fake, usuario_id=USUARIO_ID):
    fake.table("perfis").execute.return_value = query_result(data=[{"id": usuario_id}])


def test_obter_historico_ofensiva_retorna_linhas_da_tabela(app_cliente):
    cliente, fake = app_cliente
    _mock_usuario_existe(fake)

    historico = [
        {"data": "2026-08-10", "ofensiva_dias": 3},
        {"data": "2026-08-11", "ofensiva_dias": 4},
    ]
    fake.table("streak_historico").execute.return_value = query_result(data=historico)

    resposta = cliente.get(f"/admin/usuarios/{USUARIO_ID}/ofensiva-historico")

    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["sucesso"] is True
    assert corpo["historico"] == historico


def test_obter_conquistas_retorna_conquistas_desbloqueadas(app_cliente):
    cliente, fake = app_cliente
    _mock_usuario_existe(fake)

    desbloqueadas = [
        {
            "conquista_id": "c1",
            "desbloqueado_em": "2026-08-01T00:00:00Z",
            "conquistas": {
                "titulo": "Primeira Semana",
                "descricao": "desc",
                "icone": "🏆",
                "raridade": "comum",
                "xp_recompensa": 50,
            },
        }
    ]
    fake.table("conquistas_usuario").execute.return_value = query_result(data=desbloqueadas)

    resposta = cliente.get(f"/admin/usuarios/{USUARIO_ID}/conquistas")

    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["sucesso"] is True
    assert len(corpo["conquistas"]) == 1
    assert corpo["conquistas"][0]["titulo"] == "Primeira Semana"
    assert corpo["conquistas"][0]["xp"] == 50


def test_obter_medidas_retorna_acoes_administrativas(app_cliente):
    cliente, fake = app_cliente
    _mock_usuario_existe(fake)

    medidas = [
        {
            "id": "m1",
            "tipo": "suspensao",
            "motivo": "spam",
            "duracao_dias": 7,
            "administrador_id": ADMIN_ID,
            "criado_em": "2026-08-01T00:00:00Z",
        }
    ]
    fake.table("acoes_administrativas").execute.return_value = query_result(data=medidas)

    resposta = cliente.get(f"/admin/usuarios/{USUARIO_ID}/medidas")

    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["sucesso"] is True
    assert corpo["medidas"] == medidas


def test_suspender_usuario_insere_acao_administrativa(app_cliente):
    cliente, fake = app_cliente

    fake.table("perfis").execute.return_value = query_result(data=[{
        "id": USUARIO_ID,
        "nome": "Usuário Teste",
        "tipo_usuario": "aluno",
        "situacao": "ativo",
        "criado_em": "2026-01-01T00:00:00Z",
    }])

    payload = {"motivo": "violacao das regras", "duracao_dias": 7}
    resposta = cliente.post(f"/admin/usuarios/{USUARIO_ID}/suspender", json=payload)

    assert resposta.status_code == 200
    fake.table("acoes_administrativas").insert.assert_called_once()
    dados_inseridos = fake.table("acoes_administrativas").insert.call_args[0][0]
    assert dados_inseridos["tipo"] == "suspensao"
    assert dados_inseridos["usuario_id"] == USUARIO_ID
    assert dados_inseridos["administrador_id"] == ADMIN_ID
    assert dados_inseridos["motivo"] == "violacao das regras"
    assert dados_inseridos["duracao_dias"] == 7


def test_banir_usuario_insere_acao_administrativa(app_cliente):
    cliente, fake = app_cliente

    fake.table("perfis").execute.return_value = query_result(data=[{
        "id": USUARIO_ID,
        "nome": "Usuário Teste",
        "tipo_usuario": "aluno",
        "situacao": "ativo",
        "criado_em": "2026-01-01T00:00:00Z",
    }])

    payload = {"motivo": "conduta grave"}
    resposta = cliente.post(f"/admin/usuarios/{USUARIO_ID}/banir", json=payload)

    assert resposta.status_code == 200
    fake.table("acoes_administrativas").insert.assert_called_once()
    dados_inseridos = fake.table("acoes_administrativas").insert.call_args[0][0]
    assert dados_inseridos["tipo"] == "banimento"
    assert dados_inseridos["usuario_id"] == USUARIO_ID
    assert dados_inseridos["motivo"] == "conduta grave"


def test_resetar_ofensiva_atualiza_estatisticas_e_insere_acao(app_cliente):
    cliente, fake = app_cliente

    fake.table("perfis").execute.return_value = query_result(data=[{
        "id": USUARIO_ID,
        "nome": "Usuário Teste",
        "tipo_usuario": "aluno",
        "situacao": "ativo",
        "criado_em": "2026-01-01T00:00:00Z",
    }])

    resposta = cliente.post(f"/admin/usuarios/{USUARIO_ID}/resetar-ofensiva")

    assert resposta.status_code == 200
    fake.table("estatisticas_usuario").update.assert_called_once_with({"ofensiva_atual_dias": 0})
    fake.table("acoes_administrativas").insert.assert_called_once()
    dados_inseridos = fake.table("acoes_administrativas").insert.call_args[0][0]
    assert dados_inseridos["tipo"] == "reset_ofensiva"
    assert dados_inseridos["usuario_id"] == USUARIO_ID
