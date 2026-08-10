from fastapi import APIRouter, HTTPException, Depends
from database import supabase_admin
from uuid import UUID
from datetime import datetime, timezone
from utils.autenticacao import pegar_usuario_atual
from schemas.visualizacao_questoes_schema import (
    ListaQuestoesVisualizacaoResponse,
    ResponderQuestaoPayload,
    ResponderQuestaoResponse,
    FavoritarQuestaoResponse,
    FinalizarListaResponse,
)
from services.gamificacao import EventoGamificacao, registrar_evento_gamificacao
from services.gamificacao.metricas import TIPOS_LISTA_REVISAO

router = APIRouter(
    prefix='/aluno/questoes',
    tags=['Aluno - Visualização de Questões']
)

DIFICULDADE_LABEL = {
    "facil": "Fácil",
    "medio": "Médio",
    "dificil": "Difícil",
}

DIFICULDADE_COR = {
    "facil": "teal",
    "medio": "blue",
    "dificil": "red",
}


def buscar_lista_por_slug(slug: str, usuario_id: str):
    resposta = (
        supabase_admin.table("listas_questoes")
        .select("id, usuario_id, slug, titulo, materia_id, tipo_prova_id, dificuldade, tipo_lista")
        .eq("slug", slug)
        .limit(1)
        .execute()
    )

    if not resposta.data:
        raise HTTPException(status_code=404, detail="Lista de questões não encontrada")

    lista = resposta.data[0]

    if lista["usuario_id"] and lista["usuario_id"] != usuario_id:
        raise HTTPException(status_code=403, detail="Lista não pertence ao aluno autenticado")

    return lista


def buscar_itens_lista(lista_id: str):
    return (
        supabase_admin.table("itens_lista_questoes")
        .select("questao_id, ordem")
        .eq("lista_questoes_id", lista_id)
        .order("ordem")
        .execute()
        .data or []
    )


def obter_progresso(usuario_id: str, lista_id: str):
    resposta = (
        supabase_admin.table("progresso_lista_questoes_aluno")
        .select("id, status")
        .eq("usuario_id", usuario_id)
        .eq("lista_questoes_id", lista_id)
        .limit(1)
        .execute()
    )
    return resposta.data[0] if resposta.data else None


def garantir_progresso(usuario_id: str, lista_id: str):
    progresso = obter_progresso(usuario_id, lista_id)

    if progresso:
        return progresso

    nova = (
        supabase_admin.table("progresso_lista_questoes_aluno")
        .insert({
            "usuario_id": usuario_id,
            "lista_questoes_id": lista_id,
            "status": "em_andamento",
        })
        .execute()
    )
    return nova.data[0]


def calcular_progresso(usuario_id: str, lista_id: str, ids_questoes: list[str]):
    total = len(ids_questoes)

    respostas = (
        supabase_admin.table("respostas_lista_questoes_aluno")
        .select("questao_id")
        .eq("usuario_id", usuario_id)
        .eq("lista_questoes_id", lista_id)
        .execute()
        .data or []
    ) if ids_questoes else []

    concluidas = len(respostas)
    percentual = round((concluidas / total) * 100) if total > 0 else 0

    return concluidas, percentual


