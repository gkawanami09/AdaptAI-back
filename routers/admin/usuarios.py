from fastapi import APIRouter, HTTPException, Depends, Query
from database import supabase_admin
from uuid import UUID
from utils.autenticacao import exigir_administrador, pegar_usuario_atual
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

CARGOS_VALIDOS = {"aluno", "professor", "admin"}
CARGO_ALIASES = {"administrador": "admin"}


def normalizar_cargo(cargo: str) -> str:
    cargo_normalizado = CARGO_ALIASES.get(cargo, cargo)
    if cargo_normalizado not in CARGOS_VALIDOS:
        raise HTTPException(
            status_code=400,
            detail=f"Cargo inválido: {cargo}. Use um de {sorted(CARGOS_VALIDOS)}"
        )
    return cargo_normalizado

ORDENACAO = {
    "nome-az": ("nome", False),
    "nome-za": ("nome", True),
    "recentes": ("criado_em", True),
    "xp-desc": ("criado_em", True),
    "ofensiva-desc": ("criado_em", True),
}


# Fetches the estatisticas_usuario row for a single user (or defaults)
def obter_estatisticas(usuario_id: str) -> dict:
    resposta = (
        supabase_admin.table("estatisticas_usuario")
        .select("ofensiva_atual_dias, maior_ofensiva_dias, xp_total, nivel")
        .eq("usuario_id", usuario_id)
        .limit(1)
        .execute()
        .data
    )
    if resposta:
        return resposta[0]
    return {"ofensiva_atual_dias": 0, "maior_ofensiva_dias": 0, "xp_total": 0, "nivel": 1}


# Mesma origem usada em GET /aluno/configuracoes (routers/configuracoes_aluno.py:montar_perfil)
def obter_ano_enem(usuario_id: str) -> str | None:
    resposta = (
        supabase_admin.table("preferencias_aluno")
        .select("ano_alvo")
        .eq("usuario_id", usuario_id)
        .limit(1)
        .execute()
        .data
    )
    if resposta and resposta[0].get("ano_alvo"):
        return str(resposta[0]["ano_alvo"])
    return None


