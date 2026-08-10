from datetime import date, datetime, timedelta, timezone

from database import supabase_admin

CONTADORES_ATIVIDADE_DIARIA = (
    "aulas_concluidas",
    "tarefas_concluidas",
    "questoes_respondidas",
    "respostas_corretas",
    "redacoes_enviadas",
    "simulados_concluidos",
)


def _registrar_atividade_diaria(usuario_id: str, agora: datetime, xp: int, minutos_estudo: int, contadores: dict) -> None:
    hoje = agora.date().isoformat()

    campos_select = "id, minutos_estudo, xp_ganho, " + ", ".join(CONTADORES_ATIVIDADE_DIARIA)
    atividade_hoje = (
        supabase_admin.table("atividade_diaria")
        .select(campos_select)
        .eq("usuario_id", usuario_id)
        .eq("data_atividade", hoje)
        .limit(1)
        .execute()
    )

    if atividade_hoje.data:
        registro = atividade_hoje.data[0]
        atualizacao = {
            "minutos_estudo": registro["minutos_estudo"] + minutos_estudo,
            "xp_ganho": registro["xp_ganho"] + xp,
            "atualizado_em": agora.isoformat(),
        }
        for campo in CONTADORES_ATIVIDADE_DIARIA:
            atualizacao[campo] = registro[campo] + contadores.get(campo, 0)

        supabase_admin.table("atividade_diaria").update(atualizacao).eq("id", registro["id"]).execute()
    else:
        insercao = {
            "usuario_id": usuario_id,
            "data_atividade": hoje,
            "minutos_estudo": minutos_estudo,
            "xp_ganho": xp,
        }
        for campo in CONTADORES_ATIVIDADE_DIARIA:
            insercao[campo] = contadores.get(campo, 0)

        supabase_admin.table("atividade_diaria").insert(insercao).execute()


def _atualizar_ofensiva_e_xp_total(usuario_id: str, agora: datetime, xp: int, minutos_estudo: int) -> None:
    estatisticas = (
        supabase_admin.table("estatisticas_usuario")
        .select("usuario_id, xp_total, ofensiva_atual_dias, maior_ofensiva_dias, ultima_atividade_data, minutos_estudo_total")
        .eq("usuario_id", usuario_id)
        .limit(1)
        .execute()
    )

    hoje_data = agora.date()

    if estatisticas.data:
        registro = estatisticas.data[0]
        ultima_data = date.fromisoformat(registro["ultima_atividade_data"]) if registro["ultima_atividade_data"] else None

        if minutos_estudo <= 0:
            nova_ofensiva = registro["ofensiva_atual_dias"]
        elif ultima_data == hoje_data:
            nova_ofensiva = registro["ofensiva_atual_dias"]
        elif ultima_data == hoje_data - timedelta(days=1):
            nova_ofensiva = registro["ofensiva_atual_dias"] + 1
        else:
            nova_ofensiva = 1

        supabase_admin.table("estatisticas_usuario").update({
            "xp_total": registro["xp_total"] + xp,
            "ofensiva_atual_dias": nova_ofensiva,
            "maior_ofensiva_dias": max(nova_ofensiva, registro["maior_ofensiva_dias"]),
            "ultima_atividade_data": hoje_data.isoformat() if minutos_estudo > 0 else registro["ultima_atividade_data"],
            "minutos_estudo_total": registro["minutos_estudo_total"] + minutos_estudo,
            "atualizado_em": agora.isoformat(),
        }).eq("usuario_id", usuario_id).execute()
    else:
        supabase_admin.table("estatisticas_usuario").insert({
            "usuario_id": usuario_id,
            "xp_total": xp,
            "ofensiva_atual_dias": 1 if minutos_estudo > 0 else 0,
            "maior_ofensiva_dias": 1 if minutos_estudo > 0 else 0,
            "ultima_atividade_data": hoje_data.isoformat() if minutos_estudo > 0 else None,
            "minutos_estudo_total": minutos_estudo,
        }).execute()


def conceder_xp_e_atividade(
    usuario_id: str,
    xp: int,
    minutos_estudo: int = 0,
    agora: datetime | None = None,
    **contadores: int,
) -> None:
    """Único ponto do sistema que concede XP, atualiza `atividade_diaria`
    e recalcula a ofensiva (`estatisticas_usuario`). Reaproveitado por
    qualquer ação que gere XP — concluir aula, concluir tarefa do plano
    de estudos, desbloquear conquista, completar missão — em vez de cada
    fluxo reimplementar a mesma lógica de streak.

    `minutos_estudo > 0` é o que conta como "estudou hoje" para fins de
    ofensiva; XP concedido sem minutos de estudo (ex.: recompensa de
    conquista) não mexe na ofensiva, só no total de XP.
    """
    agora = agora or datetime.now(timezone.utc)

    if xp <= 0 and minutos_estudo <= 0 and not contadores:
        return

    _registrar_atividade_diaria(usuario_id, agora, xp, minutos_estudo, contadores)
    _atualizar_ofensiva_e_xp_total(usuario_id, agora, xp, minutos_estudo)


def conceder_xp(usuario_id: str, xp: int, agora: datetime | None = None) -> None:
    """Atalho para conceder XP puro (sem contar como estudo do dia) —
    usado por recompensas de conquistas e missões."""
    conceder_xp_e_atividade(usuario_id, xp, minutos_estudo=0, agora=agora)
