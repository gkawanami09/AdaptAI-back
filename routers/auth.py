from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from uuid import uuid4
from database import supabase, supabase_admin
from utils.validacao import validar_senha_forte
from utils.codigo_email import gerar_codigo_email, gerar_hash_codigo, codigo_expiracao_minutos
from services.envia_email import enviar_email_verificacao


router = APIRouter(
    prefix='/auth',
    tags=['Auth']
)

@router.post('/registro')    #remover o return de codigo hash em aplica??o real
async def registro(
    nome : str= Form(..., min_length= 2),
    email : str= Form(...),
    escola : str | None= Form(None, max_length= 100),
    senha : str= Form(...),
    conf_senha: str= Form(...),
    avatar : UploadFile | None= File(None)  
):
    try:
        nome= nome.strip()
        email= email.strip().lower()
        
        senha_valida, mensagem_senha = validar_senha_forte(senha)
        if not senha_valida:
            raise HTTPException(
                status_code= 400,
                detail= mensagem_senha
            )
            
        if senha != conf_senha:
            raise HTTPException(
                status_code= 400,
                detail='As senhas digitadas n?o coincidem'
            )
        auth_response = supabase.auth.sign_up({
            'email' : email,
            'password' : senha
        })
        
        id_usuario = auth_response.user.id
        
        if not id_usuario:
            raise HTTPException(
                status_code= 400,
                detail= 'Erro, usu?rio n?o foi criado'
            )
            
        supabase_admin.auth.admin.update_user_by_id(
            id_usuario,
            {'ban_duration': '876000h'}
        )

        avatar_path= None
        avatar_url= None
        
        if avatar and avatar.filename:
            tipos_permitidos= ['image/jpeg', 'image/png', 'image/webp']
            
            if avatar.content_type not in tipos_permitidos:
                raise HTTPException(
                    status_code= 400,
                    detail= 'Formato de imagem inv?lido. Use JPG, PNG ou WEBP'
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
            
        codigo= gerar_codigo_email()
        codigo_hash= gerar_hash_codigo(codigo)
         
        supabase_admin.table('email_verificacoes').insert(
            {
                'user_id' : id_usuario,
                'email' : email,
                'codigo_hash' : codigo_hash,
                "expira_em": codigo_expiracao_minutos(10).isoformat()
            }
        ).execute()
         
        supabase_admin.table('perfis').insert(
            {
                'id' : id_usuario,
                'nome' : nome,
                'escola_nome' : escola,
                'avatar_path': avatar_path,
                'avatar_url' : avatar_url,
                'situacao' : 'bloqueado',
                'email_verificado': False
            }
        ).execute()
        
        enviar_email_verificacao(email, codigo, nome)
    
        return {
            'sucesso' : True,
            'mensagem' : 'Usu?rio cadastrado com sucesso!',
            'usuarios' : {
                'id' : id_usuario,
                'nome' : nome,
                'email' : email,
                'codigo' : codigo,
                'codigo_hase' : codigo_hash,
                'situacao' : 'bloqueado',
                'email_verificado': False
                
            }
        }
    except HTTPException:
        raise

    except Exception as erro:
        erro_texto = str(erro).lower()

        if "user already registered" in erro_texto:
            raise HTTPException(
                status_code=409,
                detail="J? existe uma conta cadastrada com esse email."
            )

        if "email rate limit exceeded" in erro_texto:
            raise HTTPException(
                status_code=429,
                detail="Muitas tentativas de cadastro. Aguarde um pouco e tente novamente."
            )
            
        raise HTTPException(
            status_code=500,
            detail=f"Erro interno ao cadastrar usu?rio: {str(erro)}"
        )


