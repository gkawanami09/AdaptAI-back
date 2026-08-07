import re
import unicodedata
from datetime import datetime, timezone

from fastapi import HTTPException

from database import supabase_admin

TITULO_PADRAO = "Nova conversa"

# autor (mensagens_ia) <-> role usado internamente pelo chat/IA
AUTOR_PARA_ROLE = {"usuario": "user", "assistente": "assistant", "sistema": "system"}
ROLE_PARA_AUTOR = {"user": "usuario", "assistant": "assistente", "system": "sistema"}


def _slugificar(texto: str) -> str:
    texto_sem_acento = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-z0-9]+", "-", texto_sem_acento.lower()).strip("-")
    return slug or "conversa"


def _resumir_titulo(mensagem: str, tamanho_maximo: int = 60) -> str:
    mensagem_limpa = " ".join(mensagem.strip().split())
    if len(mensagem_limpa) <= tamanho_maximo:
        return mensagem_limpa
    return mensagem_limpa[:tamanho_maximo].rstrip() + "..."


class ConversationService:
    """Responsável por toda a persistência e regras de negócio das
    conversas e mensagens do Chat da Ada. Reutiliza as tabelas
    já existentes `conversas_ia` / `mensagens_ia`. O controller
    (routers/chat.py) nunca acessa supabase_admin diretamente para
    essas tabelas — sempre passa por este service.
    """

    def listar_conversas(self, aluno_id: str) -> list[dict]:
        resposta = (
            supabase_admin.table("conversas_ia")
            .select("id, titulo, atualizado_em")
            .eq("usuario_id", aluno_id)
            .eq("tipo_contexto", "chat_geral")
            .order("atualizado_em", desc=True)
            .execute()
        )
        return resposta.data or []

    def criar_conversa(self, aluno_id: str, titulo: str | None) -> dict:
        titulo_final = titulo.strip() if titulo and titulo.strip() else TITULO_PADRAO

        resposta = (
            supabase_admin.table("conversas_ia")
            .insert({
                "usuario_id": aluno_id,
                "titulo": titulo_final,
                "tipo_contexto": "chat_geral",
            })
            .execute()
        )
        return resposta.data[0]

    def obter_conversa_do_aluno(self, conversa_id: str, aluno_id: str) -> dict:
        resposta = (
            supabase_admin.table("conversas_ia")
            .select("id, titulo, usuario_id, criado_em, atualizado_em")
            .eq("id", conversa_id)
            .eq("usuario_id", aluno_id)
            .limit(1)
            .execute()
        )
        if not resposta.data:
            raise HTTPException(status_code=404, detail="Conversa não encontrada")
        return resposta.data[0]

    def listar_mensagens(self, conversa_id: str) -> list[dict]:
        resposta = (
            supabase_admin.table("mensagens_ia")
            .select("id, autor, conteudo, criado_em")
            .eq("conversa_id", conversa_id)
            .order("criado_em")
            .execute()
        )
        return [self._normalizar_mensagem(m) for m in (resposta.data or [])]

    def _normalizar_mensagem(self, mensagem: dict) -> dict:
        return {
            "id": mensagem["id"],
            "role": AUTOR_PARA_ROLE[mensagem["autor"]],
            "content": mensagem["conteudo"],
            "criado_em": mensagem["criado_em"],
        }

    def salvar_mensagem(self, conversa_id: str, role: str, content: str) -> dict:
        resposta = (
            supabase_admin.table("mensagens_ia")
            .insert({
                "conversa_id": conversa_id,
                "autor": ROLE_PARA_AUTOR[role],
                "conteudo": content,
            })
            .execute()
        )
        return self._normalizar_mensagem(resposta.data[0])

    def tocar_conversa(self, conversa_id: str) -> None:
        (
            supabase_admin.table("conversas_ia")
            .update({"atualizado_em": datetime.now(timezone.utc).isoformat()})
            .eq("id", conversa_id)
            .execute()
        )

    def atualizar_titulo_automatico_se_necessario(self, conversa: dict, primeira_mensagem_usuario: str) -> None:
        if conversa["titulo"] != TITULO_PADRAO:
            return

        novo_titulo = _resumir_titulo(primeira_mensagem_usuario)
        (
            supabase_admin.table("conversas_ia")
            .update({"titulo": novo_titulo})
            .eq("id", conversa["id"])
            .execute()
        )

    def renomear_conversa(self, conversa_id: str, aluno_id: str, titulo: str) -> dict:
        self.obter_conversa_do_aluno(conversa_id, aluno_id)

        resposta = (
            supabase_admin.table("conversas_ia")
            .update({"titulo": titulo.strip()})
            .eq("id", conversa_id)
            .execute()
        )
        return resposta.data[0]

    def excluir_conversa(self, conversa_id: str, aluno_id: str) -> None:
        self.obter_conversa_do_aluno(conversa_id, aluno_id)

        (
            supabase_admin.table("mensagens_ia")
            .delete()
            .eq("conversa_id", conversa_id)
            .execute()
        )
        (
            supabase_admin.table("conversas_ia")
            .delete()
            .eq("id", conversa_id)
            .execute()
        )

    def obter_ultima_mensagem_por_role(self, conversa_id: str, role: str) -> dict | None:
        resposta = (
            supabase_admin.table("mensagens_ia")
            .select("id, autor, conteudo, criado_em")
            .eq("conversa_id", conversa_id)
            .eq("autor", ROLE_PARA_AUTOR[role])
            .order("criado_em", desc=True)
            .limit(1)
            .execute()
        )
        return self._normalizar_mensagem(resposta.data[0]) if resposta.data else None

    def excluir_mensagem(self, mensagem_id: str) -> None:
        (
            supabase_admin.table("mensagens_ia")
            .delete()
            .eq("id", mensagem_id)
            .execute()
        )

    def gerar_slug(self, conversa_id: str, titulo: str) -> str:
        return f"{_slugificar(titulo)}-{conversa_id[:8]}"
