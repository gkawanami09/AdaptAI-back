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
from services.plano_estudos.periodo import dias_calendario
from services.gamificacao import EventoGamificacao, conceder_xp_e_atividade, registrar_evento_gamificacao

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

        ids_planos_ativos = [
            p["id"] for p in
            supabase_admin
            .table("planos_estudo")
            .select("id")
            .eq("usuario_id", id_usuario)
            .eq("status", "ativo")
            .execute()
            .data or []
        ]

        CAMPOS_TAREFA = (
            "id, titulo, tipo_tarefa, data_agendada, duracao_minutos, status, "
            "materia_id, aula_id, lista_questoes_id, tema_redacao_id"
        )

        if ids_planos_ativos:
            tarefas_periodo = (
                supabase_admin
                .table("tarefas_estudo")
                .select(CAMPOS_TAREFA)
                .eq("usuario_id", id_usuario)
                .in_("plano_estudo_id", ids_planos_ativos)
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
                .select(CAMPOS_TAREFA)
                .eq("usuario_id", id_usuario)
                .in_("plano_estudo_id", ids_planos_ativos)
                .gte("data_agendada", semana_inicio.isoformat())
                .lte("data_agendada", semana_fim.isoformat())
                .execute()
                .data or []
            )
        else:
            tarefas_periodo = []
            tarefas_semana = []

        # Slugs do conteúdo vinculado a cada tarefa (aula/lista de
        # questões/tema de redação), para o front montar o link de destino
        # por tipo (/aulas/:slug, /questoes/:slug, /redacao/:slug).
        todas_tarefas = tarefas_periodo + tarefas_semana
        ids_aulas = list({t["aula_id"] for t in todas_tarefas if t.get("aula_id")})
        ids_listas = list({t["lista_questoes_id"] for t in todas_tarefas if t.get("lista_questoes_id")})
        ids_temas_redacao = list({t["tema_redacao_id"] for t in todas_tarefas if t.get("tema_redacao_id")})

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

        # Resolve o slug do conteúdo vinculado a uma tarefa, conforme o tipo.
        def resolver_conteudo_slug(tarefa: dict) -> str | None:
            if tarefa["tipo_tarefa"] == "aula":
                return slug_por_aula_id.get(tarefa.get("aula_id"))
            if tarefa["tipo_tarefa"] == "questoes":
                return slug_por_lista_id.get(tarefa.get("lista_questoes_id"))
            if tarefa["tipo_tarefa"] == "redacao":
                return slug_por_tema_redacao_id.get(tarefa.get("tema_redacao_id"))
            return None

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

        # tarefas_do_dia deve sempre refletir a `data` recebida, independente
        # do `periodo` — este último só influencia visao_geral_semana,
        # prioridades_da_semana e progresso.
        tarefas_do_dia_banco = (
            tarefas_periodo if periodo == "dia"
            else tarefas_por_data.get(data_referencia.isoformat(), [])
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
                "conteudo_slug": resolver_conteudo_slug(tarefa),
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
        hoje = datetime.now(timezone.utc).date()

        plano_ativo = (
            supabase_admin
            .table("planos_estudo")
            .select("id, data_fim, dias_estudo")
            .eq("usuario_id", id_usuario)
            .eq("status", "ativo")
            .limit(1)
            .execute()
            .data
        )

        if not plano_ativo:
            raise HTTPException(
                status_code=422,
                detail="Não há plano de estudos ativo para reorganizar"
            )

        plano = plano_ativo[0]

        tarefas_pendentes = (
            supabase_admin
            .table("tarefas_estudo")
            .select("id, ordem")
            .eq("usuario_id", id_usuario)
            .eq("plano_estudo_id", plano["id"])
            .eq("status", "pendente")
            .order("data_agendada")
            .order("ordem")
            .execute()
            .data or []
        )

        if not tarefas_pendentes:
            raise HTTPException(
                status_code=422,
                detail="Não há tarefas suficientes para reorganizar"
            )

        data_fim = date.fromisoformat(plano["data_fim"]) if plano.get("data_fim") else None
        dias_estudo = plano.get("dias_estudo") or []

        dias_disponiveis = (
            dias_calendario(hoje, data_fim, dias_estudo)
            if data_fim and dias_estudo
            else []
        )

        if not dias_disponiveis:
            raise HTTPException(
                status_code=422,
                detail="Não há dias de estudo disponíveis no período restante do plano"
            )

        # Redistribui as tarefas pendentes igualmente entre os dias de estudo
        # restantes até o fim do plano — abordagem determinística (sem chamada
        # de IA) para uma tarefa puramente de reagendamento, mais previsível e
        # sem custo/latência de inferência.
        for indice, tarefa in enumerate(tarefas_pendentes):
            novo_dia = dias_disponiveis[indice % len(dias_disponiveis)]
            supabase_admin.table("tarefas_estudo").update({
                "data_agendada": novo_dia.isoformat(),
            }).eq("id", tarefa["id"]).execute()

        return {"sucesso": True}

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
            .select("id, usuario_id, status, duracao_minutos, tipo_tarefa, plano_estudo_id")
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

        dados_tarefa = tarefa.data[0]

        supabase_admin.table("tarefas_estudo").update({
            "status": "concluida",
            "concluido_em": agora.isoformat(),
            "atualizado_em": agora.isoformat(),
        }).eq("id", str(tarefa_id)).execute()

        duracao = dados_tarefa["duracao_minutos"] or 0

        conceder_xp_e_atividade(id_usuario, 10, minutos_estudo=duracao, agora=agora, tarefas_concluidas=1)
        registrar_evento_gamificacao(
            id_usuario, EventoGamificacao.SESSAO_ESTUDO_CONCLUIDA, {"minutos": duracao}
        )

        if dados_tarefa["tipo_tarefa"] == "aula":
            registrar_evento_gamificacao(
                id_usuario, EventoGamificacao.AULA_CONCLUIDA, {"minutos": duracao}
            )

        # Replaneja os dias futuros ainda não realizados do plano ao
        # concluir uma aula OU uma sessão de questões — a segunda é o
        # momento em que o desempenho do aluno (tentativas_questoes) muda
        # de fato, então é quando o replanejamento consegue repriorizar
        # matérias/tópicos com mais erro. Tarefas passadas e já concluídas
        # nunca são tocadas.
        if dados_tarefa["tipo_tarefa"] in ("aula", "questoes") and dados_tarefa.get("plano_estudo_id"):
            wizard_service.replanejar_apos_conclusao(dados_tarefa["plano_estudo_id"], id_usuario)

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
