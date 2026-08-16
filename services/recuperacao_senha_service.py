from datetime import datetime, timezone

from database import supabase_admin
from config import FRONTEND_URL
from utils.codigo_email import gerar_token_seguro, gerar_hash_codigo, codigo_expiracao_minutos
from services.envia_email import enviar_email_recuperacao_senha

EXPIRACAO_MINUTOS = 45
JANELA_RATE_LIMIT_MINUTOS = 15
LIMITE_SOLICITACOES_NA_JANELA = 3


def _dentro_do_rate_limit(email: str) -> bool:
    limite = codigo_expiracao_minutos(-JANELA_RATE_LIMIT_MINUTOS).isoformat()

    recentes = (
        supabase_admin.table("recuperacao_senha_tokens")
        .select("id")
        .eq("email", email)
        .gte("criado_em", limite)
        .execute()
        .data
    )

    return len(recentes or []) < LIMITE_SOLICITACOES_NA_JANELA


def solicitar_recuperacao(email: str) -> None:
    email = email.strip().lower()

    if not _dentro_do_rate_limit(email):
        # Silencioso de propósito: não revela se o email existe nem
        # expõe o rate limit ao chamador, para não ajudar enumeração.
        return

    usuarios = supabase_admin.auth.admin.list_users()
    usuario = next((u for u in usuarios if u.email and u.email.lower() == email), None)

    if not usuario:
        return

    perfil = (
        supabase_admin.table("perfis")
        .select("nome")
        .eq("id", usuario.id)
        .limit(1)
        .execute()
        .data
    )
    nome = perfil[0]["nome"] if perfil else "aluno"

    token = gerar_token_seguro()
    token_hash = gerar_hash_codigo(token)

    supabase_admin.table("recuperacao_senha_tokens").insert({
        "user_id": usuario.id,
        "email": email,
        "token_hash": token_hash,
        "expira_em": codigo_expiracao_minutos(EXPIRACAO_MINUTOS).isoformat(),
    }).execute()

    link = f"{FRONTEND_URL}/redefinir-senha?token={token}"

    try:
        enviar_email_recuperacao_senha(email, link, nome, EXPIRACAO_MINUTOS)
    except Exception as erro_email:
        print(f"Erro ao enviar email de recuperação de senha: {erro_email}")


class TokenInvalidoError(Exception):
    pass


class TokenExpiradoError(Exception):
    pass


def redefinir_senha(token: str, nova_senha: str) -> None:
    token_hash = gerar_hash_codigo(token)

    registro = (
        supabase_admin.table("recuperacao_senha_tokens")
        .select("*")
        .eq("token_hash", token_hash)
        .eq("usado", False)
        .limit(1)
        .execute()
        .data
    )

    if not registro:
        raise TokenInvalidoError()

    registro = registro[0]
    expira_em = datetime.fromisoformat(registro["expira_em"])
    if expira_em < datetime.now(timezone.utc):
        raise TokenExpiradoError()

    supabase_admin.auth.admin.update_user_by_id(
        registro["user_id"],
        {"password": nova_senha},
    )

    supabase_admin.table("recuperacao_senha_tokens").update({
        "usado": True,
    }).eq("id", registro["id"]).execute()

    # Invalida sessões antigas: qualquer refresh token emitido antes da
    # troca de senha deixa de funcionar.
    try:
        supabase_admin.auth.admin.sign_out(registro["user_id"], scope="global")
    except Exception as erro_sessao:
        print(f"Erro ao invalidar sessões após redefinição de senha: {erro_sessao}")
