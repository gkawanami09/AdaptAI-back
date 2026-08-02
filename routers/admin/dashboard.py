from fastapi import APIRouter, HTTPException, Depends, Query
from database import supabase_admin
from datetime import datetime, timedelta, timezone
from uuid import uuid4
from utils.autenticacao import exigir_administrador

router = APIRouter(
    prefix='/admin/dashboard',
    tags=['Admin - Dashboard'],
    dependencies=[Depends(exigir_administrador)]
)

PERIODO_DIAS = {
    "7d": 7,
    "30d": 30,
    "90d": 90,
    "12m": 365,
}

PERIODO_AGRUPAMENTO = {
    "7d": "diario",
    "30d": "diario",
    "90d": "semanal",
    "12m": "mensal",
}


# Calculates the interval (start_date, end_date, previous_start_date) for the given period
def calcular_intervalo(periodo: str):
    dias = PERIODO_DIAS.get(periodo, 30)
    agora = datetime.now(timezone.utc)
    inicio = agora - timedelta(days=dias)
    inicio_anterior = inicio - timedelta(days=dias)
    return inicio, agora, inicio_anterior


@router.get('')
def obter_dashboard(
    periodo: str = Query(default="30d"),
):
    try:
        if periodo not in PERIODO_DIAS:
            raise HTTPException(
                status_code=400,
                detail="Período inválido"
            )

        inicio, agora, inicio_anterior = calcular_intervalo(periodo)
        agrupamento = PERIODO_AGRUPAMENTO[periodo]

        # TODO: user, answer and exam KPIs depend on user/answer/streak tables that don't exist yet
        kpis = {
            "total_usuarios": 0,
            "total_usuarios_variacao_pct": 0,
            "questoes_respondidas": 0,
            "questoes_respondidas_variacao_pct": 0,
            "provas_realizadas": 0,
            "provas_realizadas_variacao_pct": 0,
            "ofensiva_media_dias": 0,
            "ofensiva_media_variacao_dias": 0,
        }

        # Crescimento: questões criadas por período (proxy até tabelas de resposta existirem)
        questoes_periodo = (
            supabase_admin.table("questoes")
            .select("criado_em")
            .gte("criado_em", inicio.isoformat())
            .execute()
            .data or []
        )

        listas_periodo = (
            supabase_admin.table("listas_questoes")
            .select("criado_em")
            .gte("criado_em", inicio.isoformat())
            .execute()
            .data or []
        )

        # Chooses the bucket key for a timestamp according to the aggregation granularity
        def chave_bucket(data_iso: str) -> str:
            data = datetime.fromisoformat(data_iso.replace("Z", "+00:00"))
            if agrupamento == "diario":
                return data.strftime("%Y-%m-%d")
            if agrupamento == "semanal":
                inicio_semana = data - timedelta(days=data.weekday())
                return inicio_semana.strftime("%Y-%m-%d")
            return data.strftime("%Y-%m-01")

        buckets: dict[str, dict[str, int]] = {}

        for questao in questoes_periodo:
            chave = chave_bucket(questao["criado_em"])
            buckets.setdefault(chave, {"usuarios": 0, "questoes_respondidas": 0, "listas_concluidas": 0, "provas_realizadas": 0})
            buckets[chave]["questoes_respondidas"] += 1

        for lista in listas_periodo:
            chave = chave_bucket(lista["criado_em"])
            buckets.setdefault(chave, {"usuarios": 0, "questoes_respondidas": 0, "listas_concluidas": 0, "provas_realizadas": 0})
            buckets[chave]["listas_concluidas"] += 1

        crescimento = [
            {
                "data": datetime.fromisoformat(chave).strftime("%d/%m"),
                "usuarios": valores["usuarios"],
                "questoes_respondidas": valores["questoes_respondidas"],
                "listas_concluidas": valores["listas_concluidas"],
                "provas_realizadas": valores["provas_realizadas"],
            }
            for chave, valores in sorted(buckets.items())
        ]

        # Atividade do dia
        inicio_hoje = agora.replace(hour=0, minute=0, second=0, microsecond=0)

        questoes_hoje = (
            supabase_admin.table("questoes")
            .select("id", count="exact")
            .gte("criado_em", inicio_hoje.isoformat())
            .execute()
        )

        # TODO: usuarios_online, novos_cadastros, provas_iniciadas e tempo_medio_estudo_min dependem de tabelas que não existem ainda
        atividade_hoje = {
            "usuarios_online": 0,
            "questoes_respondidas": questoes_hoje.count or 0,
            "novos_cadastros": 0,
            "provas_iniciadas": 0,
            "tempo_medio_estudo_min": 0,
        }

        # Atividades recentes
        atividades_recentes = []

        materias_recentes = (
            supabase_admin.table("materias")
            .select("id, nome, criado_em")
            .order("criado_em", desc=True)
            .limit(10)
            .execute()
            .data or []
        )

        for materia in materias_recentes:
            atividades_recentes.append({
                "id": materia["id"],
                "tipo": "materia_criada",
                "titulo": "Nova matéria criada",
                "descricao": materia["nome"],
                "criado_em": materia["criado_em"],
            })

        listas_recentes = (
            supabase_admin.table("listas_questoes")
            .select("id, titulo, criado_em")
            .order("criado_em", desc=True)
            .limit(10)
            .execute()
            .data or []
        )

        for lista in listas_recentes:
            atividades_recentes.append({
                "id": lista["id"],
                "tipo": "lista_publicada",
                "titulo": "Lista publicada",
                "descricao": lista["titulo"],
                "criado_em": lista["criado_em"],
            })

        atividades_recentes = sorted(
            atividades_recentes,
            key=lambda atividade: atividade["criado_em"],
            reverse=True,
        )[:10]

        # Resumo de conteúdo
        materias_total = supabase_admin.table("materias").select("id", count="exact").execute()
        topicos_total = supabase_admin.table("topicos").select("topico_id", count="exact").execute()
        aulas_total = supabase_admin.table("aulas").select("id", count="exact").execute()
        questoes_total = supabase_admin.table("questoes").select("id", count="exact").execute()
        listas_total = supabase_admin.table("listas_questoes").select("id", count="exact").execute()
        provas_total = supabase_admin.table("tipos_prova").select("id", count="exact").execute()

        conteudo = {
            "questoes": questoes_total.count or 0,
            "aulas": aulas_total.count or 0,
            "topicos": topicos_total.count or 0,
            "materias": materias_total.count or 0,
            "provas": provas_total.count or 0,
            "listas": listas_total.count or 0,
        }

        # Alertas
        alertas = []

        todas_aulas = (
            supabase_admin.table("aulas")
            .select("id")
            .execute()
            .data or []
        )

        conteudos_aulas = (
            supabase_admin.table("aulas_conteudo")
            .select("aula_id")
            .execute()
            .data or []
        )

        ids_aulas_com_conteudo = {conteudo["aula_id"] for conteudo in conteudos_aulas}
        total_aulas_sem_conteudo = sum(1 for aula in todas_aulas if aula["id"] not in ids_aulas_com_conteudo)

        if total_aulas_sem_conteudo > 0:
            alertas.append({
                "id": str(uuid4()),
                "tipo": "aulas_sem_conteudo",
                "severidade": "media",
                "descricao": f"{total_aulas_sem_conteudo} aulas sem conteúdo",
                "detalhe": None,
                "link": "/admin/aulas",
            })

        tipos_prova_lista = (
            supabase_admin.table("tipos_prova")
            .select("id")
            .execute()
            .data or []
        )

        questoes_tipo_prova = (
            supabase_admin.table("questoes")
            .select("tipo_prova_id")
            .execute()
            .data or []
        )

        ids_com_questoes = {questao["tipo_prova_id"] for questao in questoes_tipo_prova if questao["tipo_prova_id"]}
        provas_sem_questoes = [tipo for tipo in tipos_prova_lista if tipo["id"] not in ids_com_questoes]

        if provas_sem_questoes:
            alertas.append({
                "id": str(uuid4()),
                "tipo": "provas_sem_questoes",
                "severidade": "media",
                "descricao": f"{len(provas_sem_questoes)} provas sem questões",
                "detalhe": None,
                "link": "/admin/tipos-prova",
            })

        # TODO: storage, usuarios_denunciados e integracoes_desconectadas dependem de tabelas/serviços que não existem ainda

        return {
            "sucesso": True,
            "kpis": kpis,
            "crescimento": crescimento,
            "atividade_hoje": atividade_hoje,
            "atividades_recentes": atividades_recentes,
            "conteudo": conteudo,
            "alertas": alertas,
        }

    except HTTPException:
        raise

    except Exception as erro:
        print(f"Erro ao obter dashboard: {erro}")
        raise HTTPException(
            status_code=500,
            detail="Erro ao obter dashboard"
        )
