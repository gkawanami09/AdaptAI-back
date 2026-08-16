from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from routers import auth as auth_router
from services import recuperacao_senha_service
from utils.codigo_email import gerar_hash_codigo


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
            for metodo in ("select", "eq", "neq", "in_", "order", "limit", "range", "gte", "lt", "insert", "update", "delete"):
                getattr(mock, metodo).return_value = mock
            mock.execute.return_value = query_result(data=[])
            self._tabelas[nome] = mock
        return self._tabelas[nome]


@pytest.fixture
def app_cliente(monkeypatch):
    fake = FakeSupabase()
    monkeypatch.setattr(recuperacao_senha_service, "supabase_admin", fake)
    monkeypatch.setenv("EMAIL_CODE_SECRET", "segredo-teste")
    monkeypatch.setattr(recuperacao_senha_service, "enviar_email_recuperacao_senha", lambda *a, **k: None)

    app = FastAPI()
    app.include_router(auth_router.router)
    cliente = TestClient(app)
    return cliente, fake


def test_esqueci_senha_email_existente_retorna_mensagem_padrao(app_cliente):
    cliente, fake = app_cliente
    usuario_id = str(uuid4())
    fake.auth.admin.list_users.return_value = [SimpleNamespace(id=usuario_id, email="maria@email.com")]
    fake.table("perfis").execute.return_value = query_result(data=[{"nome": "Maria"}])

    resposta = cliente.post("/auth/esqueci-senha", json={"email": "maria@email.com"})

    assert resposta.status_code == 200
    assert resposta.json() == {
        "mensagem": "Se este email estiver cadastrado, enviaremos instruções para redefinir sua senha."
    }
    fake.table("recuperacao_senha_tokens").insert.assert_called_once()


def test_esqueci_senha_email_inexistente_retorna_mesma_resposta(app_cliente):
    cliente, fake = app_cliente
    fake.auth.admin.list_users.return_value = []

    resposta = cliente.post("/auth/esqueci-senha", json={"email": "naoexiste@email.com"})

    assert resposta.status_code == 200
    assert resposta.json() == {
        "mensagem": "Se este email estiver cadastrado, enviaremos instruções para redefinir sua senha."
    }
    fake.table("recuperacao_senha_tokens").insert.assert_not_called()


def test_redefinir_senha_com_token_valido(app_cliente):
    cliente, fake = app_cliente
    token = "token-valido"
    usuario_id = str(uuid4())

    fake.table("recuperacao_senha_tokens").execute.return_value = query_result(data=[{
        "id": 1,
        "user_id": usuario_id,
        "token_hash": gerar_hash_codigo(token),
        "usado": False,
        "expira_em": (datetime.now(timezone.utc) + timedelta(minutes=30)).isoformat(),
    }])

    resposta = cliente.post(
        "/auth/redefinir-senha",
        json={"token": token, "nova_senha": "NovaSenhaSegura456!"},
    )

    assert resposta.status_code == 200
    assert resposta.json() == {"sucesso": True}
    fake.auth.admin.update_user_by_id.assert_called_once_with(
        usuario_id, {"password": "NovaSenhaSegura456!"}
    )
    fake.table("recuperacao_senha_tokens").update.assert_called_once_with({"usado": True})


def test_redefinir_senha_token_expirado_retorna_410(app_cliente):
    cliente, fake = app_cliente
    token = "token-expirado"
    usuario_id = str(uuid4())

    fake.table("recuperacao_senha_tokens").execute.return_value = query_result(data=[{
        "id": 1,
        "user_id": usuario_id,
        "token_hash": gerar_hash_codigo(token),
        "usado": False,
        "expira_em": (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat(),
    }])

    resposta = cliente.post(
        "/auth/redefinir-senha",
        json={"token": token, "nova_senha": "NovaSenhaSegura456!"},
    )

    assert resposta.status_code == 410


def test_redefinir_senha_token_invalido_retorna_401(app_cliente):
    cliente, fake = app_cliente
    fake.table("recuperacao_senha_tokens").execute.return_value = query_result(data=[])

    resposta = cliente.post(
        "/auth/redefinir-senha",
        json={"token": "qualquer", "nova_senha": "NovaSenhaSegura456!"},
    )

    assert resposta.status_code == 401


def test_redefinir_senha_nao_pode_ser_reutilizado(app_cliente):
    cliente, fake = app_cliente
    token = "token-usado"
    fake.table("recuperacao_senha_tokens").execute.return_value = query_result(data=[])

    resposta = cliente.post(
        "/auth/redefinir-senha",
        json={"token": token, "nova_senha": "NovaSenhaSegura456!"},
    )

    assert resposta.status_code == 401


def test_redefinir_senha_invalida_retorna_400(app_cliente):
    cliente, fake = app_cliente

    resposta = cliente.post(
        "/auth/redefinir-senha",
        json={"token": "qualquer", "nova_senha": "123"},
    )

    assert resposta.status_code == 400
