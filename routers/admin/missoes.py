from fastapi import APIRouter, HTTPException, Depends, Query
from database import supabase_admin
from uuid import UUID
from utils.autenticacao import exigir_administrador
from schemas.missao_admin_schema import MissaoCriar, MissaoEditar
from utils.textos import gerar_slug

router = APIRouter(
    prefix='/admin/missoes',
    tags=['Admin - Missões'],
    dependencies=[Depends(exigir_administrador)]
)


@router.get('')
def listar_missoes(
    busca: str | None = None,
    tipo_missao: str | None = None,
    ativo: bool | None = None,
    pagina: int = Query(default=1, ge=1),
    limite: int = Query(default=20, ge=1, le=100),
):
    try:
        inicio = (pagina - 1) * limite
        fim = inicio + limite - 1

        consulta = supabase_admin.table("missoes").select("*", count="exact")

        if busca:
            consulta = consulta.ilike("titulo", f"%{busca.strip()}%")
        if tipo_missao:
            consulta = consulta.eq("tipo_missao", tipo_missao)
        if ativo is not None:
            consulta = consulta.eq("ativo", ativo)

        consulta = consulta.order("tipo_missao").order("titulo").range(inicio, fim).execute()

        missoes = consulta.data or []
        total_registros = consulta.count or 0
        total_paginas = (total_registros + limite - 1) // limite

        return {
            "sucesso": True,
            "pagina": pagina,
            "limite": limite,
            "quantidade_pagina": len(missoes),
            "total_registros": total_registros,
            "total_paginas": total_paginas,
            "missoes": missoes,
        }

    except Exception as erro:
        print(f"Erro ao listar missões: {erro}")

        raise HTTPException(
            status_code=500,
            detail="Erro ao listar missões"
        )


@router.get('/{missao_id}')
def buscar_missao(missao_id: UUID):
    try:
        resposta = (
            supabase_admin.table("missoes")
            .select("*")
            .eq("id", str(missao_id))
            .limit(1)
            .execute()
        )

        if not resposta.data:
            raise HTTPException(status_code=404, detail="Missão não encontrada")

        return {"sucesso": True, "missao": resposta.data[0]}

    except HTTPException:
        raise

    except Exception as erro:
        print(f"Erro ao buscar missão: {erro}")

        raise HTTPException(
            status_code=500,
            detail="Erro ao buscar missão"
        )


@router.post('', status_code=201)
def criar_missao(dados: MissaoCriar):
    try:
        titulo = dados.titulo.strip()
        slug = gerar_slug(titulo)

        existente = (
            supabase_admin.table("missoes")
            .select("id")
            .eq("slug", slug)
            .limit(1)
            .execute()
        )
        if existente.data:
            raise HTTPException(status_code=409, detail="Já existe uma missão com esse título")

        nova_missao = dados.model_dump()
        nova_missao["titulo"] = titulo
        nova_missao["slug"] = slug

        resposta = (
            supabase_admin.table("missoes")
            .insert(nova_missao)
            .execute()
        )

        if not resposta.data:
            raise HTTPException(status_code=500, detail="Não foi possível criar a missão")

        return {
            "sucesso": True,
            "mensagem": "Missão criada com sucesso",
            "missao": resposta.data[0],
        }

    except HTTPException:
        raise

    except Exception as erro:
        print(f"Erro ao criar missão: {erro}")

        raise HTTPException(
            status_code=500,
            detail="Erro ao criar missão"
        )


@router.patch('/{missao_id}')
def editar_missao(missao_id: UUID, dados: MissaoEditar):
    try:
        alteracoes = dados.model_dump(exclude_unset=True)

        if not alteracoes:
            raise HTTPException(status_code=400, detail="Nenhuma alteração foi enviada")

        if "titulo" in alteracoes:
            alteracoes["titulo"] = alteracoes["titulo"].strip()
            alteracoes["slug"] = gerar_slug(alteracoes["titulo"])

        resposta = (
            supabase_admin.table("missoes")
            .update(alteracoes)
            .eq("id", str(missao_id))
            .execute()
        )

        if not resposta.data:
            raise HTTPException(status_code=404, detail="Missão não encontrada")

        return {
            "sucesso": True,
            "mensagem": "Missão atualizada com sucesso",
            "missao": resposta.data[0],
        }

    except HTTPException:
        raise

    except Exception as erro:
        print(f"Erro ao atualizar missão: {erro}")

        raise HTTPException(
            status_code=500,
            detail="Erro ao atualizar missão"
        )
