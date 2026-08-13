from fastapi import APIRouter, HTTPException, Depends, Query, UploadFile, File, Form
from database import supabase_admin
from uuid import UUID, uuid4
from datetime import datetime, timezone
import time
from utils.autenticacao import exigir_administrador
from services.ai.base import AIIndisponivelError
from services.ai.factory import get_ai_provider
from schemas.configuracoes_schema import (
    ConfiguracoesGeraisEditar,
    ConfiguracoesAutenticacaoEditar,
    ConfiguracoesConteudoEditar,
    ConfiguracoesIaEditar,
    ConfiguracoesIaTestar,
    ConfiguracoesNotificacoesEditar,
    IntegracaoEditar,
)

router = APIRouter(
    prefix='/admin/configuracoes',
    tags=['Admin - Configurações'],
    dependencies=[Depends(exigir_administrador)]
)

CONFIGURACOES_PADRAO = {
    "gerais": {
        "nome_plataforma": "AdaptAI",
        "slogan": "Estude melhor. Aprenda com IA. Alcance seus objetivos.",
        "descricao": "Plataforma inteligente de estudos com questões, simulados, planos personalizados e IA para potencializar o aprendizado.",
        "logo_url": None,
        "favicon_url": None,
        "idioma": "pt-BR",
        "timezone": "America/Sao_Paulo",
        "formato_data": "DD/MM/YYYY",
        "tema": "claro",
    },
    "autenticacao": {
        "tempo_sessao_min": 1440,
        "login_google_ativo": True,
        "login_microsoft_ativo": False,
        "autenticacao_dois_fatores_ativo": False,
        "reset_senha_ativo": True,
        "senha_tamanho_minimo": 8,
        "senha_exigir_numero": True,
        "senha_exigir_maiuscula": True,
        "senha_exigir_caractere_especial": True,
    },
    "conteudo": {
        "itens_por_pagina": 20,
        "tamanho_maximo_upload_mb": 5,
        "tipos_arquivo_permitidos": ["jpg", "png", "pdf"],
        "editor_padrao": "rich-text",
        "auto_salvamento_ativo": True,
        "auto_salvamento_intervalo_seg": 30,
    },
    "ia": {
        "modelo": "claude-sonnet-5",
        "temperatura": 0.7,
        "max_tokens": 2048,
        "prompt_base": "Você é um assistente educacional do AdaptAI.",
        "limite_geracoes_dia": 500,
    },
    "notificacoes": {
        "email_ativo": True,
        "push_ativo": True,
        "alertas_internos_ativo": True,
        "evento_novo_usuario": True,
        "evento_questao_criada": True,
        "evento_questao_editada": True,
        "evento_lista_publicada": True,
        "evento_prova_criada": True,
        "evento_prova_publicada": True,
        "evento_usuario_completou_lista": True,
        "resumo_diario_email": False,
        "resumo_semanal_email": False,
    },
    "integracoes": [
        {
            "id": "b5f8f7f0-1a2b-4c3d-9e0f-111111111111",
            "provedor": "google",
            "nome": "Google Analytics",
            "descricao": "Integração com Google Analytics.",
            "ativo": True,
            "api_key_mascarada": "G-XXXXXXXXXX",
            "webhook_url": None,
            "conectado_em": "2026-01-05T10:00:00Z",
        },
        {
            "id": "b5f8f7f0-1a2b-4c3d-9e0f-222222222222",
            "provedor": "sentry",
            "nome": "Sentry",
            "descricao": "Monitoramento de erros e performance.",
            "ativo": False,
            "api_key_mascarada": None,
            "webhook_url": "https://oxxxxxxx.ingest.sentry.io/xxxxxxx",
            "conectado_em": None,
        },
        {
            "id": "b5f8f7f0-1a2b-4c3d-9e0f-333333333333",
            "provedor": "slack",
            "nome": "Slack",
            "descricao": "Envio de alertas para o Slack.",
            "ativo": True,
            "api_key_mascarada": None,
            "webhook_url": "https://hooks.slack.com/services/...",
            "conectado_em": "2026-02-01T08:00:00Z",
        },
    ],
}


