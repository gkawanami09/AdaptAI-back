from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from database import supabase, supabase_admin


validacao = HTTPBearer()

def pegar_usuario_atual(
    credentials: HTTPAuthorizationCredentials = Depends(validacao)
):
    token = credentials.credentials

    try:
        resposta = supabase.auth.get_user(token)

        if not resposta.user:
            raise HTTPException(
                status_code=401,
                detail="Token inválido ou expirado."
            )

        return resposta.user

    except HTTPException:
        raise

    except Exception:
        raise HTTPException(
            status_code=401,
            detail="Usuário não autenticado."
        )

def exigir_administrador(
    usuario=Depends(pegar_usuario_atual)
):
    resposta = (
        supabase_admin
        .table("perfis")
        .select("tipo_usuario")
        .eq("id", str(usuario.id))
        .limit(1)
        .execute()
    )

    if not resposta.data:
        raise HTTPException(
            status_code=404,
            detail="Perfil não encontrado"
        )  

    perfil = resposta.data[0]

    if perfil["tipo_usuario"] != "admin":
        raise HTTPException(
            status_code=403,
            detail="Acesso permitido apenas para administradores"
        )

    return usuario
