from fastapi import APIRouter, HTTPException, Depends, Query
from database import supabase_admin
from uuid import UUID
from utils.autenticacao import exigir_administrador
from schemas.usuario_schema import (
    UsuarioCriar,
    UsuarioEditar,
    UsuarioCargoEditar,
    UsuarioSuspender,
    UsuarioBanir,
)

router = APIRouter(
    prefix='/admin/usuarios',
    tags=['Admin - Usuários'],
    dependencies=[Depends(exigir_administrador)]
)

STATUS_PARA_SITUACAO = {"ativo": "ativo", "suspenso": "suspenso", "banido": "bloqueado"}
SITUACAO_PARA_STATUS = {"ativo": "ativo", "suspenso": "suspenso", "bloqueado": "banido"}

ORDENACAO = {
    "nome-az": ("nome", False),
    "nome-za": ("nome", True),
    "recentes": ("criado_em", True),
    "xp-desc": ("criado_em", True),
    "ofensiva-desc": ("criado_em", True),
}


# Builds the UsuarioDetalhe-shaped dict from a perfil row + auth user
def montar_usuario_detalhe(perfil: dict, usuario_auth=None):
    email = usuario_auth.user.email if usuario_auth and usuario_auth.user else perfil.get("email", "")
    email_confirmado_em = usuario_auth.user.email_confirmed_at if usuario_auth and usuario_auth.user else None

    return {
        "id": perfil["id"],
        "id_publico": perfil["id"],
        "nome": perfil["nome"],
        "email": email,
        "avatar_url": perfil.get("avatar_url"),
        "cargo": perfil["tipo_usuario"],
        "status": SITUACAO_PARA_STATUS.get(perfil["situacao"], perfil["situacao"]),
        "criado_em": perfil.get("criado_em"),
        "ultimo_acesso": None,
        "email_verificado": bool(email_confirmado_em) if usuario_auth else bool(perfil.get("email_verificado")),
        # TODO: gamification fields (ofensiva, xp, taxa_acerto etc.) depend on tables that don't exist yet
        "ofensiva_atual": 0,
        "maior_ofensiva": 0,
        "xp": 0,
        "questoes_respondidas": 0,
        "taxa_acerto": 0,
        "tempo_estudo_min": 0,
        "listas_concluidas": 0,
        "provas_realizadas": 0,
        "ranking_geral": 0,
    }


@router.get('')
def listar_usuarios(
    busca: str | None = None,
    cargo: str | None = None,
    status: str | None = None,
    ofensiva_min: int | None = None,
    ordenar: str | None = None,
    pagina: int = Query(default=1, ge=1),
    limite: int = Query(default=8, ge=1, le=100),
):
    try:
        inicio = (pagina - 1) * limite
        fim = inicio + limite - 1

        consulta = supabase_admin.table("perfis").select("*", count="exact")

        if busca:
            consulta = consulta.ilike("nome", f"%{busca.strip()}%")
        if cargo:
            consulta = consulta.eq("tipo_usuario", cargo)
        if status:
            consulta = consulta.eq("situacao", STATUS_PARA_SITUACAO.get(status, status))

        campo_ordem, decrescente = ORDENACAO.get(ordenar, ("criado_em", True))

        consulta = (
            consulta
            .order(campo_ordem, desc=decrescente)
            .range(inicio, fim)
            .execute()
        )

        perfis = consulta.data or []
        total_registros = consulta.count or 0
        total_paginas = (total_registros + limite - 1) // limite

        todos_usuarios_auth = supabase_admin.auth.admin.list_users()
        emails_por_id = {usuario.id: usuario.email for usuario in todos_usuarios_auth}

        usuarios = [
            {
                "id": perfil["id"],
                "nome": perfil["nome"],
                "email": emails_por_id.get(perfil["id"], ""),
                "avatar_url": perfil.get("avatar_url"),
                "cargo": perfil["tipo_usuario"],
                "status": SITUACAO_PARA_STATUS.get(perfil["situacao"], perfil["situacao"]),
                # TODO: ofensiva_atual and xp depend on gamification tables that don't exist yet
                "ofensiva_atual": 0,
                "xp": 0,
                "ultimo_acesso": None,
            }
            for perfil in perfis
        ]

        if ofensiva_min is not None:
            usuarios = [usuario for usuario in usuarios if usuario["ofensiva_atual"] >= ofensiva_min]

        total_ativos = sum(1 for perfil in perfis if perfil["situacao"] == "ativo")
        total_suspensos = sum(1 for perfil in perfis if perfil["situacao"] == "suspenso")

        return {
            "sucesso": True,
            "pagina": pagina,
            "limite": limite,
            "total_paginas": total_paginas,
            "total_usuarios": total_registros,
            "total_ativos": total_ativos,
            "total_suspensos": total_suspensos,
            "ofensiva_media": 0,
            "usuarios": usuarios,
        }

    except Exception as erro:
        print(f"Erro ao listar usuários: {erro}")
        raise HTTPException(
            status_code=500,
            detail="Erro ao listar usuários"
        )


