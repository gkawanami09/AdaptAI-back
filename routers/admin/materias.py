from fastapi import APIRouter, HTTPException, Depends, Query
from database import supabase_admin
from uuid import UUID
from utils.autenticacao import exigir_administrador
from schemas.materia_schema import MateriaCriar, MateriaEditar
from utils.textos import gerar_slug

router = APIRouter(
    prefix='/admin/materias',
    tags=['Admin - Matérias'],
    dependencies=[Depends(exigir_administrador)]
)

@router.get('')
def listar_materias(
    busca : str | None= None,
    area : str | None= None,
    ativo : bool | None= None,
    pagina : int= Query(default= 1, ge= 1),
    limite : int= Query(default= 6, ge= 1, le= 100)
):
    try:
        inicio = (pagina - 1) * limite
        fim = inicio + limite - 1
        consulta= (supabase_admin.table('materias')
                   .select('*', count="exact")
                   .order('ordem')
                   )
        
        if busca:
            consulta= consulta.ilike(
                'nome',
                f'%{busca.strip()}%'
            )
        if area:
            consulta= consulta.eq(
                "area",
                area
            )
        if ativo is not None:
            consulta= consulta.eq(
                "ativo",
                ativo
            )
        consulta = (
            consulta
            .order("ordem")
            .order("nome")
            .range(inicio, fim)
            .execute()
        )
                       

        materias= consulta.data or []
        
        for materia in materias:
            topicos = materia.get("topicos") or []
            aulas = materia.get("aulas") or []

            materia["total_topicos"] = len(topicos)
            materia["total_aulas"] = len(aulas)

            materia.pop("topicos", None)
            materia.pop("aulas", None)
            
        total_registros = consulta.count or 0
        
        total_paginas = (total_registros + limite - 1) // limite

        
        return {
            "sucesso": True,
            "pagina": pagina,
            "limite": limite,
            "quantidade_pagina": len(materias),
            "total_registros": total_registros,
            "total_paginas": total_paginas,
            "materias": materias
        }

    except Exception as erro:
        print(f"Erro ao listar matérias: {erro}")

        raise HTTPException(
            status_code=500,
            detail="Erro ao listar matérias"
        )

@router.get('/resumo')
def obter_resumo():
    try:
        resposta_materias= (supabase_admin.table('materias')
                            .select('id, ativo')
                            .execute()
                            )
        
        resposta_topicos= (supabase_admin.table('topicos')
                           .select('id, ativo')
                           .execute()
                           )
        
        materias= resposta_materias.data or []
        topicos= resposta_topicos.data or []
        
        materias_ativas= [materia 
                          for materia in materias
                          if materia['ativo'] 
                          ]
        
        topicos_ativos= [topico 
                          for topico in topicos
                          if topico['ativo'] 
                          ]

        return {
            "sucesso": True,
            "total_materias": len(materias),
            "total_topicos": len(topicos),
            "materias_ativas": len(materias_ativas),
            "materias_inativas": len(materias) - len(materias_ativas),
            "topicos_ativos": len(topicos_ativos),
            "topicos_inativos": len(topicos) - len(topicos_ativos),
        }
        
    except Exception as erro:
        print(f"Erro ao obter resumo de matérias: {erro}")

        raise HTTPException(
            status_code=500,
            detail="Erro ao obter resumo de matérias"
        )

@router.get('/{materia_id}')
def buscar_materias(materia_id: UUID):
    try:
        resposta= (supabase_admin.table('materias')
                .select('*')
                .eq('id', str(materia_id))
                .limit(1)
                .execute()
                )
        print(resposta.data)
        if not resposta.data:
            raise HTTPException(
                status_code= 404,
                detail= 'Matéria não encontrada'
            )
        
        materia = resposta.data[0]

        return{
            'sucesso' : True,
            'materia' : materia
        }
    
    except HTTPException:
        raise

    except Exception as erro:
        print(f"Erro ao buscar matéria: {erro}")

        raise HTTPException(
            status_code=500,
            detail="Erro ao buscar matéria"
        )
    
@router.get('/{materia_id}/topicos')
def listar_topicos_da_materia(materia_id: UUID):
    try:
        resposta_materia = (supabase_admin.table('materias')
                            .select('id')
                            .eq('id', str(materia_id))
                            .limit(1)
                            .execute()
                            )

        if not resposta_materia.data:
            raise HTTPException(
                status_code=404,
                detail='Matéria não encontrada'
            )

        resposta= (supabase_admin.table('topicos')
                .select('*')
                .eq('materia_id', str(materia_id))
                .order('ordem')
                .order('nome')
                .execute()
                )

        topicos = resposta.data or []

        return {
            'sucesso': True,
            'total_topicos': len(topicos),
            'topicos': topicos
        }

    except HTTPException:
        raise

    except Exception as erro:
        print(f"Erro ao listar tópicos da matéria: {erro}")

        raise HTTPException(
            status_code=500,
            detail="Erro ao listar tópicos da matéria"
        )

