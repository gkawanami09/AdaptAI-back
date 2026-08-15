from fastapi import APIRouter, HTTPException, Depends
from database import supabase_admin
from datetime import datetime, timedelta, timezone
from uuid import uuid4
from utils.autenticacao import pegar_usuario_atual
from schemas.dashboard_schema import AlunoDashboardResponse

router = APIRouter(
    prefix='/aluno/dashboard',
    tags=['Aluno - Dashboard']
)

DIAS_SEMANA = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]

TIPO_TAREFA_PARA_TIPO_CONTRATO = {
    "aula": "aula",
    "questoes": "questoes",
    "simulado": "prova",
    "redacao": "redacao",
    "revisao": "revisao",
    "personalizada": "revisao",
}


@router.get('', response_model=AlunoDashboardResponse)
def obter_dashboard(usuario_atual=Depends(pegar_usuario_atual)):
    try:
        id_usuario = str(usuario_atual.id)

        perfil = (
            supabase_admin
            .table("perfis")
            .select("id")
            .eq("id", id_usuario)
            .limit(1)
            .execute()
        )

        if not perfil.data:
            raise HTTPException(
                status_code=404,
                detail="Perfil não encontrado."
            )

        hoje = datetime.now(timezone.utc).date()
        inicio_semana = hoje - timedelta(days=hoje.weekday())
        fim_semana = inicio_semana + timedelta(days=6)

        estatisticas = (
            supabase_admin
            .table("estatisticas_usuario")
            .select("ofensiva_atual_dias")
            .eq("usuario_id", id_usuario)
            .limit(1)
            .execute()
        )

        ofensiva_dias = estatisticas.data[0]["ofensiva_atual_dias"] if estatisticas.data else 0

        atividades_semana = (
            supabase_admin
            .table("atividade_diaria")
            .select("data_atividade, minutos_estudo, xp_ganho, tarefas_concluidas, questoes_respondidas, respostas_corretas")
            .eq("usuario_id", id_usuario)
            .gte("data_atividade", inicio_semana.isoformat())
            .lte("data_atividade", fim_semana.isoformat())
            .execute()
            .data or []
        )

        atividades_por_data = {atividade["data_atividade"]: atividade for atividade in atividades_semana}

        tempo_estudado_min = sum(atividade["minutos_estudo"] for atividade in atividades_semana)
        xp_semana = sum(atividade["xp_ganho"] for atividade in atividades_semana)

        # resumo.tarefas_totais/tarefas_concluidas precisam refletir o mesmo
        # conjunto de tarefas de "hoje" que popula plano_do_dia abaixo — a
        # mesma data de referência e o mesmo usuario_id em ambas as queries,
        # em vez de misturar um escopo semanal com um escopo diário.
        tarefas_hoje = (
            supabase_admin
            .table("tarefas_estudo")
            .select(
                "id, titulo, tipo_tarefa, status, duracao_minutos, materia_id, "
                "aula_id, lista_questoes_id, tema_redacao_id"
            )
            .eq("usuario_id", id_usuario)
            .eq("data_agendada", hoje.isoformat())
            .order("ordem")
            .execute()
            .data or []
        )

        # Slugs do conteúdo vinculado a cada tarefa de hoje, para o front
        # montar o link de destino do botão "Começar" (/aulas/:slug,
        # /questoes/:slug, /redacao/:slug) — mesma lógica de Plano de Estudos.
        ids_aulas = list({t["aula_id"] for t in tarefas_hoje if t.get("aula_id")})
        ids_listas = list({t["lista_questoes_id"] for t in tarefas_hoje if t.get("lista_questoes_id")})
        ids_temas_redacao = list({t["tema_redacao_id"] for t in tarefas_hoje if t.get("tema_redacao_id")})

        slug_por_aula_id = {
            a["id"]: a["slug"]
            for a in (
                supabase_admin.table("aulas").select("id, slug").in_("id", ids_aulas).execute().data or []
            )
        } if ids_aulas else {}

        slug_por_lista_id = {
            l["id"]: l["slug"]
            for l in (
                supabase_admin.table("listas_questoes").select("id, slug").in_("id", ids_listas).execute().data or []
            )
        } if ids_listas else {}

        slug_por_tema_redacao_id = {
            t["id"]: t["slug"]
            for t in (
                supabase_admin.table("temas_redacao").select("id, slug").in_("id", ids_temas_redacao).execute().data or []
            )
        } if ids_temas_redacao else {}

        def resolver_conteudo_slug(tarefa: dict) -> str | None:
            if tarefa["tipo_tarefa"] == "aula":
                return slug_por_aula_id.get(tarefa.get("aula_id"))
            if tarefa["tipo_tarefa"] == "questoes":
                return slug_por_lista_id.get(tarefa.get("lista_questoes_id"))
            if tarefa["tipo_tarefa"] == "redacao":
                return slug_por_tema_redacao_id.get(tarefa.get("tema_redacao_id"))
            return None

        tarefas_totais = len(tarefas_hoje)
        tarefas_concluidas = sum(1 for tarefa in tarefas_hoje if tarefa["status"] == "concluida")

        evolucao_semanal = []
        for indice in range(7):
            dia_data = inicio_semana + timedelta(days=indice)
            atividade = atividades_por_data.get(dia_data.isoformat())

            percentual = 0
            if atividade and atividade["questoes_respondidas"] > 0:
                percentual = round((atividade["respostas_corretas"] / atividade["questoes_respondidas"]) * 100)

            evolucao_semanal.append({
                "dia_semana": DIAS_SEMANA[indice],
                "percentual": percentual,
            })

        materias = (
            supabase_admin
            .table("materias")
            .select("id, nome, cor, icone")
            .eq("ativo", True)
            .order("ordem")
            .execute()
            .data or []
        )
        materias_por_id = {materia["id"]: materia for materia in materias}

        tentativas = (
            supabase_admin
            .table("tentativas_questoes")
            .select("questao_id, acertou, questoes!inner(materia_id)")
            .eq("usuario_id", id_usuario)
            .execute()
            .data or []
        )

        acertos_por_materia: dict[str, int] = {}
        total_por_materia: dict[str, int] = {}
        for tentativa in tentativas:
            materia_id = tentativa["questoes"]["materia_id"]
            total_por_materia[materia_id] = total_por_materia.get(materia_id, 0) + 1
            if tentativa["acertou"]:
                acertos_por_materia[materia_id] = acertos_por_materia.get(materia_id, 0) + 1

        desempenho_por_materia = []
        for materia in materias:
            total = total_por_materia.get(materia["id"], 0)
            acertos = acertos_por_materia.get(materia["id"], 0)
            percentual = round((acertos / total) * 100) if total > 0 else 0

            if percentual >= 75:
                cor = "teal"
            elif percentual >= 50:
                cor = "gold"
            elif percentual >= 25:
                cor = "blue"
            else:
                cor = "red"

            desempenho_por_materia.append({
                "materia_id": materia["id"],
                "materia": materia["nome"],
                "percentual": percentual,
                "cor": cor,
            })

        STATUS_TAREFA_PARA_STATUS_DASHBOARD = {
            "concluida": "concluido",
            "em_andamento": "em-andamento",
            "pendente": "nao-iniciado",
        }

        plano_do_dia = []
        for tarefa in tarefas_hoje:
            materia = materias_por_id.get(tarefa["materia_id"])
            plano_do_dia.append({
                "id": tarefa["id"],
                "icone": materia["icone"] if materia else "📘",
                "materia": materia["nome"] if materia else "Geral",
                "materia_cor": materia["cor"] if materia else "gray",
                "status": STATUS_TAREFA_PARA_STATUS_DASHBOARD.get(tarefa["status"], "nao-iniciado"),
                "titulo": tarefa["titulo"],
                "duracao_min": tarefa["duracao_minutos"] or 0,
                "progresso": 100 if tarefa["status"] == "concluida" else (50 if tarefa["status"] == "em_andamento" else None),
                "tipo": TIPO_TAREFA_PARA_TIPO_CONTRATO.get(tarefa["tipo_tarefa"], "revisao"),
                "conteudo_slug": resolver_conteudo_slug(tarefa),
            })

        alertas = []
        materias_abaixo_meta = [m for m in desempenho_por_materia if m["percentual"] < 50 and total_por_materia.get(m["materia_id"], 0) > 0]
        if materias_abaixo_meta:
            nomes = " e ".join(m["materia"] for m in materias_abaixo_meta[:2])
            alertas.append({
                "id": str(uuid4()),
                "titulo": "Evolução semanal",
                "mensagem": f"{nomes} estão abaixo da meta. Revise esta semana!",
            })

        if not tentativas:
            alertas.append({
                "id": str(uuid4()),
                "titulo": "Sem dados de desempenho",
                "mensagem": "Ainda não há dados suficientes para calcular seu desempenho por matéria.",
            })

        if ofensiva_dias == 0:
            alertas.append({
                "id": str(uuid4()),
                "titulo": "Ofensiva parada",
                "mensagem": "Você ainda não iniciou sua ofensiva de estudos esta semana.",
            })

        return {
            "resumo": {
                "tempo_estudado_min": tempo_estudado_min,
                "tarefas_concluidas": tarefas_concluidas,
                "tarefas_totais": tarefas_totais,
                "xp_semana": xp_semana,
                "ofensiva_dias": ofensiva_dias,
            },
            "evolucao_semanal": evolucao_semanal,
            "desempenho_por_materia": desempenho_por_materia,
            "plano_do_dia": plano_do_dia,
            "alertas": alertas,
        }

    except HTTPException:
        raise

    except Exception as erro:
        print(f"Erro ao obter dashboard do aluno: {erro}")

        raise HTTPException(
            status_code=500,
            detail="Erro ao obter dashboard"
        )
