from fastapi import APIRouter, HTTPException, Depends
from database import supabase_admin
from datetime import datetime, timedelta, timezone
from utils.autenticacao import pegar_usuario_atual
from schemas.conquistas_schema import ConquistasResponse

router = APIRouter(
    prefix='/aluno/conquistas',
    tags=['Aluno - Conquistas']
)

XP_POR_NIVEL = 1000


def calcular_nivel(xp_total: int):
    nivel_atual = (xp_total // XP_POR_NIVEL) + 1
    xp_proximo_nivel = nivel_atual * XP_POR_NIVEL
    return nivel_atual, xp_proximo_nivel


def montar_resumo(usuario_id: str):
    estatisticas = (
        supabase_admin.table("estatisticas_usuario")
        .select("xp_total, ofensiva_atual_dias")
        .eq("usuario_id", usuario_id)
        .limit(1)
        .execute()
        .data
    )

    xp_total = estatisticas[0]["xp_total"] if estatisticas else 0
    ofensiva_dias = estatisticas[0]["ofensiva_atual_dias"] if estatisticas else 0

    nivel_atual, xp_proximo_nivel = calcular_nivel(xp_total)

    return xp_total, ofensiva_dias, nivel_atual, xp_proximo_nivel


def montar_conquistas(usuario_id: str):
    conquistas = (
        supabase_admin.table("conquistas")
        .select("id, titulo, descricao, icone, raridade, xp_recompensa")
        .eq("ativo", True)
        .execute()
        .data or []
    )

    if not conquistas:
        return [], []

    desbloqueadas_banco = (
        supabase_admin.table("conquistas_usuario")
        .select("conquista_id")
        .eq("usuario_id", usuario_id)
        .execute()
        .data or []
    )
    ids_desbloqueadas = {c["conquista_id"] for c in desbloqueadas_banco}

    desbloqueadas = []
    bloqueadas = []

    for conquista in conquistas:
        icone = conquista.get("icone") or "🏆"
        descricao = conquista.get("descricao") or ""

        if conquista["id"] in ids_desbloqueadas:
            desbloqueadas.append({
                "icone": icone,
                "titulo": conquista["titulo"],
                "descricao": descricao,
                "raridade": conquista["raridade"],
                "xp": conquista["xp_recompensa"],
            })
        else:
            bloqueadas.append({
                "icone": icone,
                "titulo": conquista["titulo"],
                "descricao": descricao,
                "raridade": conquista["raridade"],
            })

    return desbloqueadas, bloqueadas


def montar_missoes_diarias(usuario_id: str, hoje):
    missoes = (
        supabase_admin.table("missoes")
        .select("id, titulo, metrica, valor_alvo, xp_recompensa")
        .eq("ativo", True)
        .eq("tipo_missao", "diaria")
        .execute()
        .data or []
    )

    if not missoes:
        return []

    ids_missoes = [m["id"] for m in missoes]
    progresso_banco = (
        supabase_admin.table("progresso_missoes_usuario")
        .select("missao_id, valor_atual, concluido_em")
        .eq("usuario_id", usuario_id)
        .eq("periodo_inicio", hoje.isoformat())
        .in_("missao_id", ids_missoes)
        .execute()
        .data or []
    )
    progresso_por_missao = {p["missao_id"]: p for p in progresso_banco}

    missoes_diarias = []
    for missao in missoes:
        progresso = progresso_por_missao.get(missao["id"])
        valor_atual = progresso["valor_atual"] if progresso else 0
        completed = bool(progresso and progresso["concluido_em"]) or valor_atual >= missao["valor_alvo"]

        missoes_diarias.append({
            "label": missao["titulo"],
            "xp": missao["xp_recompensa"],
            "completed": completed,
        })

    return missoes_diarias


def montar_missoes_semanais(usuario_id: str, inicio_semana, fim_semana):
    missoes = (
        supabase_admin.table("missoes")
        .select("id, titulo, metrica, valor_alvo, xp_recompensa")
        .eq("ativo", True)
        .eq("tipo_missao", "semanal")
        .execute()
        .data or []
    )

    if not missoes:
        return []

    ids_missoes = [m["id"] for m in missoes]
    progresso_banco = (
        supabase_admin.table("progresso_missoes_usuario")
        .select("missao_id, valor_atual")
        .eq("usuario_id", usuario_id)
        .eq("periodo_inicio", inicio_semana.isoformat())
        .eq("periodo_fim", fim_semana.isoformat())
        .in_("missao_id", ids_missoes)
        .execute()
        .data or []
    )
    progresso_por_missao = {p["missao_id"]: p for p in progresso_banco}

    missoes_semanais = []
    for missao in missoes:
        progresso = progresso_por_missao.get(missao["id"])
        valor_atual = progresso["valor_atual"] if progresso else 0

        missoes_semanais.append({
            "label": missao["titulo"],
            "xp": missao["xp_recompensa"],
            "current": min(valor_atual, missao["valor_alvo"]),
            "target": missao["valor_alvo"],
        })

    return missoes_semanais


@router.get('', response_model=ConquistasResponse)
def obter_conquistas(usuario_atual=Depends(pegar_usuario_atual)):
    try:
        id_usuario = str(usuario_atual.id)
        hoje = datetime.now(timezone.utc).date()
        inicio_semana = hoje - timedelta(days=hoje.weekday())
        fim_semana = inicio_semana + timedelta(days=6)

        xp_total, ofensiva_dias, nivel_atual, xp_proximo_nivel = montar_resumo(id_usuario)
        desbloqueadas, bloqueadas = montar_conquistas(id_usuario)
        missoes_diarias = montar_missoes_diarias(id_usuario, hoje)
        missoes_semanais = montar_missoes_semanais(id_usuario, inicio_semana, fim_semana)

        total_medalhas = len(desbloqueadas)
        total_conquistas = total_medalhas + len(bloqueadas)
        subtitulo = f"{total_medalhas} de {total_conquistas} conquistas encontradas"

        return {
            "subtitulo": subtitulo,
            "ofensiva_dias": ofensiva_dias,
            "xp_total": xp_total,
            "nivel_atual": nivel_atual,
            "xp_proximo_nivel": xp_proximo_nivel,
            "total_medalhas": total_medalhas,
            "conquistas_desbloqueadas": desbloqueadas,
            "conquistas_bloqueadas": bloqueadas,
            "missoes_diarias": missoes_diarias,
            "missoes_semanais": missoes_semanais,
        }

    except Exception as erro:
        print(f"Erro ao obter conquistas do aluno: {erro}")

        raise HTTPException(
            status_code=500,
            detail="Erro ao obter conquistas do aluno"
        )
