from fastapi import APIRouter, HTTPException, Depends
from database import supabase_admin
from datetime import date, datetime, timedelta, timezone
from utils.autenticacao import pegar_usuario_atual
from schemas.progresso_schema import ProgressoResponse

router = APIRouter(
    prefix='/aluno/progresso',
    tags=['Aluno - Meu Progresso']
)

DIAS_SEMANA = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sab", "Dom"]
WEEKDAY_LABELS = ["D", "S", "T", "Q", "Q", "S", "S"]
CORES_SERIE_EVOLUCAO = ["blue", "green", "red"]
CORES_RANKING = ["purple", "teal", "gold", "red", "blue", "green", "orange"]
SEMANAS_HEATMAP = 5


def formatar_horas(minutos: int) -> str:
    horas = minutos // 60
    return f"{horas}h"


def montar_resumo(usuario_id: str, hoje: date):
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

    inicio_mes = hoje.replace(day=1)

    atividades_mes = (
        supabase_admin.table("atividade_diaria")
        .select("minutos_estudo, questoes_respondidas, simulados_concluidos")
        .eq("usuario_id", usuario_id)
        .gte("data_atividade", inicio_mes.isoformat())
        .lte("data_atividade", hoje.isoformat())
        .execute()
        .data or []
    )

    minutos_estudados_mes = sum(a["minutos_estudo"] for a in atividades_mes)
    questoes_respondidas_mes = sum(a["questoes_respondidas"] for a in atividades_mes)
    simulados_mes = sum(a["simulados_concluidos"] for a in atividades_mes)

    meta = (
        supabase_admin.table("metas_mensais_usuario")
        .select("meta_questoes, meta_minutos_estudo, meta_simulados")
        .eq("usuario_id", usuario_id)
        .eq("inicio_mes", inicio_mes.isoformat())
        .limit(1)
        .execute()
        .data
    )

    meta_mensal_percentual = 0
    if meta:
        percentuais = []
        if meta[0]["meta_questoes"]:
            percentuais.append(min(100, round((questoes_respondidas_mes / meta[0]["meta_questoes"]) * 100)))
        if meta[0]["meta_minutos_estudo"]:
            percentuais.append(min(100, round((minutos_estudados_mes / meta[0]["meta_minutos_estudo"]) * 100)))
        if meta[0]["meta_simulados"]:
            percentuais.append(min(100, round((simulados_mes / meta[0]["meta_simulados"]) * 100)))
        meta_mensal_percentual = round(sum(percentuais) / len(percentuais)) if percentuais else 0

    return {
        "meta_mensal_percentual": meta_mensal_percentual,
        "horas_estudadas": formatar_horas(minutos_estudados_mes),
        "ofensiva_dias": ofensiva_dias,
        "xp_total": xp_total,
    }


