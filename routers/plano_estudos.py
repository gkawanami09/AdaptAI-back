from fastapi import APIRouter, HTTPException, Depends, Query
from database import supabase_admin
from datetime import date, datetime, timedelta, timezone
from uuid import UUID
from utils.autenticacao import pegar_usuario_atual
from schemas.plano_estudos_schema import (
    PlanoEstudosResponse,
    ReorganizarIAResponse,
    ConcluirTarefaResponse,
    TarefaPlanoCriar,
    TarefaPlanoCriarResponse,
    GetPlanoEstudosOpcoesResponse,
    PostCriarPlanoEstudosParams,
    PostCriarPlanoEstudosResponse,
    GetPlanoEstudosGeradoResponse,
)
from services.plano_estudos_wizard_service import PlanoEstudosWizardService

router = APIRouter(
    prefix='/aluno/plano-estudos',
    tags=['Aluno - Plano de Estudos']
)

wizard_service = PlanoEstudosWizardService()

DIAS_SEMANA = ["Dom", "Seg", "Ter", "Qua", "Qui", "Sex", "Sáb"]
MESES = [
    "janeiro", "fevereiro", "março", "abril", "maio", "junho",
    "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"
]

TIPO_TAREFA_PARA_TIPO_CONTRATO = {
    "aula": "aula",
    "questoes": "questoes",
    "simulado": "prova",
    "redacao": "redacao",
    "revisao": "revisao",
    "personalizada": "revisao",
}


@router.get('/opcoes', response_model=GetPlanoEstudosOpcoesResponse)
def obter_opcoes_plano_estudos(usuario_atual=Depends(pegar_usuario_atual)):
    try:
        return wizard_service.listar_opcoes()

    except HTTPException:
        raise

    except Exception as erro:
        print(f"Erro ao obter opções de plano de estudos: {erro}")

        raise HTTPException(
            status_code=500,
            detail="Erro ao obter opções de plano de estudos"
        )


@router.post('', status_code=201, response_model=PostCriarPlanoEstudosResponse)
def criar_plano_estudos_wizard(
    dados: PostCriarPlanoEstudosParams,
    usuario_atual=Depends(pegar_usuario_atual)
):
    try:
        id_usuario = str(usuario_atual.id)
        plano = wizard_service.criar_plano(id_usuario, dados)

        if plano["status_geracao"] == "erro":
            return {
                "id": plano["id"],
                "status": "erro",
                "mensagem": plano.get("mensagem_erro") or "Não foi possível gerar o plano. Tente novamente.",
            }

        return {
            "id": plano["id"],
            "status": "concluido",
            "mensagem": "Seu plano foi gerado.",
        }

    except HTTPException:
        raise

    except Exception as erro:
        print(f"Erro ao criar plano de estudos: {erro}")

        raise HTTPException(
            status_code=500,
            detail="Erro ao criar plano de estudos"
        )


@router.get('/{plano_id}', response_model=GetPlanoEstudosGeradoResponse)
def obter_plano_estudos_gerado(plano_id: UUID, usuario_atual=Depends(pegar_usuario_atual)):
    try:
        plano = wizard_service.obter_plano(str(plano_id), str(usuario_atual.id))

        if not plano:
            raise HTTPException(
                status_code=404,
                detail="Plano não encontrado"
            )

        return wizard_service.montar_resposta_gerado(plano)

    except HTTPException:
        raise

    except Exception as erro:
        print(f"Erro ao obter plano de estudos gerado: {erro}")

        raise HTTPException(
            status_code=500,
            detail="Erro ao obter plano de estudos gerado"
        )


@router.post('/{plano_id}/sincronizar-tarefas')
def sincronizar_tarefas_plano_estudos(plano_id: UUID, usuario_atual=Depends(pegar_usuario_atual)):
    try:
        tarefas_criadas = wizard_service.sincronizar_tarefas(str(plano_id), str(usuario_atual.id))

        return {"sucesso": True, "tarefas_criadas": tarefas_criadas}

    except HTTPException:
        raise

    except Exception as erro:
        print(f"Erro ao sincronizar tarefas do plano de estudos: {erro}")

        raise HTTPException(
            status_code=500,
            detail="Erro ao sincronizar tarefas do plano de estudos"
        )