@router.post('')
def criar_materia(dados: MateriaCriar):
    try:
        nome = dados.nome.strip()
        slug= gerar_slug(nome)
        
        nova_materia= dados.model_dump()
        nova_materia['nome']= nome
        nova_materia['slug']= slug
        
        resposta= (supabase_admin.table('materias')
                   .select('id')
                   .eq('slug', slug)
                   .limit(1)
                   .execute()
                   )
        if resposta.data:
            raise HTTPException(
                status_code= 409,
                detail= 'Essa matéria já existe'
            )

        resposta= (supabase_admin.table('materias')
                   .insert(nova_materia)
                   .execute()
                   )
        
        if not resposta.data:
            raise HTTPException(
                status_code= 500,
                detail= 'Não foi possível criar a matéria'
            )
            
        return {
            'sucesso' : True,
            'mensagem' : 'Matéria criada com sucesso',
            'materia' : resposta.data[0]
        }
        
    except HTTPException:
        raise

    except Exception as erro:
        print(f"Erro ao criar matéria: {erro}")

        raise HTTPException(
            status_code=500,
            detail="Erro ao criar matéria"
        )   
        
@router.patch('/{materia_id}')
def editar_materia(
    materia_id: UUID,
    dados: MateriaEditar
    ):
    try:
        alteracoes= dados.model_dump(
            exclude_unset= True
        )
        
        if not alteracoes:
            raise HTTPException(
                status_code= 400,
                detail= 'Nenhuma alteração foi enviada'
            )
        
        if 'nome' in alteracoes:
            alteracoes['nome']= alteracoes['nome'].strip()
            
        resposta= (supabase_admin.table('materias')
                   .update(alteracoes)
                   .eq('id', str(materia_id))
                   .execute()
                   )
        
        if not resposta.data:
            raise HTTPException(
                status_code=404,
                detail="Matéria não encontrada"
            )

        return {
            "sucesso": True,
            "mensagem": "Matéria atualizada com sucesso",
            "materia": resposta.data[0]
        }

    except HTTPException:
        raise

    except Exception as erro:
        print(f"Erro ao atualizar matéria: {erro}")

        raise HTTPException(
            status_code=500,
            detail="Erro ao atualizar matéria"
        )


# Bloqueia a exclusão se houver conteúdo real vinculado (aulas/tópicos/
# questões/listas de questões) — sem isso, o DELETE quebraria com um erro
# de FK constraint cru (500) em vez de uma mensagem que o admin entenda.
# Nesses casos, o caminho é inativar a matéria (PATCH ativo=false), não
# excluir.
def _dependencias_materia(materia_id: UUID) -> list[str]:
    dependencias = []

    contagens = {
        'aulas': 'aula(s)',
        'topicos': 'tópico(s)',
        'questoes': 'questão(ões)',
        'listas_questoes': 'lista(s) de questões',
    }

    for tabela, rotulo in contagens.items():
        resposta = (
            supabase_admin.table(tabela)
            .select('id', count='exact')
            .eq('materia_id', str(materia_id))
            .execute()
        )
        total = resposta.count or 0
        if total:
            dependencias.append(f"{total} {rotulo}")

    return dependencias


@router.delete('/{materia_id}')
def excluir_materia(materia_id: UUID):
    try:
        resposta = (supabase_admin.table('materias')
                    .select('id')
                    .eq('id', str(materia_id))
                    .limit(1)
                    .execute()
                    )

        if not resposta.data:
            raise HTTPException(
                status_code=404,
                detail='Matéria não encontrada'
            )

        dependencias = _dependencias_materia(materia_id)
        if dependencias:
            raise HTTPException(
                status_code=409,
                detail=(
                    "Não é possível excluir: há " + ", ".join(dependencias)
                    + " vinculada(s) a essa matéria. Inative-a em vez de excluir."
                )
            )

        supabase_admin.table('materias').delete().eq('id', str(materia_id)).execute()

        return {
            "sucesso": True,
            "mensagem": "Matéria excluída com sucesso"
        }

    except HTTPException:
        raise

    except Exception as erro:
        print(f"Erro ao excluir matéria: {erro}")

        raise HTTPException(
            status_code=500,
            detail="Erro ao excluir matéria"
        )