@router.post('', status_code=201)
def criar_usuario(dados: UsuarioCriar):
    try:
        nome = dados.nome.strip()

        resposta_auth = supabase_admin.auth.admin.create_user({
            "email": dados.email,
            "email_confirm": False,
        })

        if not resposta_auth or not resposta_auth.user:
            raise HTTPException(
                status_code=500,
                detail="Não foi possível criar o usuário"
            )

        id_usuario = resposta_auth.user.id

        novo_perfil = {
            "id": id_usuario,
            "nome": nome,
            "tipo_usuario": dados.cargo,
            "situacao": "ativo",
        }

        resposta = (
            supabase_admin.table("perfis")
            .insert(novo_perfil)
            .execute()
        )

        if not resposta.data:
            raise HTTPException(
                status_code=500,
                detail="Não foi possível criar o usuário"
            )

        usuario = montar_usuario_detalhe(resposta.data[0], resposta_auth)

        return {
            "sucesso": True,
            "mensagem": "Usuário criado com sucesso.",
            "usuario": usuario,
        }

    except HTTPException:
        raise

    except Exception as erro:
        print(f"Erro ao criar usuário: {erro}")
        raise HTTPException(
            status_code=500,
            detail="Erro ao criar usuário"
        )


@router.get('/{usuario_id}')
def buscar_usuario(usuario_id: UUID):
    try:
        resposta = (
            supabase_admin.table("perfis")
            .select("*")
            .eq("id", str(usuario_id))
            .limit(1)
            .execute()
        )

        if not resposta.data:
            raise HTTPException(
                status_code=404,
                detail="Usuário não encontrado"
            )

        usuario_auth = supabase_admin.auth.admin.get_user_by_id(str(usuario_id))
        usuario = montar_usuario_detalhe(resposta.data[0], usuario_auth)

        return {
            "sucesso": True,
            "usuario": usuario,
        }

    except HTTPException:
        raise

    except Exception as erro:
        print(f"Erro ao buscar usuário: {erro}")
        raise HTTPException(
            status_code=500,
            detail="Erro ao buscar usuário"
        )


@router.patch('/{usuario_id}')
def editar_usuario(usuario_id: UUID, dados: UsuarioEditar):
    try:
        alteracoes = dados.model_dump(exclude_unset=True)

        if not alteracoes:
            raise HTTPException(
                status_code=400,
                detail="Nenhuma alteração foi enviada"
            )

        email = alteracoes.pop("email", None)
        if "nome" in alteracoes:
            alteracoes["nome"] = alteracoes["nome"].strip()
        if "cargo" in alteracoes:
            alteracoes["tipo_usuario"] = alteracoes.pop("cargo")

        if email:
            supabase_admin.auth.admin.update_user_by_id(
                str(usuario_id),
                {"email": email}
            )

        if alteracoes:
            resposta = (
                supabase_admin.table("perfis")
                .update(alteracoes)
                .eq("id", str(usuario_id))
                .execute()
            )
        else:
            resposta = (
                supabase_admin.table("perfis")
                .select("*")
                .eq("id", str(usuario_id))
                .execute()
            )

        if not resposta.data:
            raise HTTPException(
                status_code=404,
                detail="Usuário não encontrado"
            )

        usuario_auth = supabase_admin.auth.admin.get_user_by_id(str(usuario_id))
        usuario = montar_usuario_detalhe(resposta.data[0], usuario_auth)

        return {
            "sucesso": True,
            "mensagem": "Usuário atualizado com sucesso.",
            "usuario": usuario,
        }

    except HTTPException:
        raise

    except Exception as erro:
        print(f"Erro ao atualizar usuário: {erro}")
        raise HTTPException(
            status_code=500,
            detail="Erro ao atualizar usuário"
        )


