from fastapi import APIRouter, HTTPException, Depends
from database import supabase_admin
from datetime import datetime, timezone
from uuid import UUID
from utils.autenticacao import pegar_usuario_atual
from schemas.simulados_schema import (
    SimuladosResponse,
    IniciarSimuladoResponse,
    ResponderQuestaoSimuladoPayload,
    ResponderQuestaoSimuladoResponse,
    FinalizarSimuladoResponse,
)
from services.simulados_service import selecionar_questoes, calcular_resultado, calcular_resultado_por_area
from services.gamificacao import EventoGamificacao, conceder_xp_e_atividade, registrar_evento_gamificacao

router = APIRouter(
    prefix='/aluno/simulados',
    tags=['Aluno - Simulados']
)

TAG_POR_TIPO_MODELO = {
    "completo": ("Completo", "purple"),
    "rapido": ("Rápido", "blue"),
    "treino_area": ("Treino por área", "teal"),
    "revisao_erros": ("Revisão de erros", "gold"),
    "personalizado": ("Personalizado", "green"),
}

ICONE_POR_TIPO_MODELO = {
    "completo": ("📋", "purple"),
    "rapido": ("⚡", "blue"),
    "treino_area": ("🎯", "teal"),
    "revisao_erros": ("🔁", "gold"),
    "personalizado": ("🧩", "green"),
}


def formatar_duracao(minutos: int | None) -> str:
    if not minutos:
        return "0min"

    horas = minutos // 60
    restante = minutos % 60

    if horas and restante:
        return f"{horas}h{restante:02d}"
    if horas:
        return f"{horas}h"
    return f"{restante}min"


