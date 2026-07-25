from fastapi import APIRouter, HTTPException, Depends, Query
from database import supabase_admin
from uuid import UUID
from utils.autenticacao import exigir_administrador
from schemas.topicos_schema import TopicoCriar, TopicoEditar, TopicoGet
from utils.textos import gerar_slug

router = APIRouter(
    prefix='/admin/topicos',
    tags=['Admin - Tópicos'],
    dependencies=[Depends(exigir_administrador)]
)

@router.get("/{materia_id}")
def listar_topicos(materia_id: UUID):
    try:
        resposta = (
            supabase_admin.table("topicos")
            .select("*")
            .eq("materia_id", str(materia_id))
            .execute()
        )

        if not resposta.data:
            raise HTTPException(
                status_code=404,
                detail="Tópicos não encontrados"
            )

        topicos = [TopicoGet(**topico) for topico in resposta.data]

        return {
            "sucesso": True,
            "topicos": topicos
        }

    except HTTPException:
        raise

    except Exception as erro:
        print(f"Erro ao buscar tópicos: {erro}")
        raise HTTPException(
            status_code=500,
            detail="Erro ao buscar os tópicos"
        )

@router.post('')
def criar_topico(dados: TopicoCriar):
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

        nome = dados.nome.strip()
        slug = gerar_slug(nome)

        novo_topico = dados.model_dump()
        novo_topico["materia_id"] = str(dados.materia_id)
        novo_topico["nome"] = nome
        novo_topico["slug"] = slug

        resposta = (
            supabase_admin.table("topicos")
            .select("topico_id")
            .eq("materia_id", str(dados.materia_id))
            .eq("slug", slug)
            .limit(1)
            .execute()
        )

        if resposta.data:
            raise HTTPException(
                status_code=409,
                detail="Esse tópico já existe nessa matéria"
            )

        resposta = (
            supabase_admin.table("topicos")
            .insert(novo_topico)
            .execute()
        )

        if not resposta.data:
            raise HTTPException(
                status_code=500,
                detail="Não foi possível criar o tópico"
            )

        return {
            "sucesso": True,
            "mensagem": "Tópico criado com sucesso",
            "topico": resposta.data[0]
        }

    except HTTPException:
        raise

    except Exception as erro:
        print(f"Erro ao criar tópico: {erro}")
        raise HTTPException(
            status_code=500,
            detail="Erro ao criar tópico"
        )

@router.patch('/{topico_id}')
def editar_topico(topico_id: UUID, dados: TopicoEditar):
    try:
        alteracoes = dados.model_dump(exclude_unset=True)

        if not alteracoes:
            raise HTTPException(
                status_code=400,
                detail="Nenhuma alteração foi enviada"
            )

        if "materia_id" in alteracoes:
            alteracoes["materia_id"] = str(alteracoes["materia_id"])

        if "nome" in alteracoes:
            alteracoes["nome"] = alteracoes["nome"].strip()
            alteracoes["slug"] = gerar_slug(alteracoes["nome"])

        resposta = (
            supabase_admin.table("topicos")
            .update(alteracoes)
            .eq("topico_id", str(topico_id))
            .execute()
        )

        if not resposta.data:
            raise HTTPException(
                status_code=404,
                detail="Tópico não encontrado"
            )

        return {
            "sucesso": True,
            "mensagem": "Tópico atualizado com sucesso",
            "topico": resposta.data[0]
        }

    except HTTPException:
        raise

    except Exception as erro:
        print(f"Erro ao atualizar tópico: {erro}")
        raise HTTPException(
            status_code=500,
            detail="Erro ao atualizar tópico"
        )