@router.get('', response_model=PlanoEstudosResponse)
def obter_plano_estudos(
    periodo: str = Query(...),
    data: str = Query(...),
    usuario_atual=Depends(pegar_usuario_atual)
):
    try:
        if periodo not in ("dia", "semana", "mes"):
            raise HTTPException(
                status_code=400,
                detail="Período inválido"
            )

        try:
            data_referencia = date.fromisoformat(data)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail="Data inválida"
            )

        id_usuario = str(usuario_atual.id)

        if periodo == "dia":
            data_inicio = data_referencia
            data_fim = data_referencia
        elif periodo == "semana":
            data_inicio = data_referencia - timedelta(days=(data_referencia.weekday() + 1) % 7)
            data_fim = data_inicio + timedelta(days=6)
        else:
            data_inicio = data_referencia.replace(day=1)
            if data_inicio.month == 12:
                data_fim = data_inicio.replace(year=data_inicio.year + 1, month=1) - timedelta(days=1)
            else:
                data_fim = data_inicio.replace(month=data_inicio.month + 1) - timedelta(days=1)

        semana_inicio = data_referencia - timedelta(days=(data_referencia.weekday() + 1) % 7)
        semana_fim = semana_inicio + timedelta(days=6)

        tarefas_periodo = (
            supabase_admin
            .table("tarefas_estudo")
            .select("id, titulo, tipo_tarefa, data_agendada, duracao_minutos, status, materia_id")
            .eq("usuario_id", id_usuario)
            .gte("data_agendada", data_inicio.isoformat())
            .lte("data_agendada", data_fim.isoformat())
            .order("data_agendada")
            .order("ordem")
            .execute()
            .data or []
        )

        tarefas_semana = (
            supabase_admin
            .table("tarefas_estudo")
            .select("id, tipo_tarefa, data_agendada, duracao_minutos, status, materia_id")
            .eq("usuario_id", id_usuario)
            .gte("data_agendada", semana_inicio.isoformat())
            .lte("data_agendada", semana_fim.isoformat())
            .execute()
            .data or []
        )

        ids_materias = list({t["materia_id"] for t in (tarefas_periodo + tarefas_semana) if t["materia_id"]})
        materias = (
            supabase_admin
            .table("materias")
            .select("id, nome, cor, icone")
            .in_("id", ids_materias)
            .execute()
            .data or []
        ) if ids_materias else []
        materias_por_id = {materia["id"]: materia for materia in materias}

        tarefas_concluidas_total = sum(1 for tarefa in tarefas_periodo if tarefa["status"] == "concluida")
        tarefas_totais = len(tarefas_periodo)

        if periodo == "semana":
            intervalo_label = (
                f"Semana de {data_inicio.day:02d} a {data_fim.day:02d} de "
                f"{MESES[data_fim.month - 1]} · {tarefas_concluidas_total}/{tarefas_totais} tarefas concluídas"
            )
        elif periodo == "mes":
            intervalo_label = (
                f"{MESES[data_inicio.month - 1].capitalize()} · "
                f"{tarefas_concluidas_total}/{tarefas_totais} tarefas concluídas"
            )
        else:
            intervalo_label = (
                f"{data_referencia.day:02d} de {MESES[data_referencia.month - 1]} · "
                f"{tarefas_concluidas_total}/{tarefas_totais} tarefas concluídas"
            )

        percentual_progresso = round((tarefas_concluidas_total / tarefas_totais) * 100) if tarefas_totais > 0 else 0
        label_periodo = {"dia": "do dia", "semana": "da semana", "mes": "do mês"}[periodo]

        tarefas_por_data: dict[str, list] = {}
        for tarefa in tarefas_semana:
            tarefas_por_data.setdefault(tarefa["data_agendada"], []).append(tarefa)

        dias_da_semana = []
        for indice in range(7):
            dia_atual = semana_inicio + timedelta(days=indice)
            dias_da_semana.append({
                "label": DIAS_SEMANA[indice],
                "data": dia_atual.day,
                "data_iso": dia_atual.isoformat(),
                "tem_tarefas": bool(tarefas_por_data.get(dia_atual.isoformat())),
            })

        dia_selecionado = data_referencia
        if periodo != "dia":
            for indice in range(7):
                dia_atual = semana_inicio + timedelta(days=indice)
                if tarefas_por_data.get(dia_atual.isoformat()):
                    dia_selecionado = dia_atual
                    break

        tarefas_do_dia_banco = (
            tarefas_periodo if periodo == "dia"
            else tarefas_por_data.get(dia_selecionado.isoformat(), [])
        )

        tarefas_do_dia = []
        for tarefa in tarefas_do_dia_banco:
            materia = materias_por_id.get(tarefa["materia_id"])
            materia_nome = materia["nome"] if materia else "Geral"
            materia_cor = materia["cor"] if materia else "gray"
            icone = materia["icone"] if materia else "📘"

            tarefas_do_dia.append({
                "id": tarefa["id"],
                "icone": icone,
                "icone_cor": materia_cor,
                "titulo": tarefa["titulo"],
                "materia": materia_nome,
                "materia_cor": materia_cor,
                "duracao_min": tarefa["duracao_minutos"] or 0,
                "concluida": tarefa["status"] == "concluida",
                "progresso": 100 if tarefa["status"] == "concluida" else (50 if tarefa["status"] == "em_andamento" else None),
                "tipo": TIPO_TAREFA_PARA_TIPO_CONTRATO.get(tarefa["tipo_tarefa"], "revisao"),
            })

        visao_geral_semana = []
        for indice in range(7):
            dia_atual = semana_inicio + timedelta(days=indice)
            tarefas_dia = tarefas_por_data.get(dia_atual.isoformat(), [])

            if not tarefas_dia:
                visao_geral_semana.append({
                    "dia": DIAS_SEMANA[indice],
                    "badges": [],
                    "descanso_label": "Descanso",
                    "concluidas": 0,
                    "total": 0,
                })
                continue

            concluidas = sum(1 for t in tarefas_dia if t["status"] == "concluida")
            total = len(tarefas_dia)

            badges = []
            if concluidas == total:
                badges.append({"label": "Concluído", "color": "teal"})

            materias_do_dia = {t["materia_id"] for t in tarefas_dia if t["materia_id"]}
            for materia_id in materias_do_dia:
                materia = materias_por_id.get(materia_id)
                if materia:
                    badges.append({"label": materia["nome"], "color": materia["cor"]})

            visao_geral_semana.append({
                "dia": DIAS_SEMANA[indice],
                "badges": badges,
                "descanso_label": None,
                "concluidas": concluidas,
                "total": total,
            })

        acertos_materia: dict[str, dict] = {}
        for tarefa in tarefas_semana:
            if not tarefa["materia_id"]:
                continue
            acertos_materia.setdefault(tarefa["materia_id"], {"total": 0, "concluidas": 0})
            acertos_materia[tarefa["materia_id"]]["total"] += 1
            if tarefa["status"] == "concluida":
                acertos_materia[tarefa["materia_id"]]["concluidas"] += 1

        prioridades_da_semana = []
        for materia_id, dados in acertos_materia.items():
            materia = materias_por_id.get(materia_id)
            if not materia or dados["total"] == 0:
                continue

            percentual = round((dados["concluidas"] / dados["total"]) * 100)
            if percentual < 60:
                prioridades_da_semana.append({
                    "materia": materia["nome"],
                    "descricao": f"Abaixo da meta — {percentual}%",
                    "prioridade": "alta" if percentual < 40 else "media",
                    "tom": materia["cor"],
                    "icone": materia["icone"],
                })

        horas_planejadas_min = sum(t["duracao_minutos"] or 0 for t in tarefas_periodo)
        horas_concluidas_min = sum(t["duracao_minutos"] or 0 for t in tarefas_periodo if t["status"] == "concluida")
        tarefas_restantes = tarefas_totais - tarefas_concluidas_total

        def formatar_horas(minutos: int) -> str:
            horas = minutos // 60
            restante = minutos % 60
            return f"{horas}h{restante:02d}" if restante else f"{horas}h"

        estatisticas = [
            {"label": "Horas planejadas", "valor": formatar_horas(horas_planejadas_min), "cor": "purple"},
            {"label": "Horas concluídas", "valor": formatar_horas(horas_concluidas_min), "cor": "teal"},
            {"label": "Tarefas restantes", "valor": str(tarefas_restantes), "cor": "gold"},
        ]

        return {
            "intervalo_label": intervalo_label,
            "tarefas_concluidas_total": tarefas_concluidas_total,
            "tarefas_totais": tarefas_totais,
            "progresso": {
                "percentual": percentual_progresso,
                "label": f"{percentual_progresso}% {label_periodo}",
            },
            "dias_da_semana": dias_da_semana,
            "tarefas_do_dia": tarefas_do_dia,
            "visao_geral_semana": visao_geral_semana,
            "prioridades_da_semana": prioridades_da_semana,
            "estatisticas": estatisticas,
        }

    except HTTPException:
        raise

    except Exception as erro:
        print(f"Erro ao obter plano de estudos: {erro}")

        raise HTTPException(
            status_code=500,
            detail="Erro ao obter plano de estudos"
        )


