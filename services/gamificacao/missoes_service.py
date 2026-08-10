from datetime import date, datetime, timedelta, timezone

from postgrest.exceptions import APIError

from database import supabase_admin
from services.gamificacao.eventos import EventoGamificacao
from services.gamificacao.xp_service import conceder_xp

UNIQUE_VIOLATION = "23505"

# Métrica de missão que cada evento incrementa. "minutos_estudo" usa a
# quantidade real vinda em `dados["minutos"]`; os demais incrementam 1.
EVENTO_PARA_METRICA: dict[EventoGamificacao, str] = {
    EventoGamificacao.QUESTAO_RESPONDIDA: "questoes_respondidas",
    EventoGamificacao.AULA_CONCLUIDA: "aulas_concluidas",
    EventoGamificacao.SESSAO_ESTUDO_CONCLUIDA: "minutos_estudo",
    EventoGamificacao.REDACAO_ENVIADA: "redacoes_enviadas",
    EventoGamificacao.SIMULADO_CONCLUIDO: "simulados_concluidos",
}


def _periodo_para(tipo_missao: str, hoje: date) -> tuple[date, date]:
    if tipo_missao == "diaria":
        return hoje, hoje

    inicio_semana = hoje - timedelta(days=hoje.weekday())
    fim_semana = inicio_semana + timedelta(days=6)
    return inicio_semana, fim_semana


def _incrementar_progresso(usuario_id: str, missao: dict, periodo_inicio: date, periodo_fim: date, incremento: int, agora: datetime) -> dict:
    existente = (
        supabase_admin.table("progresso_missoes_usuario")
        .select("id, valor_atual, concluido_em")
        .eq("usuario_id", usuario_id)
        .eq("missao_id", missao["id"])
        .eq("periodo_inicio", periodo_inicio.isoformat())
        .eq("periodo_fim", periodo_fim.isoformat())
        .limit(1)
        .execute()
        .data
    )

    if existente:
        registro = existente[0]
        novo_valor = registro["valor_atual"] + incremento
        atualizacao = {"valor_atual": novo_valor, "atualizado_em": agora.isoformat()}

        ja_concluida = bool(registro["concluido_em"])
        if not ja_concluida and novo_valor >= missao["valor_alvo"]:
            atualizacao["concluido_em"] = agora.isoformat()

        supabase_admin.table("progresso_missoes_usuario").update(atualizacao).eq("id", registro["id"]).execute()

        return {
            "valor_atual": novo_valor,
            "recem_concluida": not ja_concluida and novo_valor >= missao["valor_alvo"],
        }

    novo_valor = incremento
    concluida_agora = novo_valor >= missao["valor_alvo"]

    try:
        supabase_admin.table("progresso_missoes_usuario").insert({
            "usuario_id": usuario_id,
            "missao_id": missao["id"],
            "periodo_inicio": periodo_inicio.isoformat(),
            "periodo_fim": periodo_fim.isoformat(),
            "valor_atual": novo_valor,
            "concluido_em": agora.isoformat() if concluida_agora else None,
        }).execute()
    except APIError as erro:
        if erro.code == UNIQUE_VIOLATION:
            # Corrida: outra requisição criou o progresso primeiro nesse
            # instante — tenta de novo, agora vai cair no caminho de update.
            return _incrementar_progresso(usuario_id, missao, periodo_inicio, periodo_fim, incremento, agora)
        raise

    return {"valor_atual": novo_valor, "recem_concluida": concluida_agora}


def atualizar_missoes(usuario_id: str, evento: EventoGamificacao, dados: dict | None = None) -> None:
    metrica = EVENTO_PARA_METRICA.get(evento)
    if not metrica:
        return

    dados = dados or {}
    incremento = dados.get("minutos", 1) if metrica == "minutos_estudo" else 1
    if incremento <= 0:
        return

    agora = datetime.now(timezone.utc)
    hoje = agora.date()

    missoes = (
        supabase_admin.table("missoes")
        .select("id, tipo_missao, valor_alvo, xp_recompensa")
        .eq("ativo", True)
        .eq("metrica", metrica)
        .execute()
        .data or []
    )

    for missao in missoes:
        periodo_inicio, periodo_fim = _periodo_para(missao["tipo_missao"], hoje)
        resultado = _incrementar_progresso(usuario_id, missao, periodo_inicio, periodo_fim, incremento, agora)

        if resultado["recem_concluida"] and missao["xp_recompensa"] > 0:
            conceder_xp(usuario_id, missao["xp_recompensa"], agora=agora)
