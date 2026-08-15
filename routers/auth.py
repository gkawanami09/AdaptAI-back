from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from uuid import uuid4
from datetime import datetime, timezone
from database import supabase, supabase_admin
from utils.validacao import validar_senha_forte
from utils.codigo_email import gerar_codigo_email, gerar_hash_codigo, codigo_expiracao_minutos
from services.envia_email import enviar_email_verificacao
from schemas.auth_schema import LoginUsuario, ConfirmaEmail


router = APIRouter(
    prefix='/auth',
    tags=['Auth']
)


@router.post('/registro')    #remover o return de codigo hash em aplicação real
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
                detail='As senhas digitadas não coincidem'
            )

        # `perfis` não guarda email (só existe em auth.users, gerenciado
        # pelo Supabase Auth) — por isso a checagem de duplicidade
        # precisa ser feita pela Admin API de auth, não pela tabela.
        usuarios_existentes = supabase_admin.auth.admin.list_users()
        if any(u.email and u.email.lower() == email for u in usuarios_existentes):
            raise HTTPException(
                status_code=409,
                detail="Já existe uma conta cadastrada com esse email."
            )

        auth_response = supabase.auth.sign_up({
            'email' : email,
            'password' : senha
        })

        id_usuario = auth_response.user.id if auth_response.user else None

        if not id_usuario:
            raise HTTPException(
                status_code= 400,
                detail= 'Erro, usuário não foi criado'
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
        
        try:
            enviar_email_verificacao(email, codigo, nome)
        except Exception as erro_email:
            # A conta e o código já foram persistidos acima — uma falha de
            # SMTP (ex.: credenciais não configuradas) não pode derrubar um
            # cadastro que já aconteceu de verdade, senão o usuário fica com
            # uma conta órfã (existe no banco, mas nunca recebe o código e
            # vê "email já cadastrado" em qualquer nova tentativa).
            print(f"Erro ao enviar email de verificação: {erro_email}")

        return {
            'sucesso' : True,
            'mensagem' : 'Usuário cadastrado com sucesso!',
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
                detail="Já existe uma conta cadastrada com esse email."
            )

        if "email rate limit exceeded" in erro_texto:
            raise HTTPException(
                status_code=429,
                detail="Muitas tentativas de cadastro. Aguarde um pouco e tente novamente."
            )
            
        raise HTTPException(
            status_code=500,
            detail=f"Erro interno ao cadastrar usuário: {str(erro)}"
        )


@router.post('/confirmaEmail')      #implementar verificação de código expirado
def confirmaEmail(dados : ConfirmaEmail):
    try:
        email= dados.email.strip().lower()
        codigo_hash=  gerar_hash_codigo(dados.codigo)
        
        resposta= (supabase_admin
            .table('email_verificacoes')
            .select('*')
            .eq('email', email)
            .eq('usado', False)
            .order("criado_em", desc=True)
            .limit(1)
            .execute()
        )
        
        if not resposta.data:
            raise HTTPException(
                status_code=404,
                detail="Código não encontrado, já utilizado ou e-mail diferente."
            )
        id_usuario = resposta.data[0]["user_id"]
        
        if codigo_hash != resposta.data[0]["codigo_hash"]:
            raise HTTPException(
                    status_code= 400,
                    detail= 'Código inválido.'
                )
        
        supabase_admin.table('email_verificacoes').update(
            {
                'usado' : True
            }
        ) \
            .eq('email',  email) \
            .eq('codigo_hash', codigo_hash)  \
            .execute()
        print(id_usuario)
        
        supabase_admin.table('perfis').update(
            {
                'situacao' : 'ativo',
                'email_verificado' : True,
                'email_verificado_em' : datetime.now(timezone.utc).isoformat()
            }) \
                .eq('id', id_usuario) \
                .execute()
        
        supabase_admin.auth.admin.update_user_by_id(
            id_usuario,
            {'ban_duration': 'none'}
        )

        resultado = {
            'sucesso' : True,
            'email' : email
        }

        # Gera uma sessão real (sem precisar da senha do usuário) para o
        # front não precisar chamar /auth/login logo em seguida: cria um
        # magic link via Admin API e troca o OTP dele por uma sessão.
        try:
            link = supabase_admin.auth.admin.generate_link({
                'type': 'magiclink',
                'email': email
            })
            sessao = supabase.auth.verify_otp({
                'email': email,
                'token': link.properties.email_otp,
                'type': 'magiclink'
            })
            if sessao.session:
                resultado['session'] = {
                    'access_token': sessao.session.access_token,
                    'refresh_token': sessao.session.refresh_token,
                    'token_type': 'bearer'
                }
        except Exception as erro_sessao:
            # Confirmação já foi persistida acima — se a geração da sessão
            # falhar, o front ainda pode cair para o fluxo antigo de login.
            print(f"Erro ao gerar sessão pós-confirmação: {erro_sessao}")

        return resultado
    except HTTPException:
        raise

    except Exception as erro:
        raise HTTPException(
            status_code=500,
            detail=f"Erro interno ao confirmar e-mail: {str(erro)}"
        )


@router.post('/login')     #fazer bloqueio de usuário após 3 tentativas
def login(dados : LoginUsuario):
    email= dados.email.strip().lower()
    senha= dados.senha
    try:
        resposta= supabase.auth.sign_in_with_password(
            {
                'email' : email,
                'password' : senha
            }
        )
        
        if not resposta.user or not resposta.session:
            raise HTTPException(
                status_code= 401,
                detail= 'Email ou senha inválidos.'
            )
        id_usuario = resposta.user.id
        
        resposta_perfil= supabase_admin.table('perfis').select(
            'id, nome, escola_nome, avatar_url, situacao, email_verificado, tipo_usuario'
        )  \
        .eq('id', id_usuario)   \
        .limit(1)  \
        .execute()
        
        if not resposta_perfil.data:
            raise HTTPException(
                status_code= 400,
                detail= 'Perfil do usuário não encontrado'
            )
            
        perfil= resposta_perfil.data[0]
        
        if perfil['situacao'] in ('suspenso', 'inativo'):
            raise HTTPException(
                status_code= 403,
                detail= 'Seu perfil está bloqueado, entre em contato pelo e-mail adapt2787@gmail.com'
            )
        
        if perfil['situacao']== 'bloqueado' or not perfil['email_verificado']:
            raise HTTPException(
                status_code= 403,
                detail= 'Verifique o seu perfil antes de entrar.'
            )
            
        return {
            'sucesso' : True,
            'mensagem' : 'Login realizado com sucesso',
            'usuario' : {
                'id': perfil['id'],
                'nome': perfil['nome'],
                'escola_nome': perfil['escola_nome'],
                'avatar_url': perfil['avatar_url'],
                'tipo_usuario' : perfil['tipo_usuario']
            },
                "session": {
                    "access_token": resposta.session.access_token,
                    "refresh_token": resposta.session.refresh_token,
                    "token_type": "bearer"
                }
        }
        
    except HTTPException:
        raise

    except Exception as erro:
        erro_texto = str(erro).lower()

        if "invalid login credentials" in erro_texto:
            raise HTTPException(
                status_code=401,
                detail="Email ou senha inválidos."
            )

        if "banned" in erro_texto:
            raise HTTPException(
                status_code=403,
                detail="Usuário bloqueado ou ainda não verificado."
            )

        raise HTTPException(
            status_code=500,
            detail=f"Erro interno ao fazer login: {str(erro)}"
        )
