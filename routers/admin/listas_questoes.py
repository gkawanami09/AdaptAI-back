from fastapi import APIRouter, HTTPException, Depends, Query
from database import supabase_admin
from uuid import UUID
from utils.autenticacao import exigir_administrador
from utils.textos import gerar_slug
from schemas.questoes_schema import (
    ListaQuestoesCriar,
    ListaQuestoesEditar,
    ItemListaAdicionar,
    ItensListaReordenarLote,
)

router = APIRouter(
    prefix='/admin/listas-questoes',
    tags=['Admin - Listas de Questões'],
    dependencies=[Depends(exigir_administrador)]
)


# Busca a lista com seus itens (questao_id + ordem)
def montar_lista(lista_id: UUID):
    resposta = (
        supabase_admin.table("listas_questoes")
        .select("*")
        .eq("id", str(lista_id))
        .limit(1)
        .execute()
    )

    if not resposta.data:
        return None

    lista = resposta.data[0]

    itens = (
        supabase_admin.table("itens_lista_questoes")
        .select("*")
        .eq("lista_questoes_id", str(lista_id))
        .order("ordem")
        .execute()
        .data or []
    )

    lista["itens"] = [
        {
            "questao_id": item["questao_id"],
            "ordem": item["ordem"],
        }
        for item in itens
    ]

    return lista


# Insere os itens de uma lista
def salvar_itens(lista_id: UUID, itens: list):
    for item in itens:
        supabase_admin.table("itens_lista_questoes").insert({
            "lista_questoes_id": str(lista_id),
            "questao_id": str(item.questao_id),
            "ordem": item.ordem,
        }).execute()


# Remove todos os itens de uma lista
def excluir_itens(lista_id: UUID):
    supabase_admin.table("itens_lista_questoes").delete().eq(
        "lista_questoes_id", str(lista_id)
    ).execute()


# Gera um slug único para a lista a partir do título
def gerar_slug_unico(titulo: str, lista_id: UUID | None = None):
    slug_base = gerar_slug(titulo)
    slug = slug_base
    sufixo = 1

    while True:
        consulta = (
            supabase_admin.table("listas_questoes")
            .select("id")
            .eq("slug", slug)
        )
        if lista_id:
            consulta = consulta.neq("id", str(lista_id))

        if not consulta.limit(1).execute().data:
            return slug

        sufixo += 1
        slug = f"{slug_base}-{sufixo}"


def filtrar_listas(consulta, busca, materia_id, tipo_lista):
    if busca:
        consulta = consulta.ilike("titulo", f"%{busca.strip()}%")
    if materia_id:
        consulta = consulta.eq("materia_id", str(materia_id))
    if tipo_lista:
        consulta = consulta.eq("tipo_lista", tipo_lista)
    return consulta