# Reads all configuration sections from the "configuracoes" table, seeding
# any missing section (chave) with its default value on first read
def carregar_configuracoes():
    resposta = supabase_admin.table("configuracoes").select("chave, valor").execute()
    linhas = {linha["chave"]: linha["valor"] for linha in (resposta.data or [])}

    configuracoes = {}
    for chave, valor_padrao in CONFIGURACOES_PADRAO.items():
        if chave in linhas:
            configuracoes[chave] = linhas[chave]
        else:
            supabase_admin.table("configuracoes").upsert({
                "chave": chave,
                "valor": valor_padrao,
            }).execute()
            configuracoes[chave] = valor_padrao

    return configuracoes


# Writes each top-level section of the configuration dictionary to its own
# row (chave/valor) in the "configuracoes" table
def salvar_configuracoes(configuracoes: dict):
    for chave, valor in configuracoes.items():
        supabase_admin.table("configuracoes").upsert({
            "chave": chave,
            "valor": valor,
            "atualizado_em": datetime.now(timezone.utc).isoformat(),
        }).execute()


# Masks an api_key, keeping only the last 4 characters visible
def mascarar_api_key(api_key: str) -> str:
    if len(api_key) <= 4:
        return "*" * len(api_key)
    return f"{'*' * (len(api_key) - 4)}{api_key[-4:]}"


@router.get('/gerais')
def obter_configuracoes_gerais():
    try:
        configuracoes = carregar_configuracoes()

        return {
            "sucesso": True,
            "configuracoes": configuracoes["gerais"],
        }

    except Exception as erro:
        print(f"Erro ao obter configurações gerais: {erro}")
        raise HTTPException(
            status_code=500,
            detail="Erro ao obter configurações gerais"
        )


@router.patch('/gerais')
def editar_configuracoes_gerais(dados: ConfiguracoesGeraisEditar):
    try:
        alteracoes = dados.model_dump(exclude_unset=True)

        if not alteracoes:
            raise HTTPException(
                status_code=400,
                detail="Nenhuma alteração foi enviada"
            )

        configuracoes = carregar_configuracoes()
        configuracoes["gerais"].update(alteracoes)
        salvar_configuracoes(configuracoes)

        return {
            "sucesso": True,
            "mensagem": "Configurações atualizadas.",
            "configuracoes": configuracoes["gerais"],
        }

    except HTTPException:
        raise

    except Exception as erro:
        print(f"Erro ao atualizar configurações gerais: {erro}")
        raise HTTPException(
            status_code=500,
            detail="Erro ao atualizar configurações gerais"
        )


@router.post('/gerais/logo')
def enviar_logo(
    arquivo: UploadFile = File(...),
    tipo: str = Form(...),
):
    try:
        if tipo not in ("logo", "favicon"):
            raise HTTPException(
                status_code=400,
                detail="Tipo inválido. Utilize 'logo' ou 'favicon'"
            )

        conteudo = arquivo.file.read()

        if len(conteudo) > 4 * 1024 * 1024:
            raise HTTPException(
                status_code=413,
                detail="Arquivo excede o tamanho máximo permitido"
            )

        extensao = (arquivo.filename or "").split(".")[-1].lower()
        caminho = f"branding/{tipo}-{uuid4()}.{extensao}"

        supabase_admin.storage.from_("avatars").upload(
            caminho,
            conteudo,
            {"content-type": arquivo.content_type or "image/png"},
        )

        url = supabase_admin.storage.from_("avatars").get_public_url(caminho)

        configuracoes = carregar_configuracoes()
        chave = "logo_url" if tipo == "logo" else "favicon_url"
        configuracoes["gerais"][chave] = url
        salvar_configuracoes(configuracoes)

        return {
            "sucesso": True,
            "url": url,
        }

    except HTTPException:
        raise

    except Exception as erro:
        print(f"Erro ao enviar arquivo: {erro}")
        raise HTTPException(
            status_code=500,
            detail="Erro ao enviar arquivo"
        )