def montar_evolucao_acertos(usuario_id: str, hoje: date):
    inicio_mes = hoje.replace(day=1)

    tentativas = (
        supabase_admin.table("tentativas_questoes")
        .select("questao_id, acertou, respondido_em, questoes!inner(materia_id)")
        .eq("usuario_id", usuario_id)
        .gte("respondido_em", inicio_mes.isoformat())
        .execute()
        .data or []
    )

    if not tentativas:
        return {"categories": [], "series": []}

    def numero_semana_do_mes(data_str: str) -> int:
        data_resposta = datetime.fromisoformat(data_str.replace("Z", "+00:00")).date()
        return ((data_resposta.day - 1) // 7) + 1

    semanas_presentes = sorted({numero_semana_do_mes(t["respondido_em"]) for t in tentativas})
    categories = [f"Sem {n}" for n in semanas_presentes]

    materias_ids = {t["questoes"]["materia_id"] for t in tentativas}
    materias_banco = (
        supabase_admin.table("materias")
        .select("id, nome")
        .in_("id", list(materias_ids))
        .execute()
        .data or []
    )
    materias_por_id = {m["id"]: m["nome"] for m in materias_banco}

    dados_por_materia: dict[str, dict[int, dict[str, int]]] = {}
    for tentativa in tentativas:
        materia_id = tentativa["questoes"]["materia_id"]
        semana = numero_semana_do_mes(tentativa["respondido_em"])

        dados_por_materia.setdefault(materia_id, {})
        dados_por_materia[materia_id].setdefault(semana, {"total": 0, "acertos": 0})
        dados_por_materia[materia_id][semana]["total"] += 1
        if tentativa["acertou"]:
            dados_por_materia[materia_id][semana]["acertos"] += 1

    series = []
    for indice, (materia_id, semanas) in enumerate(dados_por_materia.items()):
        values = []
        for semana in semanas_presentes:
            dados_semana = semanas.get(semana)
            if dados_semana and dados_semana["total"] > 0:
                values.append(round((dados_semana["acertos"] / dados_semana["total"]) * 100))
            else:
                values.append(0)

        series.append({
            "name": materias_por_id.get(materia_id, "Matéria"),
            "color": CORES_SERIE_EVOLUCAO[indice % len(CORES_SERIE_EVOLUCAO)],
            "values": values,
        })

    return {"categories": categories, "series": series}


def montar_horas_por_dia(usuario_id: str, hoje: date):
    inicio_semana = hoje - timedelta(days=hoje.weekday())
    fim_semana = inicio_semana + timedelta(days=6)

    atividades = (
        supabase_admin.table("atividade_diaria")
        .select("data_atividade, minutos_estudo")
        .eq("usuario_id", usuario_id)
        .gte("data_atividade", inicio_semana.isoformat())
        .lte("data_atividade", fim_semana.isoformat())
        .execute()
        .data or []
    )

    minutos_por_data = {a["data_atividade"]: a["minutos_estudo"] for a in atividades}

    horas_por_dia = []
    for indice in range(7):
        dia = inicio_semana + timedelta(days=indice)
        minutos = minutos_por_data.get(dia.isoformat(), 0)
        horas_por_dia.append({
            "label": DIAS_SEMANA[indice],
            "value": round(minutos / 60, 1),
        })

    return horas_por_dia


def montar_ranking_materias(usuario_id: str):
    tentativas = (
        supabase_admin.table("tentativas_questoes")
        .select("acertou, questoes!inner(materia_id)")
        .eq("usuario_id", usuario_id)
        .execute()
        .data or []
    )

    if not tentativas:
        return []

    total_por_materia: dict[str, int] = {}
    acertos_por_materia: dict[str, int] = {}
    for tentativa in tentativas:
        materia_id = tentativa["questoes"]["materia_id"]
        total_por_materia[materia_id] = total_por_materia.get(materia_id, 0) + 1
        if tentativa["acertou"]:
            acertos_por_materia[materia_id] = acertos_por_materia.get(materia_id, 0) + 1

    materias_banco = (
        supabase_admin.table("materias")
        .select("id, nome")
        .in_("id", list(total_por_materia.keys()))
        .execute()
        .data or []
    )
    materias_por_id = {m["id"]: m["nome"] for m in materias_banco}

    ranking = []
    for materia_id, total in total_por_materia.items():
        acertos = acertos_por_materia.get(materia_id, 0)
        percentual = round((acertos / total) * 100)
        ranking.append({
            "label": materias_por_id.get(materia_id, "Matéria"),
            "percent": percentual,
        })

    ranking.sort(key=lambda item: item["percent"], reverse=True)

    for indice, item in enumerate(ranking):
        item["color"] = CORES_RANKING[indice % len(CORES_RANKING)]

    return ranking


def montar_heatmap(usuario_id: str, hoje: date):
    fim_semana_atual = hoje + timedelta(days=(6 - hoje.weekday()) % 7)
    inicio_semana_atual = fim_semana_atual - timedelta(days=6)
    inicio_periodo = inicio_semana_atual - timedelta(weeks=SEMANAS_HEATMAP - 1)

    atividades = (
        supabase_admin.table("atividade_diaria")
        .select("data_atividade, minutos_estudo")
        .eq("usuario_id", usuario_id)
        .gte("data_atividade", inicio_periodo.isoformat())
        .lte("data_atividade", fim_semana_atual.isoformat())
        .execute()
        .data or []
    )

    minutos_por_data = {a["data_atividade"]: a["minutos_estudo"] for a in atividades}

    def nivel_por_minutos(minutos: int) -> int:
        if minutos <= 0:
            return 0
        if minutos < 30:
            return 1
        if minutos < 60:
            return 2
        if minutos < 120:
            return 3
        return 4

    weeks = []
    for semana_indice in range(SEMANAS_HEATMAP):
        inicio_semana = inicio_periodo + timedelta(weeks=semana_indice)
        linha = []
        for dia_indice in range(7):
            dia = inicio_semana + timedelta(days=dia_indice)
            minutos = minutos_por_data.get(dia.isoformat(), 0)
            linha.append(nivel_por_minutos(minutos))
        weeks.append(linha)

    return {
        "weekday_labels": WEEKDAY_LABELS,
        "weeks": weeks,
    }


def montar_metas_mensais(usuario_id: str, hoje: date):
    inicio_mes = hoje.replace(day=1)

    meta = (
        supabase_admin.table("metas_mensais_usuario")
        .select("meta_questoes, meta_minutos_estudo, meta_simulados")
        .eq("usuario_id", usuario_id)
        .eq("inicio_mes", inicio_mes.isoformat())
        .limit(1)
        .execute()
        .data
    )

    if not meta:
        return []

    atividades_mes = (
        supabase_admin.table("atividade_diaria")
        .select("minutos_estudo, questoes_respondidas, simulados_concluidos")
        .eq("usuario_id", usuario_id)
        .gte("data_atividade", inicio_mes.isoformat())
        .lte("data_atividade", hoje.isoformat())
        .execute()
        .data or []
    )

    questoes_respondidas_mes = sum(a["questoes_respondidas"] for a in atividades_mes)
    minutos_estudados_mes = sum(a["minutos_estudo"] for a in atividades_mes)
    simulados_mes = sum(a["simulados_concluidos"] for a in atividades_mes)

    metas_mensais = []

    if meta[0]["meta_questoes"]:
        metas_mensais.append({
            "label": "Questões resolvidas",
            "value": questoes_respondidas_mes,
            "target": meta[0]["meta_questoes"],
            "color": "purple",
        })

    if meta[0]["meta_minutos_estudo"]:
        metas_mensais.append({
            "label": "Horas de estudo",
            "value": round(minutos_estudados_mes / 60),
            "target": round(meta[0]["meta_minutos_estudo"] / 60),
            "color": "blue",
        })

    if meta[0]["meta_simulados"]:
        metas_mensais.append({
            "label": "Simulados feitos",
            "value": simulados_mes,
            "target": meta[0]["meta_simulados"],
            "color": "teal",
        })

    return metas_mensais


@router.get('', response_model=ProgressoResponse)
def obter_progresso(usuario_atual=Depends(pegar_usuario_atual)):
    try:
        id_usuario = str(usuario_atual.id)
        hoje = datetime.now(timezone.utc).date()

        return {
            "resumo": montar_resumo(id_usuario, hoje),
            "evolucao_acertos": montar_evolucao_acertos(id_usuario, hoje),
            "horas_por_dia": montar_horas_por_dia(id_usuario, hoje),
            "ranking_materias": montar_ranking_materias(id_usuario),
            "heatmap": montar_heatmap(id_usuario, hoje),
            "metas_mensais": montar_metas_mensais(id_usuario, hoje),
        }

    except Exception as erro:
        print(f"Erro ao obter progresso do aluno: {erro}")

        raise HTTPException(
            status_code=500,
            detail="Erro ao obter progresso do aluno"
        )
