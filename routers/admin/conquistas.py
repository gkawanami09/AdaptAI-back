from fastapi import APIRouter, HTTPException, Depends, Query
from database import supabase_admin
from uuid import UUID
from utils.autenticacao import exigir_administrador
from schemas.conquista_admin_schema import ConquistaCriar, ConquistaEditar
from utils.textos import gerar_slug

router = APIRouter(
    prefix='/admin/conquistas',
    tags=['Admin - Conquistas'],
    dependencies=[Depends(exigir_administrador)]
)


@router.get('')
def listar_conquistas(
    busca: str | None = None,
    raridade: str | None = None,
    ativo: bool | None = None,
    pagina: int = Query(default=1, ge=1),
    limite: int = Query(default=20, ge=1, le=100),
):
    try:
        inicio = (pagina - 1) * limite
        fim = inicio + limite - 1

        consulta = supabase_admin.table("conquistas").select("*", count="exact")

        if busca:
            consulta = consulta.ilike("titulo", f"%{busca.strip()}%")
        if raridade:
            consulta = consulta.eq("raridade", raridade)
        if ativo is not None:
            consulta = consulta.eq("ativo", ativo)

        consulta = consulta.order("titulo").range(inicio, fim).execute()

        conquistas = consulta.data or []
        total_registros = consulta.count or 0
        total_paginas = (total_registros + limite - 1) // limite

        return {
            "sucesso": True,
            "pagina": pagina,
            "limite": limite,
            "quantidade_pagina": len(conquistas),
            "total_registros": total_registros,
            "total_paginas": total_paginas,
            "conquistas": conquistas,
        }

    except Exception as erro:
        print(f"Erro ao listar conquistas: {erro}")

        raise HTTPException(
            status_code=500,
            detail="Erro ao listar conquistas"
        )


@router.get('/{conquista_id}')
def buscar_conquista(conquista_id: UUID):
    try:
        resposta = (
            supabase_admin.table("conquistas")
            .select("*")
            .eq("id", str(conquista_id))
            .limit(1)
            .execute()
        )

        if not resposta.data:
            raise HTTPException(status_code=404, detail="Conquista não encontrada")

        return {"sucesso": True, "conquista": resposta.data[0]}

    except HTTPException:
        raise

    except Exception as erro:
        print(f"Erro ao buscar conquista: {erro}")

        raise HTTPException(
            status_code=500,
            detail="Erro ao buscar conquista"
        )


@router.post('', status_code=201)
def criar_conquista(dados: ConquistaCriar):
    try:
        titulo = dados.titulo.strip()
        slug = gerar_slug(titulo)

        existente = (
            supabase_admin.table("conquistas")
            .select("id")
            .eq("slug", slug)
            .limit(1)
            .execute()
        )
        if existente.data:
            raise HTTPException(status_code=409, detail="Já existe uma conquista com esse título")

        nova_conquista = dados.model_dump()
        nova_conquista["titulo"] = titulo
        nova_conquista["slug"] = slug
        nova_conquista["materia_id"] = str(dados.materia_id) if dados.materia_id else None

        resposta = (
            supabase_admin.table("conquistas")
            .insert(nova_conquista)
            .execute()
        )

        if not resposta.data:
            raise HTTPException(status_code=500, detail="Não foi possível criar a conquista")

        return {
            "sucesso": True,
            "mensagem": "Conquista criada com sucesso",
            "conquista": resposta.data[0],
        }

    except HTTPException:
        raise

    except Exception as erro:
        print(f"Erro ao criar conquista: {erro}")

        raise HTTPException(
            status_code=500,
            detail="Erro ao criar conquista"
        )


@router.patch('/{conquista_id}')
def editar_conquista(conquista_id: UUID, dados: ConquistaEditar):
    try:
        alteracoes = dados.model_dump(exclude_unset=True)

        if not alteracoes:
            raise HTTPException(status_code=400, detail="Nenhuma alteração foi enviada")

        if "titulo" in alteracoes:
            alteracoes["titulo"] = alteracoes["titulo"].strip()
            alteracoes["slug"] = gerar_slug(alteracoes["titulo"])

        if "materia_id" in alteracoes and alteracoes["materia_id"] is not None:
            alteracoes["materia_id"] = str(alteracoes["materia_id"])

        resposta = (
            supabase_admin.table("conquistas")
            .update(alteracoes)
            .eq("id", str(conquista_id))
            .execute()
        )

        if not resposta.data:
            raise HTTPException(status_code=404, detail="Conquista não encontrada")

        return {
            "sucesso": True,
            "mensagem": "Conquista atualizada com sucesso",
            "conquista": resposta.data[0],
        }

    except HTTPException:
        raise

    except Exception as erro:
        print(f"Erro ao atualizar conquista: {erro}")

        raise HTTPException(
            status_code=500,
            detail="Erro ao atualizar conquista"
        )