@router.get('/autenticacao')
def obter_configuracoes_autenticacao():
    try:
        configuracoes = carregar_configuracoes()

        return {
            "sucesso": True,
            "configuracoes": configuracoes["autenticacao"],
        }

    except Exception as erro:
        print(f"Erro ao obter configurações de autenticação: {erro}")
        raise HTTPException(
            status_code=500,
            detail="Erro ao obter configurações de autenticação"
        )


@router.patch('/autenticacao')
def editar_configuracoes_autenticacao(dados: ConfiguracoesAutenticacaoEditar):
    try:
        alteracoes = dados.model_dump(exclude_unset=True)

        if not alteracoes:
            raise HTTPException(
                status_code=400,
                detail="Nenhuma alteração foi enviada"
            )

        configuracoes = carregar_configuracoes()
        configuracoes["autenticacao"].update(alteracoes)
        salvar_configuracoes(configuracoes)

        return {
            "sucesso": True,
            "mensagem": "Configurações atualizadas.",
            "configuracoes": configuracoes["autenticacao"],
        }

    except HTTPException:
        raise

    except Exception as erro:
        print(f"Erro ao atualizar configurações de autenticação: {erro}")
        raise HTTPException(
            status_code=500,
            detail="Erro ao atualizar configurações de autenticação"
        )


@router.get('/conteudo')
def obter_configuracoes_conteudo():
    try:
        configuracoes = carregar_configuracoes()

        return {
            "sucesso": True,
            "configuracoes": configuracoes["conteudo"],
        }

    except Exception as erro:
        print(f"Erro ao obter configurações de conteúdo: {erro}")
        raise HTTPException(
            status_code=500,
            detail="Erro ao obter configurações de conteúdo"
        )


@router.patch('/conteudo')
def editar_configuracoes_conteudo(dados: ConfiguracoesConteudoEditar):
    try:
        alteracoes = dados.model_dump(exclude_unset=True)

        if not alteracoes:
            raise HTTPException(
                status_code=400,
                detail="Nenhuma alteração foi enviada"
            )

        configuracoes = carregar_configuracoes()
        configuracoes["conteudo"].update(alteracoes)
        salvar_configuracoes(configuracoes)

        return {
            "sucesso": True,
            "mensagem": "Configurações atualizadas.",
            "configuracoes": configuracoes["conteudo"],
        }

    except HTTPException:
        raise

    except Exception as erro:
        print(f"Erro ao atualizar configurações de conteúdo: {erro}")
        raise HTTPException(
            status_code=500,
            detail="Erro ao atualizar configurações de conteúdo"
        )


@router.get('/ia')
def obter_configuracoes_ia():
    try:
        configuracoes = carregar_configuracoes()

        return {
            "sucesso": True,
            "configuracoes": configuracoes["ia"],
        }

    except Exception as erro:
        print(f"Erro ao obter configurações de IA: {erro}")
        raise HTTPException(
            status_code=500,
            detail="Erro ao obter configurações de IA"
        )


@router.patch('/ia')
def editar_configuracoes_ia(dados: ConfiguracoesIaEditar):
    try:
        alteracoes = dados.model_dump(exclude_unset=True)

        if not alteracoes:
            raise HTTPException(
                status_code=400,
                detail="Nenhuma alteração foi enviada"
            )

        configuracoes = carregar_configuracoes()
        configuracoes["ia"].update(alteracoes)
        salvar_configuracoes(configuracoes)

        return {
            "sucesso": True,
            "mensagem": "Configurações atualizadas.",
            "configuracoes": configuracoes["ia"],
        }

    except HTTPException:
        raise

    except Exception as erro:
        print(f"Erro ao atualizar configurações de IA: {erro}")
        raise HTTPException(
            status_code=500,
            detail="Erro ao atualizar configurações de IA"
        )