@router.get('/{slug}', response_model=ListaQuestoesVisualizacaoResponse)
def obter_lista_questoes(slug: str, usuario_atual=Depends(pegar_usuario_atual)):
    try:
        id_usuario = str(usuario_atual.id)
        lista = buscar_lista_por_slug(slug, id_usuario)

        materia_nome = "Geral"
        materia_cor = "gray"

        if lista["materia_id"]:
            materia = (
                supabase_admin.table("materias")
                .select("nome, cor")
                .eq("id", lista["materia_id"])
                .limit(1)
                .execute()
            )

            if materia.data:
                materia_nome = materia.data[0]["nome"]
                materia_cor = materia.data[0]["cor"]

        vestibular_nome = "Geral"
        if lista["tipo_prova_id"]:
            tipo_prova = (
                supabase_admin.table("tipos_prova")
                .select("nome")
                .eq("id", lista["tipo_prova_id"])
                .limit(1)
                .execute()
            )
            if tipo_prova.data:
                vestibular_nome = tipo_prova.data[0]["nome"]

        itens = buscar_itens_lista(lista["id"])
        ids_questoes = [item["questao_id"] for item in itens]

        questoes_banco = (
            supabase_admin.table("questoes")
            .select("id, materia_id, tipo_prova_id, ano, dificuldade, enunciado, dica, alternativa_correta")
            .in_("id", ids_questoes)
            .execute()
            .data or []
        ) if ids_questoes else []
        questoes_por_id = {q["id"]: q for q in questoes_banco}

        alternativas = (
            supabase_admin.table("alternativas_questao")
            .select("id, questao_id, conteudo, ordem")
            .in_("questao_id", ids_questoes)
            .order("ordem")
            .execute()
            .data or []
        ) if ids_questoes else []

        alternativas_por_questao: dict[str, list[dict]] = {}
        for alt in alternativas:
            alternativas_por_questao.setdefault(alt["questao_id"], []).append(alt)

        respostas = (
            supabase_admin.table("respostas_lista_questoes_aluno")
            .select("questao_id, alternativa_selecionada_id, correta")
            .eq("usuario_id", id_usuario)
            .eq("lista_questoes_id", lista["id"])
            .execute()
            .data or []
        ) if ids_questoes else []
        respostas_por_questao = {r["questao_id"]: r for r in respostas}

        favoritas = (
            supabase_admin.table("questoes_favoritas")
            .select("questao_id")
            .eq("usuario_id", id_usuario)
            .in_("questao_id", ids_questoes)
            .execute()
            .data or []
        ) if ids_questoes else []
        ids_favoritas = {f["questao_id"] for f in favoritas}

        materias_das_questoes = {q["materia_id"] for q in questoes_banco}
        materias_banco = (
            supabase_admin.table("materias")
            .select("id, nome, cor")
            .in_("id", list(materias_das_questoes))
            .execute()
            .data or []
        ) if materias_das_questoes else []
        materias_por_id = {m["id"]: m for m in materias_banco}

        tipos_prova_das_questoes = {q["tipo_prova_id"] for q in questoes_banco if q["tipo_prova_id"]}
        tipos_prova_banco = (
            supabase_admin.table("tipos_prova")
            .select("id, nome")
            .in_("id", list(tipos_prova_das_questoes))
            .execute()
            .data or []
        ) if tipos_prova_das_questoes else []
        tipos_prova_por_id = {t["id"]: t for t in tipos_prova_banco}

        questoes_resposta = []
        for item in itens:
            questao = questoes_por_id.get(item["questao_id"])
            if not questao:
                continue

            alts_ordenadas = sorted(
                alternativas_por_questao.get(questao["id"], []),
                key=lambda a: a["ordem"]
            )

            materia_questao = materias_por_id.get(questao["materia_id"])
            tipo_prova_questao = tipos_prova_por_id.get(questao["tipo_prova_id"])

            vestibular_label = tipo_prova_questao["nome"] if tipo_prova_questao else vestibular_nome
            ano_label = f" {questao['ano']}" if questao.get("ano") else ""
            dificuldade_label = DIFICULDADE_LABEL.get(questao["dificuldade"], questao["dificuldade"])

            resposta = respostas_por_questao.get(questao["id"])
            opcao_selecionada = None
            if resposta:
                for indice, alt in enumerate(alts_ordenadas):
                    if alt["id"] == resposta["alternativa_selecionada_id"]:
                        opcao_selecionada = indice
                        break

            questoes_resposta.append({
                "id": questao["id"],
                "subject": materia_questao["nome"] if materia_questao else materia_nome,
                "subjectColor": materia_questao["cor"] if materia_questao else materia_cor,
                "examInfo": f"{vestibular_label}{ano_label} · {dificuldade_label}",
                "question": questao["enunciado"],
                "options": [alt["conteudo"] for alt in alts_ordenadas],
                "hint": questao.get("dica"),
                "respondida": resposta is not None,
                "opcaoSelecionada": opcao_selecionada,
                "correta": resposta["correta"] if resposta else None,
                "favorita": questao["id"] in ids_favoritas,
            })

        progresso = obter_progresso(id_usuario, lista["id"])
        status = progresso["status"] if progresso else "em_andamento"
        concluidas, percentual = calcular_progresso(id_usuario, lista["id"], ids_questoes)

        return {
            "slug": lista["slug"],
            "titulo": lista["titulo"],
            "materia": materia_nome,
            "dificuldade": DIFICULDADE_LABEL.get(lista["dificuldade"], lista["dificuldade"] or "Médio"),
            "vestibular": vestibular_nome,
            "status": status,
            "questoes_totais": len(itens),
            "questoes_concluidas": concluidas,
            "progresso_percentual": percentual,
            "questoes": questoes_resposta,
        }

    except HTTPException:
        raise

    except Exception as erro:
        print(f"Erro ao obter lista de questões: {erro}")

        raise HTTPException(
            status_code=500,
            detail="Erro ao obter lista de questões"
        )