@router.get("")
def listar_listas(
    busca: str | None = None,
    materia_id: UUID | None = None,
    tipo_lista: str | None = None,
    pagina: int = Query(default=1, ge=1),
    limite: int = Query(default=6, ge=1, le=50),
    ordenar: str | None = None,
):
    try:
        inicio = (pagina - 1) * limite
        fim = inicio + limite - 1

        consulta = filtrar_listas(
            supabase_admin.table("listas_questoes").select("*", count="exact"),
            busca, materia_id, tipo_lista
        )

        if ordenar == "titulo-az":
            consulta = consulta.order("titulo")
        elif ordenar == "titulo-za":
            consulta = consulta.order("titulo", desc=True)
        else:
            consulta = consulta.order("criado_em", desc=True)

        resposta = consulta.range(inicio, fim).execute()
        listas = resposta.data or []
        total_registros = resposta.count or 0
        total_paginas = max(1, (total_registros + limite - 1) // limite)

        ids_listas = [lista["id"] for lista in listas]
        itens = (
            supabase_admin.table("itens_lista_questoes")
            .select("lista_questoes_id")
            .in_("lista_questoes_id", ids_listas)
            .execute()
            .data or []
        ) if ids_listas else []

        for lista in listas:
            lista["total_questoes"] = sum(
                1 for item in itens if item["lista_questoes_id"] == lista["id"]
            )

        return {
            "sucesso": True,
            "pagina": pagina,
            "limite": limite,
            "total_registros": total_registros,
            "total_paginas": total_paginas,
            "total_listas": total_registros,
            "listas": listas,
        }

    except Exception as erro:
        print(f"Erro ao listar listas de questões: {erro}")
        raise HTTPException(
            status_code=500,
            detail="Erro ao listar listas de questões"
        )


@router.get('/{lista_id}')
def buscar_lista(lista_id: UUID):
    try:
        lista = montar_lista(lista_id)

        if not lista:
            raise HTTPException(
                status_code=404,
                detail="Lista de questões não encontrada"
            )

        return {
            "sucesso": True,
            "lista": lista
        }

    except HTTPException:
        raise

    except Exception as erro:
        print(f"Erro ao buscar lista de questões: {erro}")
        raise HTTPException(
            status_code=500,
            detail="Erro ao buscar lista de questões"
        )


@router.post('')
def criar_lista(dados: ListaQuestoesCriar):
    try:
        nova_lista = dados.model_dump(exclude={"itens"})
        nova_lista["tipo_prova_id"] = str(dados.tipo_prova_id) if dados.tipo_prova_id else None
        nova_lista["materia_id"] = str(dados.materia_id) if dados.materia_id else None
        nova_lista["topico_id"] = str(dados.topico_id) if dados.topico_id else None
        nova_lista["titulo"] = dados.titulo.strip()
        nova_lista["slug"] = gerar_slug_unico(nova_lista["titulo"])

        resposta = (
            supabase_admin.table("listas_questoes")
            .insert(nova_lista)
            .execute()
        )

        if not resposta.data:
            raise HTTPException(
                status_code=500,
                detail="Não foi possível criar a lista de questões"
            )

        lista_id = resposta.data[0]["id"]

        if dados.itens:
            salvar_itens(lista_id, dados.itens)

        return {
            "sucesso": True,
            "mensagem": "Lista de questões criada com sucesso",
            "lista": montar_lista(lista_id)
        }

    except HTTPException:
        raise

    except Exception as erro:
        print(f"Erro ao criar lista de questões: {erro}")
        raise HTTPException(
            status_code=500,
            detail="Erro ao criar lista de questões"
        )


@router.patch('/{lista_id}')
def editar_lista(lista_id: UUID, dados: ListaQuestoesEditar):
    try:
        resposta_existente = (
            supabase_admin.table("listas_questoes")
            .select("id")
            .eq("id", str(lista_id))
            .limit(1)
            .execute()
        )

        if not resposta_existente.data:
            raise HTTPException(
                status_code=404,
                detail="Lista de questões não encontrada"
            )

        alteracoes = dados.model_dump(exclude_unset=True, exclude={"itens"})

        if not alteracoes and dados.itens is None:
            raise HTTPException(
                status_code=400,
                detail="Nenhuma alteração foi enviada"
            )

        if "titulo" in alteracoes:
            alteracoes["titulo"] = alteracoes["titulo"].strip()
            alteracoes["slug"] = gerar_slug_unico(alteracoes["titulo"], lista_id)

        if "tipo_prova_id" in alteracoes and alteracoes["tipo_prova_id"] is not None:
            alteracoes["tipo_prova_id"] = str(alteracoes["tipo_prova_id"])

        if "materia_id" in alteracoes and alteracoes["materia_id"] is not None:
            alteracoes["materia_id"] = str(alteracoes["materia_id"])

        if "topico_id" in alteracoes and alteracoes["topico_id"] is not None:
            alteracoes["topico_id"] = str(alteracoes["topico_id"])

        if alteracoes:
            supabase_admin.table("listas_questoes").update(alteracoes).eq(
                "id", str(lista_id)
            ).execute()

        if dados.itens is not None:
            excluir_itens(lista_id)
            salvar_itens(lista_id, dados.itens)

        return {
            "sucesso": True,
            "mensagem": "Lista de questões atualizada com sucesso",
            "lista": montar_lista(lista_id)
        }

    except HTTPException:
        raise

    except Exception as erro:
        print(f"Erro ao atualizar lista de questões: {erro}")
        raise HTTPException(
            status_code=500,
            detail="Erro ao atualizar lista de questões"
        )


@router.delete('/{lista_id}')
def excluir_lista(lista_id: UUID):
    try:
        resposta = (
            supabase_admin.table("listas_questoes")
            .select("id")
            .eq("id", str(lista_id))
            .limit(1)
            .execute()
        )

        if not resposta.data:
            raise HTTPException(
                status_code=404,
                detail="Lista de questões não encontrada"
            )

        excluir_itens(lista_id)

        supabase_admin.table("listas_questoes").delete().eq("id", str(lista_id)).execute()

        return {
            "sucesso": True,
            "mensagem": "Lista de questões excluída com sucesso"
        }

    except HTTPException:
        raise

    except Exception as erro:
        print(f"Erro ao excluir lista de questões: {erro}")
        raise HTTPException(
            status_code=500,
            detail="Erro ao excluir lista de questões"
        )


@router.post('/{lista_id}/itens')
def adicionar_item(lista_id: UUID, dados: ItemListaAdicionar):
    try:
        resposta_lista = (
            supabase_admin.table("listas_questoes")
            .select("id")
            .eq("id", str(lista_id))
            .limit(1)
            .execute()
        )

        if not resposta_lista.data:
            raise HTTPException(
                status_code=404,
                detail="Lista de questões não encontrada"
            )

        resposta_questao = (
            supabase_admin.table("questoes")
            .select("id")
            .eq("id", str(dados.questao_id))
            .limit(1)
            .execute()
        )

        if not resposta_questao.data:
            raise HTTPException(
                status_code=404,
                detail="Questão não encontrada"
            )

        resposta_item = (
            supabase_admin.table("itens_lista_questoes")
            .select("id")
            .eq("lista_questoes_id", str(lista_id))
            .eq("questao_id", str(dados.questao_id))
            .limit(1)
            .execute()
        )

        if resposta_item.data:
            raise HTTPException(
                status_code=409,
                detail="Essa questão já está nessa lista"
            )

        supabase_admin.table("itens_lista_questoes").insert({
            "lista_questoes_id": str(lista_id),
            "questao_id": str(dados.questao_id),
            "ordem": dados.ordem,
        }).execute()

        return {
            "sucesso": True,
            "mensagem": "Questão adicionada à lista com sucesso",
            "lista": montar_lista(lista_id)
        }

    except HTTPException:
        raise

    except Exception as erro:
        print(f"Erro ao adicionar questão à lista: {erro}")
        raise HTTPException(
            status_code=500,
            detail="Erro ao adicionar questão à lista"
        )


@router.delete('/{lista_id}/itens/{questao_id}')
def remover_item(lista_id: UUID, questao_id: UUID):
    try:
        resposta = (
            supabase_admin.table("itens_lista_questoes")
            .select("id")
            .eq("lista_questoes_id", str(lista_id))
            .eq("questao_id", str(questao_id))
            .limit(1)
            .execute()
        )

        if not resposta.data:
            raise HTTPException(
                status_code=404,
                detail="Questão não encontrada nessa lista"
            )

        supabase_admin.table("itens_lista_questoes").delete().eq(
            "lista_questoes_id", str(lista_id)
        ).eq("questao_id", str(questao_id)).execute()

        return {
            "sucesso": True,
            "mensagem": "Questão removida da lista com sucesso",
            "lista": montar_lista(lista_id)
        }

    except HTTPException:
        raise

    except Exception as erro:
        print(f"Erro ao remover questão da lista: {erro}")
        raise HTTPException(
            status_code=500,
            detail="Erro ao remover questão da lista"
        )


@router.patch('/{lista_id}/itens/ordem')
def reordenar_itens(lista_id: UUID, dados: ItensListaReordenarLote):
    try:
        resposta_lista = (
            supabase_admin.table("listas_questoes")
            .select("id")
            .eq("id", str(lista_id))
            .limit(1)
            .execute()
        )

        if not resposta_lista.data:
            raise HTTPException(
                status_code=404,
                detail="Lista de questões não encontrada"
            )

        for item in dados.itens:
            resposta = (
                supabase_admin.table("itens_lista_questoes")
                .update({"ordem": item.ordem})
                .eq("lista_questoes_id", str(lista_id))
                .eq("questao_id", str(item.questao_id))
                .execute()
            )

            if not resposta.data:
                raise HTTPException(
                    status_code=404,
                    detail=f"Questão {item.questao_id} não encontrada nessa lista"
                )

        return {
            "sucesso": True,
            "mensagem": "Ordem da lista atualizada com sucesso",
            "lista": montar_lista(lista_id)
        }

    except HTTPException:
        raise

    except Exception as erro:
        print(f"Erro ao reordenar itens da lista: {erro}")
        raise HTTPException(
            status_code=500,
            detail="Erro ao reordenar itens da lista"
        )
