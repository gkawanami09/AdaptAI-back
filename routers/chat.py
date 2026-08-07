import logging

from fastapi import APIRouter, HTTPException, Depends

from utils.autenticacao import pegar_usuario_atual
from services.ai.base import AIIndisponivelError, AIRespostaInvalidaError
from services.chat_ai_service import ChatAIService
from services.conversation_service import ConversationService
from schemas.chat_schema import (
    GetChatConversasResponse,
    PostChatConversaParams,
    ChatConversaResumo,
    GetChatConversaResponse,
    ChatMensagem,
    PostChatMensagemParams,
    PostChatMensagemResponse,
    PatchChatConversaParams,
    PostChatRegenerarResponse,
    GetChatModelosResponse,
)

logger = logging.getLogger("chat_router")

router = APIRouter(
    prefix='/aluno/chat',
    tags=['Aluno - Chat'],
)

conversation_service = ConversationService()
chat_ai_service = ChatAIService()


def _mapear_role_banco_para_api(role: str) -> str:
    return "ada" if role == "assistant" else role


def _mensagem_para_schema(mensagem: dict) -> ChatMensagem:
    return ChatMensagem(
        id=mensagem["id"],
        sender=_mapear_role_banco_para_api(mensagem["role"]),
        texto=mensagem["content"],
        timestamp=mensagem["criado_em"],
        anexos=[],
    )


def _conversa_para_resumo(conversa: dict) -> ChatConversaResumo:
    return ChatConversaResumo(
        id=conversa["id"],
        slug=conversation_service.gerar_slug(conversa["id"], conversa["titulo"]),
        titulo=conversa["titulo"],
        atualizadoEm=conversa["atualizado_em"],
    )


@router.get('/conversas', response_model=GetChatConversasResponse)
def listar_conversas(usuario_atual=Depends(pegar_usuario_atual)):
    try:
        conversas = conversation_service.listar_conversas(str(usuario_atual.id))
        return {"conversas": [_conversa_para_resumo(c) for c in conversas]}

    except HTTPException:
        raise
    except Exception as erro:
        logger.exception("Erro ao listar conversas do chat")
        raise HTTPException(status_code=500, detail="Erro ao listar conversas")


@router.post('/conversas', status_code=201, response_model=ChatConversaResumo)
def criar_conversa(dados: PostChatConversaParams, usuario_atual=Depends(pegar_usuario_atual)):
    try:
        conversa = conversation_service.criar_conversa(str(usuario_atual.id), dados.titulo)
        return _conversa_para_resumo(conversa)

    except HTTPException:
        raise
    except Exception as erro:
        logger.exception("Erro ao criar conversa do chat")
        raise HTTPException(status_code=500, detail="Erro ao criar conversa")


@router.get('/conversas/{conversa_id}', response_model=GetChatConversaResponse)
def obter_conversa(conversa_id: str, usuario_atual=Depends(pegar_usuario_atual)):
    try:
        conversa = conversation_service.obter_conversa_do_aluno(conversa_id, str(usuario_atual.id))
        mensagens = conversation_service.listar_mensagens(conversa_id)

        return GetChatConversaResponse(
            id=conversa["id"],
            slug=conversation_service.gerar_slug(conversa["id"], conversa["titulo"]),
            titulo=conversa["titulo"],
            mensagens=[_mensagem_para_schema(m) for m in mensagens],
        )

    except HTTPException:
        raise
    except Exception as erro:
        logger.exception("Erro ao buscar conversa do chat")
        raise HTTPException(status_code=500, detail="Erro ao buscar conversa")


@router.post('/conversas/{conversa_id}/mensagens', response_model=PostChatMensagemResponse)
def enviar_mensagem(conversa_id: str, dados: PostChatMensagemParams, usuario_atual=Depends(pegar_usuario_atual)):
    try:
        if not dados.mensagem.strip():
            raise HTTPException(status_code=422, detail="Mensagem não pode estar vazia")

        conversa = conversation_service.obter_conversa_do_aluno(conversa_id, str(usuario_atual.id))

        historico_bruto = conversation_service.listar_mensagens(conversa_id)
        eh_primeira_mensagem = len(historico_bruto) == 0
        historico = [{"role": m["role"], "content": m["content"]} for m in historico_bruto]

        mensagem_usuario = conversation_service.salvar_mensagem(
            conversa_id=conversa_id,
            role="user",
            content=dados.mensagem,
        )

        try:
            resultado_ia = chat_ai_service.gerar_resposta(historico, dados.mensagem)
        except (AIIndisponivelError, AIRespostaInvalidaError):
            raise HTTPException(status_code=503, detail="Não foi possível gerar resposta.")

        mensagem_assistente = conversation_service.salvar_mensagem(
            conversa_id=conversa_id,
            role="assistant",
            content=resultado_ia.texto,
        )

        conversation_service.tocar_conversa(conversa_id)
        if eh_primeira_mensagem:
            conversation_service.atualizar_titulo_automatico_se_necessario(conversa, dados.mensagem)

        return PostChatMensagemResponse(
            user=_mensagem_para_schema(mensagem_usuario),
            assistant=_mensagem_para_schema(mensagem_assistente),
            tempoProcessamentoMs=resultado_ia.tempo_processamento_ms,
            modelo=resultado_ia.modelo,
            sugestoes=None,
        )

    except HTTPException:
        raise
    except Exception as erro:
        logger.exception("Erro ao processar mensagem do chat")
        raise HTTPException(status_code=500, detail="Erro ao processar mensagem")


