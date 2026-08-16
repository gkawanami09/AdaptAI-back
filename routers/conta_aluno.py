from fastapi import APIRouter, HTTPException, Depends
from database import supabase
from utils.autenticacao import pegar_usuario_atual
from services.exclusao_conta_service import excluir_conta
from schemas.conta_aluno_schema import ExcluirContaPayload, ExcluirContaResponse

router = APIRouter(
    prefix='/aluno',
    tags=['Aluno - Conta']
)


@router.delete('/conta', response_model=ExcluirContaResponse)
def deletar_conta(
    dados: ExcluirContaPayload,
    usuario_atual=Depends(pegar_usuario_atual)
):
    try:
        email = usuario_atual.email
        if not email:
            raise HTTPException(status_code=400, detail="Usuário sem email associado")

        try:
            supabase.auth.sign_in_with_password({
                "email": email,
                "password": dados.senha,
            })
        except Exception:
            raise HTTPException(status_code=403, detail="Senha incorreta")

        excluir_conta(str(usuario_atual.id))

        return {"sucesso": True}

    except HTTPException:
        raise

    except Exception as erro:
        print(f"Erro ao excluir conta do aluno: {erro}")

        raise HTTPException(
            status_code=500,
            detail="Erro ao excluir conta do aluno"
        )