@router.patch('/{slug}/questoes/{questao_id}', response_model=ResponderQuestaoResponse)
def responder_questao(
    slug: str,
    questao_id: UUID,
    dados: ResponderQuestaoPayload,
    usuario_atual=Depends(pegar_usuario_atual)
):
    try:
        id_usuario = str(usuario_atual.id)
        lista = buscar_lista_por_slug(slug, id_usuario)

        item = (
            supabase_admin.table("itens_lista_questoes")
            .select("questao_id")
            .eq("lista_questoes_id", lista["id"])
            .eq("questao_id", str(questao_id))
            .limit(1)
            .execute()
        )

        if not item.data:
            raise HTTPException(status_code=404, detail="Questão não encontrada nessa lista")

        progresso = obter_progresso(id_usuario, lista["id"])
        if progresso and progresso["status"] == "finalizada":
            raise HTTPException(status_code=422, detail="Lista já finalizada")

        questao = (
            supabase_admin.table("questoes")
            .select("id, alternativa_correta, materia_id")
            .eq("id", str(questao_id))
            .limit(1)
            .execute()
        )

        if not questao.data:
            raise HTTPException(status_code=404, detail="Questão não encontrada")

        alternativas = (
            supabase_admin.table("alternativas_questao")
            .select("id, ordem")
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
            supabase_admin.table("respostas_lista_questoes_aluno")
            .select("id")
            .eq("usuario_id", id_usuario)
            .eq("lista_questoes_id", lista["id"])
            .eq("questao_id", str(questao_id))
            .limit(1)
            .execute()
        )

        agora = datetime.now(timezone.utc).isoformat()

        if existente.data:
            supabase_admin.table("respostas_lista_questoes_aluno").update({
                "alternativa_selecionada_id": alternativa_escolhida["id"],
                "correta": correta,
                "respondido_em": agora,
            }).eq("id", existente.data[0]["id"]).execute()
        else:
            supabase_admin.table("respostas_lista_questoes_aluno").insert({
                "usuario_id": id_usuario,
                "lista_questoes_id": lista["id"],
                "questao_id": str(questao_id),
                "alternativa_selecionada_id": alternativa_escolhida["id"],
                "correta": correta,
            }).execute()

        garantir_progresso(id_usuario, lista["id"])

        materia_id = questao.data[0]["materia_id"]
        registrar_evento_gamificacao(id_usuario, EventoGamificacao.QUESTAO_RESPONDIDA)
        if correta:
            registrar_evento_gamificacao(
                id_usuario, EventoGamificacao.QUESTAO_ACERTADA, {"materia_id": materia_id}
            )
            if lista.get("tipo_lista") in TIPOS_LISTA_REVISAO:
                registrar_evento_gamificacao(id_usuario, EventoGamificacao.REVISAO_QUESTAO_CONCLUIDA)

        itens = buscar_itens_lista(lista["id"])
        ids_questoes = [i["questao_id"] for i in itens]
        concluidas, percentual = calcular_progresso(id_usuario, lista["id"], ids_questoes)

        return {
            "id": str(questao_id),
            "respondida": True,
            "opcaoSelecionada": dados.opcao_selecionada,
            "correta": correta,
            "questoes_concluidas": concluidas,
            "progresso_percentual": percentual,
        }

    except HTTPException:
        raise

    except Exception as erro:
        print(f"Erro ao responder questão: {erro}")

        raise HTTPException(
            status_code=500,
            detail="Erro ao responder questão"
        )