@router.delete('/conversas/{conversa_id}', status_code=204)
def excluir_conversa(conversa_id: str, usuario_atual=Depends(pegar_usuario_atual)):
    try:
        conversation_service.excluir_conversa(conversa_id, str(usuario_atual.id))

    except HTTPException:
        raise
    except Exception as erro:
        logger.exception("Erro ao excluir conversa do chat")
        raise HTTPException(status_code=500, detail="Erro ao excluir conversa")


@router.patch('/conversas/{conversa_id}', response_model=ChatConversaResumo)
def renomear_conversa(conversa_id: str, dados: PatchChatConversaParams, usuario_atual=Depends(pegar_usuario_atual)):
    try:
        if not dados.titulo.strip():
            raise HTTPException(status_code=422, detail="Título não pode estar vazio")

        conversa = conversation_service.renomear_conversa(conversa_id, str(usuario_atual.id), dados.titulo)
        return _conversa_para_resumo(conversa)

    except HTTPException:
        raise
    except Exception as erro:
        logger.exception("Erro ao renomear conversa do chat")
        raise HTTPException(status_code=500, detail="Erro ao renomear conversa")


@router.post('/conversas/{conversa_id}/regenerar', response_model=PostChatRegenerarResponse)
def regenerar_resposta(conversa_id: str, usuario_atual=Depends(pegar_usuario_atual)):
    try:
        conversation_service.obter_conversa_do_aluno(conversa_id, str(usuario_atual.id))

        ultima_assistente = conversation_service.obter_ultima_mensagem_por_role(conversa_id, "assistant")
        ultima_usuario = conversation_service.obter_ultima_mensagem_por_role(conversa_id, "user")
        if ultima_usuario is None:
            raise HTTPException(status_code=404, detail="Não há mensagens para regenerar")

        if ultima_assistente is not None:
            conversation_service.excluir_mensagem(ultima_assistente["id"])

        historico_bruto = [
            m for m in conversation_service.listar_mensagens(conversa_id)
            if m["id"] != (ultima_assistente["id"] if ultima_assistente else None)
        ]
        historico_sem_ultima_pergunta = [
            {"role": m["role"], "content": m["content"]}
            for m in historico_bruto
            if m["id"] != ultima_usuario["id"]
        ]

        try:
            resultado_ia = chat_ai_service.gerar_resposta(historico_sem_ultima_pergunta, ultima_usuario["content"])
        except (AIIndisponivelError, AIRespostaInvalidaError):
            raise HTTPException(status_code=503, detail="Não foi possível gerar resposta.")

        nova_mensagem_assistente = conversation_service.salvar_mensagem(
            conversa_id=conversa_id,
            role="assistant",
            content=resultado_ia.texto,
        )
        conversation_service.tocar_conversa(conversa_id)

        return PostChatRegenerarResponse(assistant=_mensagem_para_schema(nova_mensagem_assistente))

    except HTTPException:
        raise
    except Exception as erro:
        logger.exception("Erro ao regenerar resposta do chat")
        raise HTTPException(status_code=500, detail="Erro ao regenerar resposta")


@router.get('/modelos', response_model=GetChatModelosResponse)
def listar_modelos(usuario_atual=Depends(pegar_usuario_atual)):
    import config

    return GetChatModelosResponse(
        modelos=[
            {
                "id": config.AI_MODEL,
                "nome": "Ada",
                "descricao": "Modelo padrão",
                "padrao": True,
            }
        ]
    )


# --- Ferramentas da IA (tool calling) ---------------------------------
# Endpoints preparados desde já para o frontend consumir, mas ainda não
# implementados. Cada ferramenta futura deve implementar AITool
# (services/ai/tools/base.py) e ser registrada em um ToolExecutor.

def _not_implemented():
    raise HTTPException(status_code=501, detail="Ferramenta ainda não implementada")


@router.post('/tools/questoes')
def tool_questoes(payload: dict, usuario_atual=Depends(pegar_usuario_atual)):
    _not_implemented()


@router.post('/tools/resumo')
def tool_resumo(payload: dict, usuario_atual=Depends(pegar_usuario_atual)):
    _not_implemented()


@router.post('/tools/revisao')
def tool_revisao(payload: dict, usuario_atual=Depends(pegar_usuario_atual)):
    _not_implemented()


@router.post('/tools/plano-estudos')
def tool_plano_estudos(payload: dict, usuario_atual=Depends(pegar_usuario_atual)):
    _not_implemented()


@router.post('/tools/redacao')
def tool_redacao(payload: dict, usuario_atual=Depends(pegar_usuario_atual)):
    _not_implemented()


@router.post('/tools/explicacao')
def tool_explicacao(payload: dict, usuario_atual=Depends(pegar_usuario_atual)):
    _not_implemented()


@router.post('/tools/lista')
def tool_lista(payload: dict, usuario_atual=Depends(pegar_usuario_atual)):
    _not_implemented()


@router.post('/tools/simulados')
def tool_simulados(payload: dict, usuario_atual=Depends(pegar_usuario_atual)):
    _not_implemented()
