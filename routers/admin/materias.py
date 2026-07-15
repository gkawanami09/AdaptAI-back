from fastapi import APIRouter, HTTPException, Depends
from database import supabase_admin
from uuid import UUID
from utils.autenticacao import exigir_administrador

router = APIRouter(
    prefix='/admin/materias',
    tags=['Admin - Matérias'],
    dependencies=[Depends(exigir_administrador)]
)

@router.get('')
def listar_materias():
    try:
        resposta= (supabase_admin.table('materias')
                   .select('*')
                   .order('ordem')
                   .execute()
                   )

        materias= resposta.data or []

        
        return {
            "sucesso" : True,
            "quantidade" : len(materias),
            "materias" : materias
        }

    except Exception as erro:
        print(f"Erro ao listar matérias: {erro}")

        raise HTTPException(
            status_code=500,
            detail="Erro ao listar matérias"
        )

@router.get('/resumo')
def obter_resumo():
    pass


@router.get('/{materia_id}')
def buscar_materias(materia_id: UUID):
    pass