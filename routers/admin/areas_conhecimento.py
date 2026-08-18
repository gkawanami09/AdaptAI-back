from fastapi import APIRouter, HTTPException, Depends, Query
from database import supabase_admin
from uuid import UUID
from utils.autenticacao import exigir_administrador
from schemas.areas_conhecimento_schema import AreaConhecimentoCriar, AreaConhecimentoEditar
from utils.textos import gerar_slug

router = APIRouter(
    prefix='/admin/areas-conhecimento',
    tags=['Admin - Áreas do Conhecimento'],
    dependencies=[Depends(exigir_administrador)]
)


@router.get('')
def listar_areas_conhecimento(
    busca: str | None = None,
    ativo: bool | None = None,
    pagina: int = Query(default=1, ge=1),
    limite: int = Query(default=6, ge=1, le=50),
):
    try:
        inicio = (pagina - 1) * limite
        fim = inicio + limite - 1

        consulta = (
            supabase_admin.table('areas_conhecimento')
            .select('*', count="exact")
        )

        if busca:
            consulta = consulta.ilike('nome', f'%{busca.strip()}%')
        if ativo is not None:
            consulta = consulta.eq('ativo', ativo)

        resposta = consulta.order('nome').range(inicio, fim).execute()

        areas = resposta.data or []
        total_registros = resposta.count or 0
        total_paginas = max(1, (total_registros + limite - 1) // limite)

        return {
            "sucesso": True,
            "pagina": pagina,
            "limite": limite,
            "total_registros": total_registros,
            "total_paginas": total_paginas,
            "areas": areas
        }

    except Exception as erro:
        print(f"Erro ao listar áreas do conhecimento: {erro}")
        raise HTTPException(
            status_code=500,
            detail="Erro ao listar áreas do conhecimento"
        )


@router.get('/resumo')
def obter_resumo():
    try:
        resposta = (
            supabase_admin.table('areas_conhecimento')
            .select('id, ativo')
            .execute()
        )

        areas = resposta.data or []
        ativas = [area for area in areas if area['ativo']]

        return {
            "sucesso": True,
            "total_areas": len(areas),
            "areas_ativas": len(ativas),
            "areas_inativas": len(areas) - len(ativas),
        }

    except Exception as erro:
        print(f"Erro ao obter resumo de áreas do conhecimento: {erro}")
        raise HTTPException(
            status_code=500,
            detail="Erro ao obter resumo de áreas do conhecimento"
        )


@router.get('/{area_id}')
def buscar_area_conhecimento(area_id: UUID):
    try:
        resposta = (
            supabase_admin.table('areas_conhecimento')
            .select('*')
            .eq('id', str(area_id))
            .limit(1)
            .execute()
        )

        if not resposta.data:
            raise HTTPException(
                status_code=404,
                detail="Área do conhecimento não encontrada"
            )

        return {
            "sucesso": True,
            "area": resposta.data[0]
        }

    except HTTPException:
        raise

    except Exception as erro:
        print(f"Erro ao buscar área do conhecimento: {erro}")
        raise HTTPException(
            status_code=500,
            detail="Erro ao buscar área do conhecimento"
        )


@router.post('', status_code=201)
def criar_area_conhecimento(dados: AreaConhecimentoCriar):
    try:
        nome = dados.nome.strip()
        slug = gerar_slug(nome)

        resposta = (
            supabase_admin.table('areas_conhecimento')
            .select('id')
            .eq('slug', slug)
            .limit(1)
            .execute()
        )

        if resposta.data:
            raise HTTPException(
                status_code=422,
                detail="Essa área do conhecimento já existe"
            )

        nova_area = dados.model_dump()
        nova_area['nome'] = nome
        nova_area['slug'] = slug

        resposta = (
            supabase_admin.table('areas_conhecimento')
            .insert(nova_area)
            .execute()
        )

        if not resposta.data:
            raise HTTPException(
                status_code=500,
                detail="Não foi possível criar a área do conhecimento"
            )

        return {
            "sucesso": True,
            "mensagem": "Área do conhecimento criada com sucesso.",
            "area": resposta.data[0]
        }

    except HTTPException:
        raise

    except Exception as erro:
        print(f"Erro ao criar área do conhecimento: {erro}")
        raise HTTPException(
            status_code=500,
            detail="Erro ao criar área do conhecimento"
        )


@router.patch('/{area_id}')
def editar_area_conhecimento(area_id: UUID, dados: AreaConhecimentoEditar):
    try:
        alteracoes = dados.model_dump(exclude_unset=True)

        if not alteracoes:
            raise HTTPException(
                status_code=422,
                detail="Nenhuma alteração foi enviada"
            )

        if 'nome' in alteracoes:
            nome = alteracoes['nome'].strip()
            slug = gerar_slug(nome)

            resposta = (
                supabase_admin.table('areas_conhecimento')
                .select('id')
                .eq('slug', slug)
                .neq('id', str(area_id))
                .limit(1)
                .execute()
            )

            if resposta.data:
                raise HTTPException(
                    status_code=422,
                    detail="Essa área do conhecimento já existe"
                )

            alteracoes['nome'] = nome
            alteracoes['slug'] = slug

        resposta = (
            supabase_admin.table('areas_conhecimento')
            .update(alteracoes)
            .eq('id', str(area_id))
            .execute()
        )

        if not resposta.data:
            raise HTTPException(
                status_code=404,
                detail="Área do conhecimento não encontrada"
            )

        return {
            "sucesso": True,
            "mensagem": "Área do conhecimento atualizada com sucesso.",
            "area": resposta.data[0]
        }

    except HTTPException:
        raise

    except Exception as erro:
        print(f"Erro ao atualizar área do conhecimento: {erro}")
        raise HTTPException(
            status_code=500,
            detail="Erro ao atualizar área do conhecimento"
        )


@router.delete('/{area_id}')
def excluir_area_conhecimento(area_id: UUID):
    try:
        resposta = (
            supabase_admin.table('areas_conhecimento')
            .select('id')
            .eq('id', str(area_id))
            .limit(1)
            .execute()
        )

        if not resposta.data:
            raise HTTPException(
                status_code=404,
                detail="Área do conhecimento não encontrada"
            )

        supabase_admin.table('areas_conhecimento').delete().eq('id', str(area_id)).execute()

        return {
            "sucesso": True,
            "mensagem": "Área do conhecimento excluída com sucesso."
        }

    except HTTPException:
        raise

    except Exception as erro:
        print(f"Erro ao excluir área do conhecimento: {erro}")
        raise HTTPException(
            status_code=500,
            detail="Erro ao excluir área do conhecimento"
        )
