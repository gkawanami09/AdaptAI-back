from fastapi import APIRouter, HTTPException, Depends, Query
from database import supabase_admin
from uuid import UUID
from utils.autenticacao import exigir_administrador
from schemas.questoes_schema import QuestaoCriar, QuestaoEditar

router = APIRouter(
    prefix='/admin/questoes',
    tags=['Admin - Questões'],
    dependencies=[Depends(exigir_administrador)]
)


# Busca a questão com suas alternativas já formatadas
def montar_questao(questao_id: UUID):
    resposta = (
        supabase_admin.table("questoes")
        .select("*")
        .eq("id", str(questao_id))
        .limit(1)
        .execute()
    )

    if not resposta.data:
        return None

    questao = resposta.data[0]

    alternativas = (
        supabase_admin.table("alternativas_questao")
        .select("*")
        .eq("questao_id", str(questao_id))
        .order("ordem")
        .execute()
        .data or []
    )

    questao["alternativas"] = [
        {
            "id": alt["id"],
            "letra": alt["letra"],
            "texto": alt["conteudo"],
            "correta": alt["id"] == questao["alternativa_correta"],
        }
        for alt in alternativas
    ]

    return questao


# Cria as alternativas de uma questão e define a alternativa_correta na questão
def salvar_alternativas(questao_id: UUID, alternativas: list):
    id_correta = None

    for indice, alternativa in enumerate(alternativas):
        resposta = (
            supabase_admin.table("alternativas_questao")
            .insert({
                "questao_id": str(questao_id),
                "letra": alternativa.letra,
                "conteudo": alternativa.texto,
                "ordem": indice,
            })
            .execute()
        )

        if alternativa.correta:
            id_correta = resposta.data[0]["id"]

    supabase_admin.table("questoes").update(
        {"alternativa_correta": id_correta}
    ).eq("id", str(questao_id)).execute()


# Remove todas as alternativas de uma questão
def excluir_alternativas(questao_id: UUID):
    supabase_admin.table("alternativas_questao").delete().eq("questao_id", str(questao_id)).execute()


# Aplica os filtros comuns de listagem de questões
def filtrar_questoes(consulta, busca, materia_id, dificuldade, ativo):
    if busca:
        consulta = consulta.ilike("enunciado", f"%{busca.strip()}%")
    if materia_id:
        consulta = consulta.eq("materia_id", str(materia_id))
    if dificuldade:
        consulta = consulta.eq("dificuldade", dificuldade)
    if ativo is not None:
        consulta = consulta.eq("ativo", ativo)
    return consulta


