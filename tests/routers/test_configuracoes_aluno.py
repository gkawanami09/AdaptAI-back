from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from routers import configuracoes_aluno as configuracoes_router
from routers import conta_aluno as conta_router
from utils.autenticacao import pegar_usuario_atual


def query_result(data=None):
    resultado = MagicMock()
    resultado.data = data
    return resultado


class FakeSupabase:
    def __init__(self):
        self._tabelas: dict[str, MagicMock] = {}
        self.auth = MagicMock()

    def table(self, nome: str) -> MagicMock:
        if nome not in self._tabelas:
            mock = MagicMock(name=f"tabela_{nome}")
            for metodo in ("select", "eq", "neq", "in_", "order", "limit", "range", "gte", "lt", "insert", "update", "upsert", "delete"):
                getattr(mock, metodo).return_value = mock
            mock.execute.return_value = query_result(data=[])
            self._tabelas[nome] = mock
        return self._tabelas[nome]


USUARIO_ID = str(uuid4())
USUARIO = SimpleNamespace(id=USUARIO_ID, email="maria@email.com")


@pytest.fixture
def app_cliente(monkeypatch):
    fake = FakeSupabase()
    monkeypatch.setattr(configuracoes_router, "supabase_admin", fake)
    monkeypatch.setattr(configuracoes_router, "supabase", fake)
    monkeypatch.setattr("services.dados_ia_service.supabase_admin", fake)

    fake.table("perfis").execute.return_value = query_result(
        data=[{"nome": "Maria Silva", "escola_nome": "Colégio Exemplo"}]
    )
    fake.table("estatisticas_usuario").execute.return_value = query_result(
        data=[{"nivel": 12, "xp_total": 4820}]
    )
    fake.table("preferencias_aluno").execute.return_value = query_result(
        data=[{"ano_alvo": 2026}]
    )
    fake.table("configuracoes_usuario").execute.return_value = query_result(
        data=[{
            "usuario_id": USUARIO_ID,
            "tema": "sistema",
            "lembrete_estudo_ativo": True,
            "alerta_ofensiva_ativo": True,
            "notificacao_conquistas_ativa": True,
            "novidades_adaptai_ativo": False,
        }]
    )

    app = FastAPI()
    app.include_router(configuracoes_router.router)
    app.dependency_overrides[pegar_usuario_atual] = lambda: USUARIO

    cliente = TestClient(app)
    return cliente, fake


def test_get_configuracoes_sem_autenticacao_retorna_401():
    app = FastAPI()
    app.include_router(configuracoes_router.router)
    cliente = TestClient(app)

    resposta = cliente.get("/aluno/configuracoes")
    assert resposta.status_code == 403 or resposta.status_code == 401


def test_get_configuracoes_retorna_perfil_notificacoes_e_aparencia(app_cliente):
    cliente, fake = app_cliente

    resposta = cliente.get("/aluno/configuracoes")

    assert resposta.status_code == 200
    corpo = resposta.json()

    assert corpo["perfil"]["nome"] == "Maria Silva"
    assert corpo["perfil"]["email"] == "maria@email.com"
    assert corpo["perfil"]["nivel"] == 12
    assert corpo["perfil"]["xp_total"] == 4820

    ids_notificacoes = {n["id"] for n in corpo["notificacoes"]}
    assert ids_notificacoes == {"lembrete-diario", "alerta-ofensiva", "novas-conquistas", "novidades"}
    assert "relatorio-semanal" not in ids_notificacoes

    assert "metas" not in corpo
    assert corpo["aparencia"] == {"tema": "sistema"}


def test_patch_perfil_atualiza_nome_e_escola_mas_nao_email(app_cliente):
    cliente, fake = app_cliente

    payload = {"nome": "Maria Souza", "escola": "Nova Escola", "ano_enem": "2027"}
    resposta = cliente.patch("/aluno/configuracoes/perfil", json=payload)

    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["email"] == "maria@email.com"

    dados_atualizados = fake.table("perfis").update.call_args[0][0]
    assert dados_atualizados["nome"] == "Maria Souza"
    assert dados_atualizados["escola_nome"] == "Nova Escola"
    assert "email" not in dados_atualizados


def test_patch_notificacoes_ativa_e_desativa(app_cliente):
    cliente, fake = app_cliente

    resposta = cliente.patch(
        "/aluno/configuracoes/notificacoes",
        json={"id": "lembrete-diario", "enabled": False},
    )

    assert resposta.status_code == 200
    assert resposta.json() == {"id": "lembrete-diario", "enabled": False}


def test_patch_notificacoes_id_invalido_retorna_404(app_cliente):
    cliente, fake = app_cliente

    resposta = cliente.patch(
        "/aluno/configuracoes/notificacoes",
        json={"id": "relatorio-semanal", "enabled": True},
    )

    assert resposta.status_code == 404