@router.post('/reorganizar-ia', response_model=ReorganizarIAResponse)
def reorganizar_plano_ia(usuario_atual=Depends(pegar_usuario_atual)):
    try:
        id_usuario = str(usuario_atual.id)

        tarefas_pendentes = (
            supabase_admin
            .table("tarefas_estudo")
            .select("id", count="exact")
            .eq("usuario_id", id_usuario)
            .eq("status", "pendente")
            .execute()
        )

        if not tarefas_pendentes.count:
            raise HTTPException(
                status_code=422,
                detail="Não há tarefas suficientes para reorganizar"
            )

        # TODO: integração com IA para redistribuir tarefas pendentes ainda não
        # implementada. Aguardando definição do serviço/modelo responsável pela
        # reorganização automática do plano.
        raise HTTPException(
            status_code=422,
            detail="Reorganização automática ainda não disponível"
        )

    except HTTPException:
        raise

    except Exception as erro:
        print(f"Erro ao reorganizar plano de estudos: {erro}")

        raise HTTPException(
            status_code=500,
            detail="Erro ao reorganizar plano de estudos"
        )


@router.patch('/tarefas/{tarefa_id}/concluir', response_model=ConcluirTarefaResponse)
def concluir_tarefa(
    tarefa_id: UUID,
    usuario_atual=Depends(pegar_usuario_atual)
):
    try:
        id_usuario = str(usuario_atual.id)
        agora = datetime.now(timezone.utc)

        tarefa = (
            supabase_admin
            .table("tarefas_estudo")
            .select("id, usuario_id, status, duracao_minutos")
            .eq("id", str(tarefa_id))
            .eq("usuario_id", id_usuario)
            .limit(1)
            .execute()
        )

        if not tarefa.data:
            raise HTTPException(
                status_code=404,
                detail="Tarefa não encontrada"
            )

        supabase_admin.table("tarefas_estudo").update({
            "status": "concluida",
            "concluido_em": agora.isoformat(),
            "atualizado_em": agora.isoformat(),
        }).eq("id", str(tarefa_id)).execute()

        xp_ganho = 10
        hoje = agora.date().isoformat()
        duracao = tarefa.data[0]["duracao_minutos"] or 0

        atividade_hoje = (
            supabase_admin
            .table("atividade_diaria")
            .select("id, minutos_estudo, xp_ganho, tarefas_concluidas")
            .eq("usuario_id", id_usuario)
            .eq("data_atividade", hoje)
            .limit(1)
            .execute()
        )

        if atividade_hoje.data:
            registro = atividade_hoje.data[0]
            supabase_admin.table("atividade_diaria").update({
                "minutos_estudo": registro["minutos_estudo"] + duracao,
                "xp_ganho": registro["xp_ganho"] + xp_ganho,
                "tarefas_concluidas": registro["tarefas_concluidas"] + 1,
                "atualizado_em": agora.isoformat(),
            }).eq("id", registro["id"]).execute()
        else:
            supabase_admin.table("atividade_diaria").insert({
                "usuario_id": id_usuario,
                "data_atividade": hoje,
                "minutos_estudo": duracao,
                "xp_ganho": xp_ganho,
                "tarefas_concluidas": 1,
            }).execute()

        estatisticas = (
            supabase_admin
            .table("estatisticas_usuario")
            .select("usuario_id, xp_total, ofensiva_atual_dias, maior_ofensiva_dias, ultima_atividade_data, minutos_estudo_total")
            .eq("usuario_id", id_usuario)
            .limit(1)
            .execute()
        )

        hoje_data = agora.date()

        if estatisticas.data:
            registro = estatisticas.data[0]
            ultima_data = date.fromisoformat(registro["ultima_atividade_data"]) if registro["ultima_atividade_data"] else None

            if ultima_data == hoje_data:
                nova_ofensiva = registro["ofensiva_atual_dias"]
            elif ultima_data == hoje_data - timedelta(days=1):
                nova_ofensiva = registro["ofensiva_atual_dias"] + 1
            else:
                nova_ofensiva = 1

            supabase_admin.table("estatisticas_usuario").update({
                "xp_total": registro["xp_total"] + xp_ganho,
                "ofensiva_atual_dias": nova_ofensiva,
                "maior_ofensiva_dias": max(nova_ofensiva, registro["maior_ofensiva_dias"]),
                "ultima_atividade_data": hoje_data.isoformat(),
                "minutos_estudo_total": registro["minutos_estudo_total"] + duracao,
                "atualizado_em": agora.isoformat(),
            }).eq("usuario_id", id_usuario).execute()
        else:
            supabase_admin.table("estatisticas_usuario").insert({
                "usuario_id": id_usuario,
                "xp_total": xp_ganho,
                "ofensiva_atual_dias": 1,
                "maior_ofensiva_dias": 1,
                "ultima_atividade_data": hoje_data.isoformat(),
                "minutos_estudo_total": duracao,
            }).execute()

        return {"sucesso": True}

    except HTTPException:
        raise

    except Exception as erro:
        print(f"Erro ao concluir tarefa: {erro}")

        raise HTTPException(
            status_code=500,
            detail="Erro ao concluir tarefa"
        )