@router.patch('/{usuario_id}/cargo')
def alterar_cargo(usuario_id: UUID, dados: UsuarioCargoEditar):
    try:
        resposta = (
            supabase_admin.table("perfis")
            .update({"tipo_usuario": dados.cargo})
            .eq("id", str(usuario_id))
            .execute()
        )

        if not resposta.data:
            raise HTTPException(
                status_code=404,
                detail="Usuário não encontrado"
            )

        usuario_auth = supabase_admin.auth.admin.get_user_by_id(str(usuario_id))
        usuario = montar_usuario_detalhe(resposta.data[0], usuario_auth)

        return {
            "sucesso": True,
            "mensagem": "Cargo atualizado.",
            "usuario": usuario,
        }

    except HTTPException:
        raise

    except Exception as erro:
        print(f"Erro ao alterar cargo: {erro}")
        raise HTTPException(
            status_code=500,
            detail="Erro ao alterar cargo"
        )


@router.get('/{usuario_id}/ofensiva-historico')
def obter_historico_ofensiva(usuario_id: UUID):
    try:
        resposta = (
            supabase_admin.table("perfis")
            .select("id")
            .eq("id", str(usuario_id))
            .limit(1)
            .execute()
        )

        if not resposta.data:
            raise HTTPException(
                status_code=404,
                detail="Usuário não encontrado"
            )

        # TODO: depends on a streak-history table that doesn't exist yet
        return {
            "sucesso": True,
            "historico": [],
        }

    except HTTPException:
        raise

    except Exception as erro:
        print(f"Erro ao obter histórico de ofensiva: {erro}")
        raise HTTPException(
            status_code=500,
            detail="Erro ao obter histórico de ofensiva"
        )


@router.get('/{usuario_id}/conquistas')
def obter_conquistas(usuario_id: UUID):
    try:
        resposta = (
            supabase_admin.table("perfis")
            .select("id")
            .eq("id", str(usuario_id))
            .limit(1)
            .execute()
        )

        if not resposta.data:
            raise HTTPException(
                status_code=404,
                detail="Usuário não encontrado"
            )

        # TODO: depends on an achievements table that doesn't exist yet
        return {
            "sucesso": True,
            "conquistas": [],
        }

    except HTTPException:
        raise

    except Exception as erro:
        print(f"Erro ao obter conquistas: {erro}")
        raise HTTPException(
            status_code=500,
            detail="Erro ao obter conquistas"
        )


@router.get('/{usuario_id}/historico')
def obter_historico_atividades(
    usuario_id: UUID,
    pagina: int = Query(default=1, ge=1),
    limite: int = Query(default=8, ge=1, le=100),
):
    try:
        resposta = (
            supabase_admin.table("perfis")
            .select("id")
            .eq("id", str(usuario_id))
            .limit(1)
            .execute()
        )

        if not resposta.data:
            raise HTTPException(
                status_code=404,
                detail="Usuário não encontrado"
            )

        # TODO: depends on an activity-log table that doesn't exist yet
        return {
            "sucesso": True,
            "pagina": pagina,
            "limite": limite,
            "total_paginas": 0,
            "itens": [],
        }

    except HTTPException:
        raise

    except Exception as erro:
        print(f"Erro ao obter histórico de atividades: {erro}")
        raise HTTPException(
            status_code=500,
            detail="Erro ao obter histórico de atividades"
        )


@router.get('/{usuario_id}/medidas')
def obter_medidas(usuario_id: UUID):
    try:
        resposta = (
            supabase_admin.table("perfis")
            .select("id")
            .eq("id", str(usuario_id))
            .limit(1)
            .execute()
        )

        if not resposta.data:
            raise HTTPException(
                status_code=404,
                detail="Usuário não encontrado"
            )

        # TODO: depends on an administrative-actions table that doesn't exist yet
        return {
            "sucesso": True,
            "medidas": [],
        }

    except HTTPException:
        raise

    except Exception as erro:
        print(f"Erro ao obter medidas administrativas: {erro}")
        raise HTTPException(
            status_code=500,
            detail="Erro ao obter medidas administrativas"
        )


@router.get('/{usuario_id}/timeline')
def obter_timeline(usuario_id: UUID):
    try:
        resposta = (
            supabase_admin.table("perfis")
            .select("*")
            .eq("id", str(usuario_id))
            .limit(1)
            .execute()
        )

        if not resposta.data:
            raise HTTPException(
                status_code=404,
                detail="Usuário não encontrado"
            )

        perfil = resposta.data[0]
        criado_em = perfil.get("criado_em")

        eventos = [
            {
                "id": "conta_criada",
                "tipo": "conta_criada",
                "titulo": "Conta criada",
                "descricao": "Usuário se cadastrou na plataforma",
                "data": criado_em,
            }
        ]

        return {
            "sucesso": True,
            "eventos": eventos,
        }

    except HTTPException:
        raise

    except Exception as erro:
        print(f"Erro ao obter timeline: {erro}")
        raise HTTPException(
            status_code=500,
            detail="Erro ao obter timeline"
        )


