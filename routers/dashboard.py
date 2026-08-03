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

        tarefas_semana = (
            supabase_admin
            .table("tarefas_estudo")
            .select("id, status")
            .eq("usuario_id", id_usuario)
            .gte("data_agendada", inicio_semana.isoformat())
            .lte("data_agendada", fim_semana.isoformat())
            .execute()
            .data or []
        )

        tarefas_totais = len(tarefas_semana)
        tarefas_concluidas = sum(1 for tarefa in tarefas_semana if tarefa["status"] == "concluida")

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
            .select("id, nome")
            .eq("ativo", True)
            .order("ordem")
            .execute()
            .data or []
        )

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

        # TODO: plano_do_dia depende de mapear tarefas_estudo (aula_id/lista_questoes_id/
        # modelo_simulado_id/tema_redacao_id) para ícone e cor de exibição; aguardando
        # definição do design system de ícones por tipo de tarefa.
        plano_do_dia = []

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