# Builds the UsuarioDetalhe-shaped dict from a perfil row + auth user
def montar_usuario_detalhe(perfil: dict, usuario_auth=None):
    email = usuario_auth.user.email if usuario_auth and usuario_auth.user else perfil.get("email", "")
    email_confirmado_em = usuario_auth.user.email_confirmed_at if usuario_auth and usuario_auth.user else None

    usuario_id = perfil["id"]
    estatisticas = obter_estatisticas(usuario_id)

    respostas = (
        supabase_admin.table("respostas_lista_questoes_aluno")
        .select("correta")
        .eq("usuario_id", usuario_id)
        .execute()
        .data or []
    )
    questoes_respondidas = len(respostas)
    acertos = sum(1 for r in respostas if r["correta"])
    taxa_acerto = round((acertos / questoes_respondidas) * 100, 1) if questoes_respondidas else 0

    atividades = (
        supabase_admin.table("atividade_diaria")
        .select("minutos_estudo")
        .eq("usuario_id", usuario_id)
        .execute()
        .data or []
    )
    tempo_estudo_min = sum(a["minutos_estudo"] for a in atividades)

    listas_concluidas = (
        supabase_admin.table("progresso_lista_questoes_aluno")
        .select("id", count="exact")
        .eq("usuario_id", usuario_id)
        .eq("status", "finalizada")
        .execute()
        .count or 0
    )

    provas_realizadas = (
        supabase_admin.table("sessoes_simulado")
        .select("id", count="exact")
        .eq("usuario_id", usuario_id)
        .eq("status", "concluido")
        .execute()
        .count or 0
    )

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
        "ofensiva_atual": estatisticas.get("ofensiva_atual_dias", 0),
        "maior_ofensiva": estatisticas.get("maior_ofensiva_dias", 0),
        "xp": estatisticas.get("xp_total", 0),
        "nivel": estatisticas.get("nivel", 1),
        "escola": perfil.get("escola_nome"),
        "ano_enem": obter_ano_enem(usuario_id),
        "questoes_respondidas": questoes_respondidas,
        "taxa_acerto": taxa_acerto,
        "tempo_estudo_min": tempo_estudo_min,
        "listas_concluidas": listas_concluidas,
        "provas_realizadas": provas_realizadas,
        # ranking_geral ainda não tem tabela/cálculo de ranking global — sem dado real disponível
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
            consulta = consulta.eq("tipo_usuario", normalizar_cargo(cargo))
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

        ids_perfis = [perfil["id"] for perfil in perfis]
        estatisticas_linhas = (
            supabase_admin.table("estatisticas_usuario")
            .select("usuario_id, ofensiva_atual_dias, xp_total, nivel")
            .in_("usuario_id", ids_perfis)
            .execute()
            .data or []
        ) if ids_perfis else []
        estatisticas_por_usuario = {linha["usuario_id"]: linha for linha in estatisticas_linhas}

        preferencias_linhas = (
            supabase_admin.table("preferencias_aluno")
            .select("usuario_id, ano_alvo")
            .in_("usuario_id", ids_perfis)
            .execute()
            .data or []
        ) if ids_perfis else []
        ano_enem_por_usuario = {
            linha["usuario_id"]: str(linha["ano_alvo"])
            for linha in preferencias_linhas
            if linha.get("ano_alvo")
        }

        usuarios = [
            {
                "id": perfil["id"],
                "nome": perfil["nome"],
                "email": emails_por_id.get(perfil["id"], ""),
                "avatar_url": perfil.get("avatar_url"),
                "cargo": perfil["tipo_usuario"],
                "status": SITUACAO_PARA_STATUS.get(perfil["situacao"], perfil["situacao"]),
                "ofensiva_atual": estatisticas_por_usuario.get(perfil["id"], {}).get("ofensiva_atual_dias", 0),
                "xp": estatisticas_por_usuario.get(perfil["id"], {}).get("xp_total", 0),
                "ultimo_acesso": None,
                "nivel": estatisticas_por_usuario.get(perfil["id"], {}).get("nivel", 1),
                "escola": perfil.get("escola_nome"),
                "ano_enem": ano_enem_por_usuario.get(perfil["id"]),
            }
            for perfil in perfis
        ]

        if ofensiva_min is not None:
            usuarios = [usuario for usuario in usuarios if usuario["ofensiva_atual"] >= ofensiva_min]

        total_ativos = sum(1 for perfil in perfis if perfil["situacao"] == "ativo")
        total_suspensos = sum(1 for perfil in perfis if perfil["situacao"] == "suspenso")

        ofensiva_media = (
            round(sum(usuario["ofensiva_atual"] for usuario in usuarios) / len(usuarios), 1)
            if usuarios else 0
        )

        return {
            "sucesso": True,
            "pagina": pagina,
            "limite": limite,
            "total_paginas": total_paginas,
            "total_usuarios": total_registros,
            "total_ativos": total_ativos,
            "total_suspensos": total_suspensos,
            "ofensiva_media": ofensiva_media,
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
            "tipo_usuario": normalizar_cargo(dados.cargo),
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

        erro_texto = str(erro).lower()
        if "already registered" in erro_texto or "already been registered" in erro_texto:
            raise HTTPException(
                status_code=409,
                detail="Já existe uma conta cadastrada com esse email."
            )

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
            alteracoes["tipo_usuario"] = normalizar_cargo(alteracoes.pop("cargo"))

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
            .update({"tipo_usuario": normalizar_cargo(dados.cargo)})
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

        historico_resposta = (
            supabase_admin.table("streak_historico")
            .select("data, ofensiva_dias")
            .eq("usuario_id", str(usuario_id))
            .order("data", desc=False)
            .execute()
            .data or []
        )

        return {
            "sucesso": True,
            "historico": historico_resposta,
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

        desbloqueadas_banco = (
            supabase_admin.table("conquistas_usuario")
            .select("conquista_id, desbloqueado_em, conquistas(titulo, descricao, icone, raridade, xp_recompensa)")
            .eq("usuario_id", str(usuario_id))
            .order("desbloqueado_em", desc=True)
            .execute()
            .data or []
        )

        conquistas = [
            {
                "id": linha["conquista_id"],
                "titulo": (linha.get("conquistas") or {}).get("titulo"),
                "descricao": (linha.get("conquistas") or {}).get("descricao"),
                "icone": (linha.get("conquistas") or {}).get("icone"),
                "raridade": (linha.get("conquistas") or {}).get("raridade"),
                "xp": (linha.get("conquistas") or {}).get("xp_recompensa"),
                "desbloqueado_em": linha["desbloqueado_em"],
            }
            for linha in desbloqueadas_banco
        ]

        return {
            "sucesso": True,
            "conquistas": conquistas,
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

        inicio = (pagina - 1) * limite
        fim = inicio + limite - 1

        consulta = (
            supabase_admin.table("log_atividade")
            .select("id, tipo, descricao, metadata, criado_em", count="exact")
            .eq("usuario_id", str(usuario_id))
            .order("criado_em", desc=True)
            .range(inicio, fim)
            .execute()
        )

        itens = consulta.data or []
        total_registros = consulta.count or 0
        total_paginas = (total_registros + limite - 1) // limite

        return {
            "sucesso": True,
            "pagina": pagina,
            "limite": limite,
            "total_paginas": total_paginas,
            "itens": itens,
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

        medidas = (
            supabase_admin.table("acoes_administrativas")
            .select("id, tipo, motivo, duracao_dias, administrador_id, criado_em")
            .eq("usuario_id", str(usuario_id))
            .order("criado_em", desc=True)
            .execute()
            .data or []
        )

        return {
            "sucesso": True,
            "medidas": medidas,
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
def suspender_usuario(usuario_id: UUID, dados: UsuarioSuspender, usuario_atual=Depends(pegar_usuario_atual)):
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

        supabase_admin.table("acoes_administrativas").insert({
            "usuario_id": str(usuario_id),
            "administrador_id": str(usuario_atual.id),
            "tipo": "suspensao",
            "motivo": dados.motivo,
            "duracao_dias": dados.duracao_dias,
        }).execute()

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
def banir_usuario(usuario_id: UUID, dados: UsuarioBanir, usuario_atual=Depends(pegar_usuario_atual)):
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

        supabase_admin.table("acoes_administrativas").insert({
            "usuario_id": str(usuario_id),
            "administrador_id": str(usuario_atual.id),
            "tipo": "banimento",
            "motivo": dados.motivo,
        }).execute()

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
def resetar_ofensiva(usuario_id: UUID, usuario_atual=Depends(pegar_usuario_atual)):
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

        supabase_admin.table("estatisticas_usuario").update({
            "ofensiva_atual_dias": 0,
        }).eq("usuario_id", str(usuario_id)).execute()

        supabase_admin.table("acoes_administrativas").insert({
            "usuario_id": str(usuario_id),
            "administrador_id": str(usuario_atual.id),
            "tipo": "reset_ofensiva",
        }).execute()

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