@router.post('/tarefas', status_code=201, response_model=TarefaPlanoCriarResponse)
def criar_tarefa(
    dados: TarefaPlanoCriar,
    usuario_atual=Depends(pegar_usuario_atual)
):
    try:
        id_usuario = str(usuario_atual.id)

        try:
            date.fromisoformat(dados.data)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail="Data inválida"
            )

        materia = (
            supabase_admin
            .table("materias")
            .select("id")
            .eq("id", str(dados.materia_id))
            .limit(1)
            .execute()
        )

        if not materia.data:
            raise HTTPException(
                status_code=400,
                detail="Matéria não encontrada"
            )

        tipo_tarefa = {
            "aula": "aula",
            "questoes": "questoes",
            "lista": "questoes",
            "prova": "simulado",
            "redacao": "redacao",
            "revisao": "revisao",
        }.get(dados.tipo, "personalizada")

        plano_ativo = (
            supabase_admin
            .table("planos_estudo")
            .select("id")
            .eq("usuario_id", id_usuario)
            .eq("status", "ativo")
            .limit(1)
            .execute()
        )

        if plano_ativo.data:
            plano_estudo_id = plano_ativo.data[0]["id"]
        else:
            novo_plano = (
                supabase_admin
                .table("planos_estudo")
                .insert({
                    "usuario_id": id_usuario,
                    "titulo": "Plano de estudos",
                    "status": "ativo",
                    "criado_por": "usuario",
                })
                .execute()
            )
            plano_estudo_id = novo_plano.data[0]["id"]

        nova_tarefa = (
            supabase_admin
            .table("tarefas_estudo")
            .insert({
                "plano_estudo_id": plano_estudo_id,
                "usuario_id": id_usuario,
                "materia_id": str(dados.materia_id),
                "titulo": dados.titulo.strip(),
                "tipo_tarefa": tipo_tarefa,
                "data_agendada": dados.data,
                "duracao_minutos": dados.duracao_min,
                "origem": "usuario",
            })
            .execute()
        )

        if not nova_tarefa.data:
            raise HTTPException(
                status_code=500,
                detail="Não foi possível criar a tarefa"
            )

        return {
            "id": nova_tarefa.data[0]["id"],
            "sucesso": True,
        }

    except HTTPException:
        raise

    except Exception as erro:
        print(f"Erro ao criar tarefa: {erro}")

        raise HTTPException(
            status_code=500,
            detail="Erro ao criar tarefa"
        )