def test_patch_aparencia_continua_funcionando(app_cliente):
    cliente, fake = app_cliente

    resposta = cliente.patch("/aluno/configuracoes/aparencia", json={"tema": "escuro"})

    assert resposta.status_code == 200
    assert resposta.json() == {"tema": "escuro"}


def test_alterar_senha_com_senha_atual_correta(app_cliente):
    cliente, fake = app_cliente
    fake.auth.sign_in_with_password.return_value = SimpleNamespace(user=USUARIO)

    resposta = cliente.post(
        "/aluno/configuracoes/senha",
        json={"senha_atual": "SenhaAtual123!", "nova_senha": "NovaSenhaSegura456!"},
    )

    assert resposta.status_code == 200
    assert resposta.json() == {"sucesso": True}
    fake.auth.admin.update_user_by_id.assert_called_once()


def test_alterar_senha_com_senha_atual_incorreta_retorna_403(app_cliente):
    cliente, fake = app_cliente
    fake.auth.sign_in_with_password.side_effect = Exception("Invalid login credentials")

    resposta = cliente.post(
        "/aluno/configuracoes/senha",
        json={"senha_atual": "errada", "nova_senha": "NovaSenhaSegura456!"},
    )

    assert resposta.status_code == 403


def test_alterar_senha_nova_senha_fraca_retorna_400(app_cliente):
    cliente, fake = app_cliente

    resposta = cliente.post(
        "/aluno/configuracoes/senha",
        json={"senha_atual": "SenhaAtual123!", "nova_senha": "123"},
    )

    assert resposta.status_code == 400


def test_dados_ia_retorna_apenas_categorias_do_usuario(app_cliente):
    cliente, fake = app_cliente
    fake.table("preferencias_dados_ia").execute.return_value = query_result(
        data=[{"categoria_id": "redacoes", "utilizado": False}]
    )

    resposta = cliente.get("/aluno/configuracoes/dados-ia")

    assert resposta.status_code == 200
    corpo = resposta.json()
    ids = {d["id"] for d in corpo["dados"]}
    assert ids == {"desempenho-matematica", "questoes-erradas", "tempo-estudo", "redacoes"}

    redacoes = next(d for d in corpo["dados"] if d["id"] == "redacoes")
    assert redacoes["utilizado"] is False


def test_patch_dados_ia_categoria_invalida_retorna_404(app_cliente):
    cliente, fake = app_cliente

    resposta = cliente.patch(
        "/aluno/configuracoes/dados-ia",
        json={"id": "categoria-inexistente", "utilizado": False},
    )

    assert resposta.status_code == 404


def test_patch_dados_ia_desativa_categoria(app_cliente):
    cliente, fake = app_cliente

    resposta = cliente.patch(
        "/aluno/configuracoes/dados-ia",
        json={"id": "redacoes", "utilizado": False},
    )

    assert resposta.status_code == 200
    assert resposta.json() == {"id": "redacoes", "utilizado": False}
    fake.table("preferencias_dados_ia").upsert.assert_called_once()


@pytest.fixture
def conta_cliente(monkeypatch):
    fake = FakeSupabase()
    monkeypatch.setattr(conta_router, "supabase", fake)
    monkeypatch.setattr("services.exclusao_conta_service.supabase_admin", fake)

    app = FastAPI()
    app.include_router(conta_router.router)
    app.dependency_overrides[pegar_usuario_atual] = lambda: USUARIO

    cliente = TestClient(app)
    return cliente, fake


def test_excluir_conta_sem_autenticacao_retorna_401():
    app = FastAPI()
    app.include_router(conta_router.router)
    cliente = TestClient(app)

    resposta = cliente.request("DELETE", "/aluno/conta", json={"senha": "x"})
    assert resposta.status_code in (401, 403)


def test_excluir_conta_com_senha_correta(conta_cliente):
    cliente, fake = conta_cliente
    fake.auth.sign_in_with_password.return_value = SimpleNamespace(user=USUARIO)

    resposta = cliente.request(
        "DELETE", "/aluno/conta", json={"senha": "SenhaAtual123!"}
    )

    assert resposta.status_code == 200
    assert resposta.json() == {"sucesso": True}
    fake.auth.admin.delete_user.assert_called_once_with(USUARIO_ID)


def test_excluir_conta_com_senha_incorreta_nao_exclui(conta_cliente):
    cliente, fake = conta_cliente
    fake.auth.sign_in_with_password.side_effect = Exception("Invalid login credentials")

    resposta = cliente.request("DELETE", "/aluno/conta", json={"senha": "errada"})

    assert resposta.status_code == 403
    fake.auth.admin.delete_user.assert_not_called()
