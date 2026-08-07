from typing import Literal
from pydantic import BaseModel, Field

ChatRole = Literal['ada', 'user', 'system']
ChatFerramenta = Literal[
    'questoes', 'resumo', 'revisao', 'plano-estudos',
    'redacao', 'explicacao', 'lista', 'simulados',
]


class ChatSugestaoAcao(BaseModel):
    tipo: ChatFerramenta
    label: str


class ChatConversaResumo(BaseModel):
    id: str
    slug: str
    titulo: str
    atualizadoEm: str


class GetChatConversasResponse(BaseModel):
    conversas: list[ChatConversaResumo]


class PostChatConversaParams(BaseModel):
    titulo: str | None = None


class ChatMensagem(BaseModel):
    id: str
    sender: ChatRole
    texto: str
    timestamp: str
    anexos: list[dict] = Field(default_factory=list)
    sugestoes: list[ChatSugestaoAcao] | None = None
    tokens: int | None = None
    modelo: str | None = None


class GetChatConversaResponse(BaseModel):
    id: str
    slug: str
    titulo: str
    mensagens: list[ChatMensagem]


class PostChatMensagemParams(BaseModel):
    mensagem: str = Field(min_length=1)


class PostChatMensagemResponse(BaseModel):
    user: ChatMensagem
    assistant: ChatMensagem
    tempoProcessamentoMs: int
    modelo: str | None = None
    sugestoes: list[ChatSugestaoAcao] | None = None


class PatchChatConversaParams(BaseModel):
    titulo: str = Field(min_length=1)


class PostChatRegenerarResponse(BaseModel):
    assistant: ChatMensagem


class ChatModelo(BaseModel):
    id: str
    nome: str
    descricao: str
    padrao: bool


class GetChatModelosResponse(BaseModel):
    modelos: list[ChatModelo]