@router.post('/ia/testar')
def testar_configuracoes_ia(dados: ConfiguracoesIaTestar):
    try:
        # NOTE: usa o provider configurado globalmente (get_ai_provider() é um
        # singleton cacheado, construído a partir das variáveis de ambiente em
        # config.py). Este teste sempre roda contra o modelo atualmente
        # configurado, ignorando dados.modelo/temperatura/max_tokens do
        # request — simplificação aceitável para este endpoint de diagnóstico.
        provider = get_ai_provider()

        mensagens = []
        if dados.prompt_base:
            mensagens.append({"role": "system", "content": dados.prompt_base})
        mensagens.append({"role": "user", "content": dados.prompt_teste})

        inicio = time.time()

        try:
            resposta_texto = provider.responder_chat(mensagens)
        except AIIndisponivelError as erro:
            raise HTTPException(
                status_code=502,
                detail=f"Não foi possível se comunicar com o provedor de IA: {erro}"
            )

        tempo_resposta_ms = int((time.time() - inicio) * 1000)
        tokens_utilizados = len(dados.prompt_base.split()) + len(dados.prompt_teste.split()) + len(resposta_texto.split())

        return {
            "sucesso": True,
            "resposta": resposta_texto,
            "tokens_utilizados": tokens_utilizados,
            "tempo_resposta_ms": tempo_resposta_ms,
        }

    except HTTPException:
        raise

    except Exception as erro:
        print(f"Erro ao testar configurações de IA: {erro}")
        raise HTTPException(
            status_code=502,
            detail="Erro ao testar configurações de IA"
        )


@router.get('/notificacoes')
def obter_configuracoes_notificacoes():
    try:
        configuracoes = carregar_configuracoes()

        return {
            "sucesso": True,
            "configuracoes": configuracoes["notificacoes"],
        }

    except Exception as erro:
        print(f"Erro ao obter configurações de notificações: {erro}")
        raise HTTPException(
            status_code=500,
            detail="Erro ao obter configurações de notificações"
        )


@router.patch('/notificacoes')
def editar_configuracoes_notificacoes(dados: ConfiguracoesNotificacoesEditar):
    try:
        alteracoes = dados.model_dump(exclude_unset=True)

        if not alteracoes:
            raise HTTPException(
                status_code=400,
                detail="Nenhuma alteração foi enviada"
            )

        configuracoes = carregar_configuracoes()
        configuracoes["notificacoes"].update(alteracoes)
        salvar_configuracoes(configuracoes)

        return {
            "sucesso": True,
            "mensagem": "Configurações atualizadas.",
            "configuracoes": configuracoes["notificacoes"],
        }

    except HTTPException:
        raise

    except Exception as erro:
        print(f"Erro ao atualizar configurações de notificações: {erro}")
        raise HTTPException(
            status_code=500,
            detail="Erro ao atualizar configurações de notificações"
        )


@router.get('/integracoes')
def listar_integracoes():
    try:
        configuracoes = carregar_configuracoes()

        return {
            "sucesso": True,
            "integracoes": configuracoes["integracoes"],
        }

    except Exception as erro:
        print(f"Erro ao listar integrações: {erro}")
        raise HTTPException(
            status_code=500,
            detail="Erro ao listar integrações"
        )


@router.patch('/integracoes/{integracao_id}')
def editar_integracao(integracao_id: UUID, dados: IntegracaoEditar):
    try:
        alteracoes = dados.model_dump(exclude_unset=True)

        if not alteracoes:
            raise HTTPException(
                status_code=400,
                detail="Nenhuma alteração foi enviada"
            )

        configuracoes = carregar_configuracoes()
        integracoes = configuracoes["integracoes"]

        integracao = next(
            (item for item in integracoes if item["id"] == str(integracao_id)),
            None,
        )

        if not integracao:
            raise HTTPException(
                status_code=404,
                detail="Integração não encontrada"
            )

        if "ativo" in alteracoes:
            integracao["ativo"] = alteracoes["ativo"]

        if "webhook_url" in alteracoes:
            integracao["webhook_url"] = alteracoes["webhook_url"]

        if "api_key" in alteracoes:
            integracao["api_key_mascarada"] = mascarar_api_key(alteracoes["api_key"])
            integracao["conectado_em"] = datetime.now(timezone.utc).isoformat()

        salvar_configuracoes(configuracoes)

        return {
            "sucesso": True,
            "mensagem": "Integração atualizada.",
            "integracao": integracao,
        }

    except HTTPException:
        raise

    except Exception as erro:
        print(f"Erro ao atualizar integração: {erro}")
        raise HTTPException(
            status_code=500,
            detail="Erro ao atualizar integração"
        )


