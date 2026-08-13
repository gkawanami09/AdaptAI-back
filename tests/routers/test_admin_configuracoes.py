from unittest.mock import patch

from routers.admin import configuracoes
from services.ai.base import AIIndisponivelError
from schemas.configuracoes_schema import ConfiguracoesIaTestar
from tests.services._supabase_mock import FakeSupabase, query_result


def test_carregar_configuracoes_seeda_padroes_quando_tabela_vazia():
    fake = FakeSupabase()
    fake.table("configuracoes").execute.return_value = query_result(data=[])

    with patch("routers.admin.configuracoes.supabase_admin", fake):
        configuracoes_carregadas = configuracoes.carregar_configuracoes()

    assert configuracoes_carregadas == configuracoes.CONFIGURACOES_PADRAO
    # um upsert por seção ausente
    assert fake.table("configuracoes").upsert.call_count == len(configuracoes.CONFIGURACOES_PADRAO)


def test_carregar_configuracoes_usa_linhas_existentes_sem_seedar():
    fake = FakeSupabase()
    linhas = [{"chave": chave, "valor": valor} for chave, valor in configuracoes.CONFIGURACOES_PADRAO.items()]
    fake.table("configuracoes").execute.return_value = query_result(data=linhas)

    with patch("routers.admin.configuracoes.supabase_admin", fake):
        configuracoes_carregadas = configuracoes.carregar_configuracoes()

    assert configuracoes_carregadas == configuracoes.CONFIGURACOES_PADRAO
    fake.table("configuracoes").upsert.assert_not_called()


def test_salvar_configuracoes_faz_upsert_por_secao():
    fake = FakeSupabase()

    with patch("routers.admin.configuracoes.supabase_admin", fake):
        configuracoes.salvar_configuracoes({"gerais": {"nome_plataforma": "Teste"}})

    fake.table("configuracoes").upsert.assert_called_once()
    payload = fake.table("configuracoes").upsert.call_args[0][0]
    assert payload["chave"] == "gerais"
    assert payload["valor"] == {"nome_plataforma": "Teste"}
    assert "atualizado_em" in payload


def test_testar_configuracoes_ia_retorna_resposta_do_provider():
    dados = ConfiguracoesIaTestar(
        modelo="modelo-teste",
        temperatura=0.5,
        max_tokens=100,
        prompt_base="Você é um assistente.",
        prompt_teste="Olá!",
    )

    provider_mock = type("P", (), {"responder_chat": staticmethod(lambda mensagens, contexto=None: "Resposta real")})()

    with patch("routers.admin.configuracoes.get_ai_provider", return_value=provider_mock):
        resultado = configuracoes.testar_configuracoes_ia(dados)

    assert resultado["sucesso"] is True
    assert resultado["resposta"] == "Resposta real"
    assert resultado["tokens_utilizados"] > 0
    assert resultado["tempo_resposta_ms"] >= 0


def test_testar_configuracoes_ia_levanta_502_quando_provider_indisponivel():
    dados = ConfiguracoesIaTestar(
        modelo="modelo-teste",
        temperatura=0.5,
        max_tokens=100,
        prompt_base="Você é um assistente.",
        prompt_teste="Olá!",
    )

    def responder_chat_indisponivel(mensagens, contexto=None):
        raise AIIndisponivelError("timeout")

    provider_mock = type("P", (), {"responder_chat": staticmethod(responder_chat_indisponivel)})()

    with patch("routers.admin.configuracoes.get_ai_provider", return_value=provider_mock):
        try:
            configuracoes.testar_configuracoes_ia(dados)
            assert False, "deveria ter levantado HTTPException"
        except Exception as erro:
            assert getattr(erro, "status_code", None) == 502
