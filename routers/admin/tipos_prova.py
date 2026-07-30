from fastapi import APIRouter, HTTPException, Depends, Query
from database import supabase_admin
from uuid import UUID
from utils.autenticacao import exigir_administrador
from schemas.questoes_schema import TipoProvaCriar, TipoProvaEditar
from utils.textos import gerar_slug

router = APIRouter(
    prefix='/admin/tipos-prova',
    tags=['Admin - Tipos de Prova'],
    dependencies=[Depends(exigir_administrador)]
)


@router.get('')
def listar_tipos_prova(
    busca: str | None = None,
    ativo: bool | None = None,
    pagina: int = Query(default=1, ge=1),
    limite: int = Query(default=6, ge=1, le=50),
):
    try:
        inicio = (pagina - 1) * limite
        fim = inicio + limite - 1

        consulta = (
            supabase_admin.table('tipos_prova')
            .select('*', count="exact")
        )

        if busca:
            consulta = consulta.ilike('nome', f'%{busca.strip()}%')
        if ativo is not None:
            consulta = consulta.eq('ativo', ativo)

        resposta = consulta.order('nome').range(inicio, fim).execute()

        tipos_prova = resposta.data or []
        total_registros = resposta.count or 0
        total_paginas = max(1, (total_registros + limite - 1) // limite)

        return {
            "sucesso": True,
            "pagina": pagina,
            "limite": limite,
            "total_registros": total_registros,
            "total_paginas": total_paginas,
            "tipos_prova": tipos_prova
        }

    except Exception as erro:
        print(f"Erro ao listar tipos de prova: {erro}")
        raise HTTPException(
            status_code=500,
            detail="Erro ao listar tipos de prova"
        )


@router.get('/resumo')
def obter_resumo():
    try:
        resposta = (
            supabase_admin.table('tipos_prova')
            .select('id, ativo')
            .execute()
        )

        tipos_prova = resposta.data or []
        ativos = [tipo for tipo in tipos_prova if tipo['ativo']]

        return {
            "sucesso": True,
            "total_tipos_prova": len(tipos_prova),
            "tipos_prova_ativos": len(ativos),
            "tipos_prova_inativos": len(tipos_prova) - len(ativos),
        }

    except Exception as erro:
        print(f"Erro ao obter resumo de tipos de prova: {erro}")
        raise HTTPException(
            status_code=500,
            detail="Erro ao obter resumo de tipos de prova"
        )


@router.get('/{tipo_prova_id}')
def buscar_tipo_prova(tipo_prova_id: UUID):
    try:
        resposta = (
            supabase_admin.table('tipos_prova')
            .select('*')
            .eq('id', str(tipo_prova_id))
            .limit(1)
            .execute()
        )

        if not resposta.data:
            raise HTTPException(
                status_code=404,
                detail="Tipo de prova não encontrado"
            )

        return {
            "sucesso": True,
            "tipo_prova": resposta.data[0]
        }

    except HTTPException:
        raise

    except Exception as erro:
        print(f"Erro ao buscar tipo de prova: {erro}")
        raise HTTPException(
            status_code=500,
            detail="Erro ao buscar tipo de prova"
        )


@router.post('')
def criar_tipo_prova(dados: TipoProvaCriar):
    try:
        nome = dados.nome.strip()
        slug = gerar_slug(nome)

        resposta = (
            supabase_admin.table('tipos_prova')
            .select('id')
            .eq('slug', slug)
            .limit(1)
            .execute()
        )

        if resposta.data:
            raise HTTPException(
                status_code=409,
                detail="Esse tipo de prova já existe"
            )

        novo_tipo_prova = dados.model_dump()
        novo_tipo_prova['nome'] = nome
        novo_tipo_prova['slug'] = slug

        resposta = (
            supabase_admin.table('tipos_prova')
            .insert(novo_tipo_prova)
            .execute()
        )

        if not resposta.data:
            raise HTTPException(
                status_code=500,
                detail="Não foi possível criar o tipo de prova"
            )

        return {
            "sucesso": True,
            "mensagem": "Tipo de prova criado com sucesso",
            "tipo_prova": resposta.data[0]
        }

    except HTTPException:
        raise

    except Exception as erro:
        print(f"Erro ao criar tipo de prova: {erro}")
        raise HTTPException(
            status_code=500,
            detail="Erro ao criar tipo de prova"
        )


@router.patch('/{tipo_prova_id}')
def editar_tipo_prova(tipo_prova_id: UUID, dados: TipoProvaEditar):
    try:
        alteracoes = dados.model_dump(exclude_unset=True)

        if not alteracoes:
            raise HTTPException(
                status_code=400,
                detail="Nenhuma alteração foi enviada"
            )

        if 'nome' in alteracoes:
            nome = alteracoes['nome'].strip()
            slug = gerar_slug(nome)

            resposta = (
                supabase_admin.table('tipos_prova')
                .select('id')
                .eq('slug', slug)
                .neq('id', str(tipo_prova_id))
                .limit(1)
                .execute()
            )

            if resposta.data:
                raise HTTPException(
                    status_code=409,
                    detail="Esse tipo de prova já existe"
                )

            alteracoes['nome'] = nome
            alteracoes['slug'] = slug

        resposta = (
            supabase_admin.table('tipos_prova')
            .update(alteracoes)
            .eq('id', str(tipo_prova_id))
            .execute()
        )

        if not resposta.data:
            raise HTTPException(
                status_code=404,
                detail="Tipo de prova não encontrado"
            )

        return {
            "sucesso": True,
            "mensagem": "Tipo de prova atualizado com sucesso",
            "tipo_prova": resposta.data[0]
        }

    except HTTPException:
        raise

    except Exception as erro:
        print(f"Erro ao atualizar tipo de prova: {erro}")
        raise HTTPException(
            status_code=500,
            detail="Erro ao atualizar tipo de prova"
        )


@router.delete('/{tipo_prova_id}')
def excluir_tipo_prova(tipo_prova_id: UUID):
    try:
        resposta = (
            supabase_admin.table('tipos_prova')
            .select('id')
            .eq('id', str(tipo_prova_id))
            .limit(1)
            .execute()
        )

        if not resposta.data:
            raise HTTPException(
                status_code=404,
                detail="Tipo de prova não encontrado"
            )

        supabase_admin.table('tipos_prova').delete().eq('id', str(tipo_prova_id)).execute()

        return {
            "sucesso": True,
            "mensagem": "Tipo de prova excluído com sucesso"
        }

    except HTTPException:
        raise

    except Exception as erro:
        print(f"Erro ao excluir tipo de prova: {erro}")
        raise HTTPException(
            status_code=500,
            detail="Erro ao excluir tipo de prova"
        )
