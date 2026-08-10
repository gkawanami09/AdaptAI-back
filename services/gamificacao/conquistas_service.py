import logging

from postgrest.exceptions import APIError

from database import supabase_admin
from services.gamificacao.eventos import EventoGamificacao
from services.gamificacao.metricas import MEDIDORES
from services.gamificacao.xp_service import conceder_xp

logger = logging.getLogger("gamificacao_conquistas")

UNIQUE_VIOLATION = "23505"

# Só avalia as conquistas cujo tipo_condicao está relacionado ao evento —
# evita recalcular as 9 conquistas a cada questão respondida.
EVENTO_PARA_CONDICOES: dict[EventoGamificacao, tuple[str, ...]] = {
    EventoGamificacao.QUESTAO_RESPONDIDA: ("questoes_respondidas",),
    EventoGamificacao.QUESTAO_ACERTADA: ("percentual_acerto_materia",),
    EventoGamificacao.REVISAO_QUESTAO_CONCLUIDA: ("questoes_erradas_revisadas",),
    EventoGamificacao.AULA_CONCLUIDA: ("dias_estudo", "ofensiva_dias"),
    EventoGamificacao.SESSAO_ESTUDO_CONCLUIDA: ("dias_estudo", "ofensiva_dias", "minutos_estudo_dia"),
    EventoGamificacao.REDACAO_ENVIADA: ("redacoes_enviadas",),
    EventoGamificacao.CORRECAO_REDACAO_CONCLUIDA: ("nota_redacao",),
    EventoGamificacao.SIMULADO_CONCLUIDO: ("simulados_completos",),
}


def _buscar_conquistas_pendentes(usuario_id: str, condicoes: tuple[str, ...]) -> list[dict]:
    conquistas = (
        supabase_admin.table("conquistas")
        .select("id, titulo, descricao, xp_recompensa, tipo_condicao, valor_condicao, materia_id")
        .eq("ativo", True)
        .in_("tipo_condicao", condicoes)
        .execute()
        .data or []
    )
    if not conquistas:
        return []

    ids_desbloqueadas = {
        c["conquista_id"] for c in
        supabase_admin.table("conquistas_usuario")
        .select("conquista_id")
        .eq("usuario_id", usuario_id)
        .in_("conquista_id", [c["id"] for c in conquistas])
        .execute()
        .data or []
    }

    return [c for c in conquistas if c["id"] not in ids_desbloqueadas]


def desbloquear_conquista(usuario_id: str, conquista: dict) -> bool:
    """Insere o desbloqueio e concede o XP da conquista. Idempotente: se
    a conquista já estava desbloqueada (inclusive por uma requisição
    concorrente), o UNIQUE(usuario_id, conquista_id) no banco rejeita o
    insert duplicado e nenhum XP extra é concedido.
    """
    try:
        supabase_admin.table("conquistas_usuario").insert({
            "usuario_id": usuario_id,
            "conquista_id": conquista["id"],
        }).execute()
    except APIError as erro:
        if erro.code == UNIQUE_VIOLATION:
            return False
        raise

    if conquista["xp_recompensa"] > 0:
        conceder_xp(usuario_id, conquista["xp_recompensa"])

    _notificar_desbloqueio(usuario_id, conquista)

    return True


def _notificar_desbloqueio(usuario_id: str, conquista: dict) -> None:
    """Best-effort: uma falha aqui não desfaz o desbloqueio nem o XP, já
    commitados antes. Só registra e segue."""
    try:
        supabase_admin.table("notificacoes").insert({
            "usuario_id": usuario_id,
            "titulo": f"Conquista desbloqueada: {conquista['titulo']}",
            "mensagem": conquista.get("descricao") or "",
            "tipo": "conquista",
            "link_acao": "/conquistas",
        }).execute()
    except Exception:
        logger.exception("Falha ao criar notificação de conquista desbloqueada usuario_id=%s conquista_id=%s", usuario_id, conquista["id"])


def avaliar_conquistas(usuario_id: str, evento: EventoGamificacao, dados: dict | None = None) -> list[str]:
    condicoes = EVENTO_PARA_CONDICOES.get(evento)
    if not condicoes:
        return []

    dados = dados or {}
    pendentes = _buscar_conquistas_pendentes(usuario_id, condicoes)
    if not pendentes:
        return []

    if evento == EventoGamificacao.QUESTAO_ACERTADA and dados.get("materia_id"):
        pendentes = [c for c in pendentes if c.get("materia_id") == dados["materia_id"]]

    desbloqueadas = []
    for conquista in pendentes:
        medidor = MEDIDORES.get(conquista["tipo_condicao"])
        if medidor is None:
            logger.warning("Conquista com tipo_condicao sem medidor: %s", conquista["tipo_condicao"])
            continue

        valor_atual = medidor(usuario_id, conquista)
        if valor_atual >= conquista["valor_condicao"]:
            if desbloquear_conquista(usuario_id, conquista):
                desbloqueadas.append(conquista["id"])

    return desbloqueadas


def recalcular_conquistas_aluno(usuario_id: str) -> list[str]:
    """Avalia TODAS as conquistas ativas contra o histórico real do
    aluno, ignorando o evento que originou a chamada. Usado para
    retroatividade — aluno que já tinha 100 questões respondidas antes
    do sistema de conquistas existir não precisa refazer nada."""
    todas_condicoes = tuple(MEDIDORES.keys())
    pendentes = _buscar_conquistas_pendentes(usuario_id, todas_condicoes)

    desbloqueadas = []
    for conquista in pendentes:
        medidor = MEDIDORES.get(conquista["tipo_condicao"])
        if medidor is None:
            continue

        valor_atual = medidor(usuario_id, conquista)
        if valor_atual >= conquista["valor_condicao"]:
            if desbloquear_conquista(usuario_id, conquista):
                desbloqueadas.append(conquista["id"])

    return desbloqueadas


def recalcular_conquistas_todos_alunos() -> dict[str, list[str]]:
    """Não é chamado automaticamente em lugar nenhum — utilitário para
    rodar manualmente (script/console) quando uma conquista nova for
    adicionada e precisar avaliar a base inteira de alunos existente."""
    usuarios = (
        supabase_admin.table("perfis").select("id").execute().data or []
    )

    resultado = {}
    for usuario in usuarios:
        desbloqueadas = recalcular_conquistas_aluno(usuario["id"])
        if desbloqueadas:
            resultado[usuario["id"]] = desbloqueadas

    return resultado