@router.get("")
def listar_questoes(
    busca: str | None = None,
    materia_id: UUID | None = None,
    dificuldade: str | None = None,
    ativo: bool | None = None,
    pagina: int = Query(default=1, ge=1),
    limite: int = Query(default=6, ge=1, le=50),
    ordenar: str | None = None,
):
    try:
        inicio = (pagina - 1) * limite
        fim = inicio + limite - 1

        consulta = filtrar_questoes(
            supabase_admin.table("questoes").select("*", count="exact"),
            busca, materia_id, dificuldade, ativo
        )

        if ordenar == "enunciado-az":
            consulta = consulta.order("enunciado")
        elif ordenar == "enunciado-za":
            consulta = consulta.order("enunciado", desc=True)
        else:
            consulta = consulta.order("criado_em", desc=True)

        resposta = consulta.range(inicio, fim).execute()
        questoes = resposta.data or []
        total_registros = resposta.count or 0
        total_paginas = max(1, (total_registros + limite - 1) // limite)

        stats = filtrar_questoes(
            supabase_admin.table("questoes").select("id, ativo"),
            busca, materia_id, dificuldade, ativo
        ).execute().data or []

        total_publicadas = sum(1 for questao in stats if questao["ativo"])
        total_inativas = len(stats) - total_publicadas

        ids_questoes_stats = [questao["id"] for questao in stats]
        alternativas = (
            supabase_admin.table("alternativas_questao")
            .select("questao_id")
            .in_("questao_id", ids_questoes_stats)
            .execute()
            .data or []
        ) if ids_questoes_stats else []

        total_alternativas = len(alternativas)

        for questao in questoes:
            questao["total_alternativas"] = sum(
                1 for alt in alternativas if alt["questao_id"] == questao["id"]
            )

        return {
            "sucesso": True,
            "pagina": pagina,
            "limite": limite,
            "total_registros": total_registros,
            "total_paginas": total_paginas,
            "total_questoes": total_registros,
            "total_publicadas": total_publicadas,
            "total_inativas": total_inativas,
            "total_alternativas": total_alternativas,
            "questoes": questoes,
        }

    except Exception as erro:
        print(f"Erro ao listar questões: {erro}")
        raise HTTPException(
            status_code=500,
            detail="Erro ao listar questões"
        )


@router.get('/{questao_id}')
def buscar_questao(questao_id: UUID):
    try:
        questao = montar_questao(questao_id)

        if not questao:
            raise HTTPException(
                status_code=404,
                detail="Questão não encontrada"
            )

        return {
            "sucesso": True,
            "questao": questao
        }

    except HTTPException:
        raise

    except Exception as erro:
        print(f"Erro ao buscar questão: {erro}")
        raise HTTPException(
            status_code=500,
            detail="Erro ao buscar questão"
        )


@router.post('')
def criar_questao(dados: QuestaoCriar):
    try:
        resposta_materia = (
            supabase_admin.table("materias")
            .select("id")
            .eq("id", str(dados.materia_id))
            .limit(1)
            .execute()
        )

        if not resposta_materia.data:
            raise HTTPException(
                status_code=404,
                detail="Matéria não encontrada"
            )

        nova_questao = dados.model_dump(exclude={"alternativas"})
        nova_questao["materia_id"] = str(dados.materia_id)
        nova_questao["topico_id"] = str(dados.topico_id) if dados.topico_id else None
        nova_questao["tipo_prova_id"] = str(dados.tipo_prova_id) if dados.tipo_prova_id else None
        nova_questao["aula_id"] = str(dados.aula_id) if dados.aula_id else None
        nova_questao["alternativa_correta"] = None

        resposta = (
            supabase_admin.table("questoes")
            .insert(nova_questao)
            .execute()
        )

        if not resposta.data:
            raise HTTPException(
                status_code=500,
                detail="Não foi possível criar a questão"
            )

        questao_id = resposta.data[0]["id"]

        salvar_alternativas(questao_id, dados.alternativas)

        return {
            "sucesso": True,
            "mensagem": "Questão criada com sucesso",
            "questao": montar_questao(questao_id)
        }

    except HTTPException:
        raise

    except Exception as erro:
        print(f"Erro ao criar questão: {erro}")
        raise HTTPException(
            status_code=500,
            detail="Erro ao criar questão"
        )


@router.patch('/{questao_id}')
def editar_questao(questao_id: UUID, dados: QuestaoEditar):
    try:
        resposta_existente = (
            supabase_admin.table("questoes")
            .select("id")
            .eq("id", str(questao_id))
            .limit(1)
            .execute()
        )

        if not resposta_existente.data:
            raise HTTPException(
                status_code=404,
                detail="Questão não encontrada"
            )

        alteracoes = dados.model_dump(exclude_unset=True, exclude={"alternativas"})

        if not alteracoes and dados.alternativas is None:
            raise HTTPException(
                status_code=400,
                detail="Nenhuma alteração foi enviada"
            )

        if "materia_id" in alteracoes:
            alteracoes["materia_id"] = str(alteracoes["materia_id"])

        if "topico_id" in alteracoes and alteracoes["topico_id"] is not None:
            alteracoes["topico_id"] = str(alteracoes["topico_id"])

        if "tipo_prova_id" in alteracoes and alteracoes["tipo_prova_id"] is not None:
            alteracoes["tipo_prova_id"] = str(alteracoes["tipo_prova_id"])

        if "aula_id" in alteracoes and alteracoes["aula_id"] is not None:
            alteracoes["aula_id"] = str(alteracoes["aula_id"])

        if alteracoes:
            supabase_admin.table("questoes").update(alteracoes).eq(
                "id", str(questao_id)
            ).execute()

        if dados.alternativas is not None:
            excluir_alternativas(questao_id)
            salvar_alternativas(questao_id, dados.alternativas)

        return {
            "sucesso": True,
            "mensagem": "Questão atualizada com sucesso",
            "questao": montar_questao(questao_id)
        }

    except HTTPException:
        raise

    except Exception as erro:
        print(f"Erro ao atualizar questão: {erro}")
        raise HTTPException(
            status_code=500,
            detail="Erro ao atualizar questão"
        )


@router.delete('/{questao_id}')
def excluir_questao(questao_id: UUID):
    try:
        resposta = (
            supabase_admin.table("questoes")
            .select("id")
            .eq("id", str(questao_id))
            .limit(1)
            .execute()
        )

        if not resposta.data:
            raise HTTPException(
                status_code=404,
                detail="Questão não encontrada"
            )

        supabase_admin.table("questoes").update(
            {"alternativa_correta": None}
        ).eq("id", str(questao_id)).execute()

        excluir_alternativas(questao_id)

        supabase_admin.table("questoes").delete().eq("id", str(questao_id)).execute()

        return {
            "sucesso": True,
            "mensagem": "Questão excluída com sucesso"
        }

    except HTTPException:
        raise

    except Exception as erro:
        print(f"Erro ao excluir questão: {erro}")
        raise HTTPException(
            status_code=500,
            detail="Erro ao excluir questão"
        )