@router.patch('/favoritos/{questao_id}', response_model=FavoritarQuestaoResponse)
def alternar_favorito(questao_id: UUID, usuario_atual=Depends(pegar_usuario_atual)):
    try:
        id_usuario = str(usuario_atual.id)

        questao = (
            supabase_admin.table("questoes")
            .select("id")
            .eq("id", str(questao_id))
            .limit(1)
            .execute()
        )

        if not questao.data:
            raise HTTPException(status_code=404, detail="Questão não encontrada")

        existente = (
            supabase_admin.table("questoes_favoritas")
            .select("id")
            .eq("usuario_id", id_usuario)
            .eq("questao_id", str(questao_id))
            .limit(1)
            .execute()
        )

        if existente.data:
            supabase_admin.table("questoes_favoritas").delete().eq(
                "id", existente.data[0]["id"]
            ).execute()
            favorita = False
        else:
            supabase_admin.table("questoes_favoritas").insert({
                "usuario_id": id_usuario,
                "questao_id": str(questao_id),
            }).execute()
            favorita = True

        return {
            "id": str(questao_id),
            "favorita": favorita,
        }

    except HTTPException:
        raise

    except Exception as erro:
        print(f"Erro ao alternar favorito da questão: {erro}")

        raise HTTPException(
            status_code=500,
            detail="Erro ao alternar favorito da questão"
        )


@router.post('/{slug}/finalizar', response_model=FinalizarListaResponse)
def finalizar_lista(slug: str, usuario_atual=Depends(pegar_usuario_atual)):
    try:
        id_usuario = str(usuario_atual.id)
        lista = buscar_lista_por_slug(slug, id_usuario)

        itens = buscar_itens_lista(lista["id"])
        ids_questoes = [item["questao_id"] for item in itens]
        concluidas, percentual = calcular_progresso(id_usuario, lista["id"], ids_questoes)

        progresso = garantir_progresso(id_usuario, lista["id"])

        if progresso["status"] == "finalizada":
            return {
                "status": "finalizada",
                "progresso_percentual": percentual,
                "questoes_concluidas": concluidas,
                "questoes_totais": len(ids_questoes),
            }

        if concluidas < len(ids_questoes):
            raise HTTPException(
                status_code=422,
                detail="Existem questões pendentes de resposta"
            )

        agora = datetime.now(timezone.utc).isoformat()
        supabase_admin.table("progresso_lista_questoes_aluno").update({
            "status": "finalizada",
            "concluido_em": agora,
            "atualizado_em": agora,
        }).eq("id", progresso["id"]).execute()

        return {
            "status": "finalizada",
            "progresso_percentual": percentual,
            "questoes_concluidas": concluidas,
            "questoes_totais": len(ids_questoes),
        }

    except HTTPException:
        raise

    except Exception as erro:
        print(f"Erro ao finalizar lista de questões: {erro}")

        raise HTTPException(
            status_code=500,
            detail="Erro ao finalizar lista de questões"
        )