@router.post('/{usuario_id}/suspender')
def suspender_usuario(usuario_id: UUID, dados: UsuarioSuspender):
    try:
        resposta = (
            supabase_admin.table("perfis")
            .update({"situacao": "suspenso"})
            .eq("id", str(usuario_id))
            .execute()
        )

        if not resposta.data:
            raise HTTPException(
                status_code=404,
                detail="Usuário não encontrado"
            )

        # TODO: persist motivo/duracao_dias once an administrative-actions table exists
        usuario_auth = supabase_admin.auth.admin.get_user_by_id(str(usuario_id))
        usuario = montar_usuario_detalhe(resposta.data[0], usuario_auth)

        return {
            "sucesso": True,
            "mensagem": "Usuário suspenso com sucesso.",
            "usuario": usuario,
        }

    except HTTPException:
        raise

    except Exception as erro:
        print(f"Erro ao suspender usuário: {erro}")
        raise HTTPException(
            status_code=500,
            detail="Erro ao suspender usuário"
        )


@router.post('/{usuario_id}/banir')
def banir_usuario(usuario_id: UUID, dados: UsuarioBanir):
    try:
        resposta = (
            supabase_admin.table("perfis")
            .update({"situacao": "bloqueado"})
            .eq("id", str(usuario_id))
            .execute()
        )

        if not resposta.data:
            raise HTTPException(
                status_code=404,
                detail="Usuário não encontrado"
            )

        # TODO: persist motivo once an administrative-actions table exists
        usuario_auth = supabase_admin.auth.admin.get_user_by_id(str(usuario_id))
        usuario = montar_usuario_detalhe(resposta.data[0], usuario_auth)

        return {
            "sucesso": True,
            "mensagem": "Usuário banido com sucesso.",
            "usuario": usuario,
        }

    except HTTPException:
        raise

    except Exception as erro:
        print(f"Erro ao banir usuário: {erro}")
        raise HTTPException(
            status_code=500,
            detail="Erro ao banir usuário"
        )


@router.post('/{usuario_id}/reativar')
def reativar_usuario(usuario_id: UUID):
    try:
        resposta = (
            supabase_admin.table("perfis")
            .update({"situacao": "ativo"})
            .eq("id", str(usuario_id))
            .execute()
        )

        if not resposta.data:
            raise HTTPException(
                status_code=404,
                detail="Usuário não encontrado"
            )

        usuario_auth = supabase_admin.auth.admin.get_user_by_id(str(usuario_id))
        usuario = montar_usuario_detalhe(resposta.data[0], usuario_auth)

        return {
            "sucesso": True,
            "mensagem": "Usuário reativado com sucesso.",
            "usuario": usuario,
        }

    except HTTPException:
        raise

    except Exception as erro:
        print(f"Erro ao reativar usuário: {erro}")
        raise HTTPException(
            status_code=500,
            detail="Erro ao reativar usuário"
        )


@router.post('/{usuario_id}/resetar-senha')
def resetar_senha(usuario_id: UUID):
    try:
        usuario_auth = supabase_admin.auth.admin.get_user_by_id(str(usuario_id))

        if not usuario_auth or not usuario_auth.user:
            raise HTTPException(
                status_code=404,
                detail="Usuário não encontrado"
            )

        supabase_admin.auth.reset_password_email(usuario_auth.user.email)

        return {
            "sucesso": True,
            "mensagem": "Email de redefinição de senha enviado.",
        }

    except HTTPException:
        raise

    except Exception as erro:
        print(f"Erro ao resetar senha: {erro}")
        raise HTTPException(
            status_code=500,
            detail="Erro ao resetar senha"
        )


@router.post('/{usuario_id}/resetar-ofensiva')
def resetar_ofensiva(usuario_id: UUID):
    try:
        resposta = (
            supabase_admin.table("perfis")
            .select("*")
            .eq("id", str(usuario_id))
            .limit(1)
            .execute()
        )

        if not resposta.data:
            raise HTTPException(
                status_code=404,
                detail="Usuário não encontrado"
            )

        # TODO: persist reset once a gamification/streak table exists
        usuario_auth = supabase_admin.auth.admin.get_user_by_id(str(usuario_id))
        usuario = montar_usuario_detalhe(resposta.data[0], usuario_auth)

        return {
            "sucesso": True,
            "mensagem": "Ofensiva resetada com sucesso.",
            "usuario": usuario,
        }

    except HTTPException:
        raise

    except Exception as erro:
        print(f"Erro ao resetar ofensiva: {erro}")
        raise HTTPException(
            status_code=500,
            detail="Erro ao resetar ofensiva"
        )