def formatar_duracao_segundos(segundos: int | None) -> str:
    if not segundos:
        return "0min"

    return formatar_duracao(segundos // 60)


def montar_resumo(usuario_id: str):
    sessoes_concluidas = (
        supabase_admin.table("sessoes_simulado")
        .select("nota_estimada, duracao_segundos, percentual_acerto")
        .eq("usuario_id", usuario_id)
        .eq("status", "concluido")
        .execute()
        .data or []
    )

    if not sessoes_concluidas:
        return {
            "nota_estimada": 0,
            "tempo_medio": "0min",
            "taxa_acerto_percentual": 0,
        }

    notas = [s["nota_estimada"] for s in sessoes_concluidas if s["nota_estimada"] is not None]
    duracoes = [s["duracao_segundos"] for s in sessoes_concluidas if s["duracao_segundos"] is not None]
    percentuais = [s["percentual_acerto"] for s in sessoes_concluidas if s["percentual_acerto"] is not None]

    nota_estimada = round(sum(notas) / len(notas)) if notas else 0
    tempo_medio_segundos = round(sum(duracoes) / len(duracoes)) if duracoes else 0
    taxa_acerto = round(sum(percentuais) / len(percentuais)) if percentuais else 0

    return {
        "nota_estimada": nota_estimada,
        "tempo_medio": formatar_duracao_segundos(tempo_medio_segundos),
        "taxa_acerto_percentual": taxa_acerto,
    }


def montar_catalogo():
    modelos = (
        supabase_admin.table("modelos_simulado")
        .select("slug, titulo, descricao, tipo_modelo, total_questoes, duracao_minutos")
        .eq("ativo", True)
        .execute()
        .data or []
    )

    if not modelos:
        return []

    catalogo = []
    for modelo in modelos:
        icone, icone_cor = ICONE_POR_TIPO_MODELO.get(modelo["tipo_modelo"], ("📋", "gray"))
        tag, tag_cor = TAG_POR_TIPO_MODELO.get(modelo["tipo_modelo"], (modelo["tipo_modelo"], "gray"))

        descricao = modelo.get("descricao")
        if not descricao:
            total_questoes = modelo.get("total_questoes") or 0
            descricao = f"{total_questoes} questões"

        catalogo.append({
            "slug": modelo["slug"],
            "titulo": modelo["titulo"],
            "descricao": descricao,
            "icone": icone,
            "icone_cor": icone_cor,
            "tag": tag,
            "tag_cor": tag_cor,
            "duracao": formatar_duracao(modelo.get("duracao_minutos")),
        })

    return catalogo


def montar_historico(usuario_id: str):
    sessoes = (
        supabase_admin.table("sessoes_simulado")
        .select("id, concluido_em, duracao_segundos, nota_estimada, percentual_acerto, modelo_simulado_id")
        .eq("usuario_id", usuario_id)
        .eq("status", "concluido")
        .order("concluido_em", desc=True)
        .execute()
        .data or []
    )

    if not sessoes:
        return []

    ids_modelos = list({s["modelo_simulado_id"] for s in sessoes if s["modelo_simulado_id"]})
    modelos = (
        supabase_admin.table("modelos_simulado")
        .select("id, titulo")
        .in_("id", ids_modelos)
        .execute()
        .data or []
    ) if ids_modelos else []
    modelos_por_id = {m["id"]: m for m in modelos}

    historico = []
    for sessao in sessoes:
        modelo = modelos_por_id.get(sessao["modelo_simulado_id"])
        modelo_titulo = modelo["titulo"] if modelo else "Simulado"

        concluido_em = sessao["concluido_em"]
        dia = "--"
        titulo = modelo_titulo

        if concluido_em:
            data_concluido = concluido_em[:10]
            ano, mes, dia_numero = data_concluido.split("-")
            dia = dia_numero
            titulo = f"{modelo_titulo} — {dia_numero}/{mes}"

        historico.append({
            "id": sessao["id"],
            "dia": dia,
            "titulo": titulo,
            "tempo": formatar_duracao_segundos(sessao.get("duracao_segundos")),
            "nota": sessao.get("nota_estimada") or 0,
            "acertos_percentual": round(sessao["percentual_acerto"]) if sessao.get("percentual_acerto") is not None else 0,
        })

    return historico


def montar_resposta_sessao(sessao_id: str, modelo: dict, id_usuario: str) -> dict:
    itens = (
        supabase_admin.table("questoes_sessao_simulado")
        .select("questao_id, area, ordem")
        .eq("sessao_simulado_id", sessao_id)
        .order("ordem")
        .execute()
        .data or []
    )
    ids_questoes = [i["questao_id"] for i in itens]

    questoes_banco = (
        supabase_admin.table("questoes")
        .select("id, materia_id, enunciado")
        .in_("id", ids_questoes)
        .execute()
        .data or []
    ) if ids_questoes else []
    questoes_por_id = {q["id"]: q for q in questoes_banco}

    alternativas = (
        supabase_admin.table("alternativas_questao")
        .select("id, questao_id, conteudo, letra, ordem")
        .in_("questao_id", ids_questoes)
        .order("ordem")
        .execute()
        .data or []
    ) if ids_questoes else []
    alternativas_por_questao: dict[str, list[dict]] = {}
    for alt in alternativas:
        alternativas_por_questao.setdefault(alt["questao_id"], []).append(alt)

    ids_materias = list({q["materia_id"] for q in questoes_banco})
    materias = (
        supabase_admin.table("materias").select("id, nome, cor").in_("id", ids_materias).execute().data or []
    ) if ids_materias else []
    materias_por_id = {m["id"]: m for m in materias}

    tentativas = (
        supabase_admin.table("tentativas_questoes")
        .select("questao_id, alternativa_escolhida")
        .eq("usuario_id", id_usuario)
        .eq("sessao_simulado_id", sessao_id)
        .execute()
        .data or []
    )
    tentativas_por_questao = {t["questao_id"]: t for t in tentativas}

    questoes_resposta = []
    for item in itens:
        questao = questoes_por_id.get(item["questao_id"])
        if not questao:
            continue

        alts = sorted(alternativas_por_questao.get(questao["id"], []), key=lambda a: a["ordem"])
        materia = materias_por_id.get(questao["materia_id"])
        tentativa = tentativas_por_questao.get(questao["id"])

        opcao_selecionada = None
        if tentativa:
            for indice, alt in enumerate(alts):
                if alt["letra"] == tentativa["alternativa_escolhida"]:
                    opcao_selecionada = indice
                    break

        questoes_resposta.append({
            "id": questao["id"],
            "area": item["area"],
            "subject": materia["nome"] if materia else "Geral",
            "subjectColor": materia["cor"] if materia else "gray",
            "question": questao["enunciado"],
            "options": [a["conteudo"] for a in alts],
            "respondida": tentativa is not None,
            "opcaoSelecionada": opcao_selecionada,
        })

    return {
        "sessao_id": sessao_id,
        "slug": modelo["slug"],
        "titulo": modelo["titulo"],
        "duracao_minutos": modelo.get("duracao_minutos") or 0,
        "total_questoes": len(questoes_resposta),
        "questoes": questoes_resposta,
    }


@router.post('/{slug}/iniciar', response_model=IniciarSimuladoResponse)
def iniciar_simulado(slug: str, usuario_atual=Depends(pegar_usuario_atual)):
    try:
        id_usuario = str(usuario_atual.id)

        modelo_resposta = (
            supabase_admin.table("modelos_simulado")
            .select("id, slug, titulo, tipo_prova_id, total_questoes, duracao_minutos")
            .eq("slug", slug)
            .eq("ativo", True)
            .limit(1)
            .execute()
        )
        if not modelo_resposta.data:
            raise HTTPException(status_code=404, detail="Simulado não encontrado")
        modelo = modelo_resposta.data[0]

        sessao_existente = (
            supabase_admin.table("sessoes_simulado")
            .select("id")
            .eq("usuario_id", id_usuario)
            .eq("modelo_simulado_id", modelo["id"])
            .eq("status", "em_andamento")
            .limit(1)
            .execute()
        )

        if sessao_existente.data:
            sessao_id = sessao_existente.data[0]["id"]
            return montar_resposta_sessao(sessao_id, modelo, id_usuario)

        pool_query = supabase_admin.table("questoes").select("id").eq("ativo", True)
        if modelo["tipo_prova_id"]:
            pool_query = pool_query.eq("tipo_prova_id", modelo["tipo_prova_id"])
        pool = [q["id"] for q in pool_query.execute().data or []]

        if not pool:
            raise HTTPException(status_code=422, detail="Não há questões suficientes para montar esse simulado")

        ids_selecionadas = selecionar_questoes(pool, modelo["total_questoes"] or len(pool))

        nova_sessao = (
            supabase_admin.table("sessoes_simulado")
            .insert({
                "usuario_id": id_usuario,
                "modelo_simulado_id": modelo["id"],
                "status": "em_andamento",
                "total_questoes": len(ids_selecionadas),
            })
            .execute()
        )
        sessao_id = nova_sessao.data[0]["id"]

        questoes_banco = (
            supabase_admin.table("questoes")
            .select("id, materia_id")
            .in_("id", ids_selecionadas)
            .execute()
            .data or []
        )
        ids_materias = list({q["materia_id"] for q in questoes_banco})
        materias = (
            supabase_admin.table("materias").select("id, area").in_("id", ids_materias).execute().data or []
        ) if ids_materias else []
        area_por_materia = {m["id"]: m["area"] for m in materias}

        itens_sessao = [
            {
                "sessao_simulado_id": sessao_id,
                "questao_id": questao["id"],
                "area": area_por_materia[questao["materia_id"]],
                "ordem": indice,
            }
            for indice, questao in enumerate(questoes_banco)
        ]
        supabase_admin.table("questoes_sessao_simulado").insert(itens_sessao).execute()

        return montar_resposta_sessao(sessao_id, modelo, id_usuario)

    except HTTPException:
        raise

    except Exception as erro:
        print(f"Erro ao iniciar simulado: {erro}")

        raise HTTPException(
            status_code=500,
            detail="Erro ao iniciar simulado"
        )


@router.patch('/sessoes/{sessao_id}/questoes/{questao_id}', response_model=ResponderQuestaoSimuladoResponse)
def responder_questao_simulado(
    sessao_id: UUID,
    questao_id: UUID,
    dados: ResponderQuestaoSimuladoPayload,
    usuario_atual=Depends(pegar_usuario_atual)
):
    try:
        id_usuario = str(usuario_atual.id)

        sessao = (
            supabase_admin.table("sessoes_simulado")
            .select("id, usuario_id, status")
            .eq("id", str(sessao_id))
            .eq("usuario_id", id_usuario)
            .limit(1)
            .execute()
        )
        if not sessao.data:
            raise HTTPException(status_code=404, detail="Sessão de simulado não encontrada")
        if sessao.data[0]["status"] != "em_andamento":
            raise HTTPException(status_code=422, detail="Sessão de simulado já finalizada")

        item = (
            supabase_admin.table("questoes_sessao_simulado")
            .select("questao_id")
            .eq("sessao_simulado_id", str(sessao_id))
            .eq("questao_id", str(questao_id))
            .limit(1)
            .execute()
        )
        if not item.data:
            raise HTTPException(status_code=404, detail="Questão não encontrada nessa sessão")

        questao = (
            supabase_admin.table("questoes")
            .select("id, alternativa_correta")
            .eq("id", str(questao_id))
            .limit(1)
            .execute()
        )
        if not questao.data:
            raise HTTPException(status_code=404, detail="Questão não encontrada")

        alternativas = (
            supabase_admin.table("alternativas_questao")
            .select("id, letra, ordem")
            .eq("questao_id", str(questao_id))
            .order("ordem")
            .execute()
            .data or []
        )
        if dados.opcao_selecionada < 0 or dados.opcao_selecionada >= len(alternativas):
            raise HTTPException(status_code=422, detail="Opção selecionada inválida")

        alternativa_escolhida = alternativas[dados.opcao_selecionada]
        correta = alternativa_escolhida["id"] == questao.data[0]["alternativa_correta"]

        existente = (
            supabase_admin.table("tentativas_questoes")
            .select("id")
            .eq("usuario_id", id_usuario)
            .eq("sessao_simulado_id", str(sessao_id))
            .eq("questao_id", str(questao_id))
            .limit(1)
            .execute()
        )

        agora = datetime.now(timezone.utc).isoformat()

        if existente.data:
            supabase_admin.table("tentativas_questoes").update({
                "alternativa_escolhida": alternativa_escolhida["letra"],
                "acertou": correta,
                "respondido_em": agora,
            }).eq("id", existente.data[0]["id"]).execute()
        else:
            supabase_admin.table("tentativas_questoes").insert({
                "usuario_id": id_usuario,
                "questao_id": str(questao_id),
                "sessao_simulado_id": str(sessao_id),
                "alternativa_escolhida": alternativa_escolhida["letra"],
                "acertou": correta,
            }).execute()

        respondidas = (
            supabase_admin.table("tentativas_questoes")
            .select("id", count="exact")
            .eq("usuario_id", id_usuario)
            .eq("sessao_simulado_id", str(sessao_id))
            .execute()
        )
        total = (
            supabase_admin.table("questoes_sessao_simulado")
            .select("id", count="exact")
            .eq("sessao_simulado_id", str(sessao_id))
            .execute()
        )

        return {
            "id": str(questao_id),
            "respondida": True,
            "correta": correta,
            "questoes_respondidas": respondidas.count or 0,
            "total_questoes": total.count or 0,
        }

    except HTTPException:
        raise

    except Exception as erro:
        print(f"Erro ao responder questão do simulado: {erro}")

        raise HTTPException(
            status_code=500,
            detail="Erro ao responder questão do simulado"
        )


@router.post('/sessoes/{sessao_id}/finalizar', response_model=FinalizarSimuladoResponse)
def finalizar_simulado(sessao_id: UUID, usuario_atual=Depends(pegar_usuario_atual)):
    try:
        id_usuario = str(usuario_atual.id)
        agora = datetime.now(timezone.utc)

        sessao_resposta = (
            supabase_admin.table("sessoes_simulado")
            .select("id, usuario_id, status, iniciado_em")
            .eq("id", str(sessao_id))
            .eq("usuario_id", id_usuario)
            .limit(1)
            .execute()
        )
        if not sessao_resposta.data:
            raise HTTPException(status_code=404, detail="Sessão de simulado não encontrada")
        sessao = sessao_resposta.data[0]
        if sessao["status"] != "em_andamento":
            raise HTTPException(status_code=422, detail="Sessão de simulado já finalizada")

        itens = (
            supabase_admin.table("questoes_sessao_simulado")
            .select("questao_id, area")
            .eq("sessao_simulado_id", str(sessao_id))
            .execute()
            .data or []
        )
        area_por_questao = {i["questao_id"]: i["area"] for i in itens}

        tentativas = (
            supabase_admin.table("tentativas_questoes")
            .select("questao_id, acertou")
            .eq("usuario_id", id_usuario)
            .eq("sessao_simulado_id", str(sessao_id))
            .execute()
            .data or []
        )

        respostas = [bool(t["acertou"]) for t in tentativas]
        resultado = calcular_resultado(respostas)

        respostas_por_area: dict[str, list[bool]] = {}
        for tentativa in tentativas:
            area = area_por_questao.get(tentativa["questao_id"])
            if area:
                respostas_por_area.setdefault(area, []).append(bool(tentativa["acertou"]))
        resultados_area = calcular_resultado_por_area(respostas_por_area)

        iniciado_em = datetime.fromisoformat(sessao["iniciado_em"])
        duracao_segundos = max(0, int((agora - iniciado_em).total_seconds()))

        supabase_admin.table("sessoes_simulado").update({
            "status": "concluido",
            "concluido_em": agora.isoformat(),
            "duracao_segundos": duracao_segundos,
            "total_questoes": resultado["total_questoes"],
            "respostas_corretas": resultado["respostas_corretas"],
            "percentual_acerto": resultado["percentual_acerto"],
            "nota_estimada": resultado["nota_estimada"],
            "atualizado_em": agora.isoformat(),
        }).eq("id", str(sessao_id)).execute()

        if resultados_area:
            supabase_admin.table("resultados_area_simulado").insert([
                {"sessao_simulado_id": str(sessao_id), **area_resultado}
                for area_resultado in resultados_area
            ]).execute()

        conceder_xp_e_atividade(
            id_usuario, 20, minutos_estudo=duracao_segundos // 60, agora=agora, simulados_concluidos=1
        )
        registrar_evento_gamificacao(id_usuario, EventoGamificacao.SIMULADO_CONCLUIDO)

        return {
            "id": str(sessao_id),
            "status": "concluido",
            "total_questoes": resultado["total_questoes"],
            "respostas_corretas": resultado["respostas_corretas"],
            "percentual_acerto": resultado["percentual_acerto"],
            "nota_estimada": resultado["nota_estimada"],
            "duracao": formatar_duracao_segundos(duracao_segundos),
            "resultados_por_area": resultados_area,
        }

    except HTTPException:
        raise

    except Exception as erro:
        print(f"Erro ao finalizar simulado: {erro}")

        raise HTTPException(
            status_code=500,
            detail="Erro ao finalizar simulado"
        )


@router.get('', response_model=SimuladosResponse)
def obter_simulados(usuario_atual=Depends(pegar_usuario_atual)):
    try:
        id_usuario = str(usuario_atual.id)

        return {
            "resumo": montar_resumo(id_usuario),
            "catalogo": montar_catalogo(),
            "historico": montar_historico(id_usuario),
        }

    except Exception as erro:
        print(f"Erro ao obter simulados: {erro}")

        raise HTTPException(
            status_code=500,
            detail="Erro ao obter simulados"
        )
