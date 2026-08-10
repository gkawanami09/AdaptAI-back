from fastapi import APIRouter, HTTPException, Depends
from utils.autenticacao import exigir_administrador
from services.gamificacao import recalcular_conquistas_todos_alunos

router = APIRouter(
    prefix='/admin/gamificacao',
    tags=['Admin - Gamificação'],
    dependencies=[Depends(exigir_administrador)]
)


@router.post('/recalcular-todos')
def recalcular_conquistas_de_todos_os_alunos():
    """Único ponto que dispara services.gamificacao.recalcular_conquistas_todos_alunos
    — não é chamado automaticamente em lugar nenhum. Uso: retroatividade
    depois de rodar a migration inicial, ou depois de cadastrar uma
    conquista nova que precise avaliar a base inteira de alunos."""
    try:
        resultado = recalcular_conquistas_todos_alunos()

        return {
            "sucesso": True,
            "alunos_com_novas_conquistas": len(resultado),
            "total_conquistas_desbloqueadas": sum(len(c) for c in resultado.values()),
        }

    except Exception as erro:
        print(f"Erro ao recalcular conquistas de todos os alunos: {erro}")

        raise HTTPException(
            status_code=500,
            detail="Erro ao recalcular conquistas de todos os alunos"
        )
