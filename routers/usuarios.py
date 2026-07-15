from fastapi import APIRouter, Depends, HTTPException, Form, UploadFile, File
from database import supabase, supabase_admin
from utils.validacao import validar_senha_forte
from utils.autenticacao import pegar_usuario_atual
from uuid import uuid4

router = APIRouter(
    prefix="/usuarios",
    tags=["Usuários"]
)


@router.get("/perfil")
def perfil(usuario_atual= Depends(pegar_usuario_atual)):
    try:
        id_usuario = usuario_atual.id

        resposta = (
            supabase_admin
            .table("perfis")
            .select("id, nome, escola_nome, avatar_url, situacao, email_verificado")
            .eq("id", id_usuario)
            .limit(1)
            .execute()
        )

        if not resposta.data:
            raise HTTPException(
                status_code=404,
                detail="Perfil não encontrado."
            )

        return {
            "sucesso": True,
            "usuario": resposta.data[0]
        }

    except HTTPException:
        raise

    except Exception as erro:
        raise HTTPException(
            status_code=500,
            detail=f"Erro interno ao buscar usuário: {str(erro)}"
        )
        
@router.patch('/edicao')
async def edicao(
    nome: str | None = Form(None),
    escola_nome: str | None = Form(None),
    avatar: UploadFile | None = File(None),
    senha: str | None = Form(None),
    confsenha: str | None = Form(None),
    usuario=Depends(pegar_usuario_atual)
):
    try:
        id_usuario= usuario.id
         
        campos_atualizar = {}
         
        if nome is not None:
            campos_atualizar['nome'] = nome.strip()
        
        if escola_nome is not None:
            campos_atualizar['escola_nome']= escola_nome.strip()
            
        if senha is not None:
            senha_valida, mensagem_senha = validar_senha_forte(senha)
            
            if not senha_valida:
                raise HTTPException(
                    status_code= 400,
                    detail= mensagem_senha
                )
            if confsenha is None:
                raise HTTPException(
                    status_code= 400,
                    detail='Você deve confirmar a sua senha'
                )
            
            if senha != confsenha:
                raise HTTPException(
                    status_code= 400,
                    detail= 'As senhas digitadas não coincidem'
                )

            supabase_admin.auth.admin.update_user_by_id(
                id_usuario,
                {'password': senha}
            )
            
        if avatar is not None:
            avatar_path= None
            avatar_url= None
            
            if avatar and avatar.filename:
                tipos_permitidos= ['image/jpeg', 'image/png', 'image/webp']
                
                if avatar.content_type not in tipos_permitidos:
                    raise HTTPException(
                        status_code= 400,
                        detail= 'Formato de imagem inválido. Use JPG, PNG ou WEBP'
                    )
                imagem= await avatar.read()
                tipo= avatar.filename.split('.')[-1]
                nome_arquivo= f'{uuid4()}.{tipo}'
                
                avatar_path= f'usuarios/{id_usuario}/{nome_arquivo}'
                
                supabase_admin.storage.from_('avatars').upload(
                    path= avatar_path,
                    file= imagem,
                    file_options={
                        'content-type':avatar.content_type
                    }
                )
                
                avatar_url= supabase.storage.from_('avatars').get_public_url(avatar_path)
                
                campos_atualizar['avatar_path']= avatar_path
                campos_atualizar['avatar_url']= avatar_url
                
        if not campos_atualizar and senha is None:
            raise HTTPException(
                status_code=400,
                detail="Nenhum campo enviado para atualização."
            )
            
        if campos_atualizar:
            supabase_admin.table("perfis") \
            .update(campos_atualizar) \
            .eq("id", id_usuario) \
            .execute()
        
        resposta = (
        supabase_admin
        .table("perfis")
        .select("id, nome, escola_nome, avatar_url, situacao, email_verificado, tipo_usuario")
        .eq("id", id_usuario)
        .limit(1)
        .execute()
        )

        if not resposta.data:
            raise HTTPException(
                status_code=404,
                detail="Perfil não encontrado."
            )

        return {
            "sucesso": True,
            "mensagem": "Perfil atualizado com sucesso.",
            "usuario": resposta.data[0]
        }

    except HTTPException:
        raise

    except Exception as erro:
        raise HTTPException(
            status_code=500,
            detail=f"Erro interno ao editar perfil: {str(erro)}"
        )
