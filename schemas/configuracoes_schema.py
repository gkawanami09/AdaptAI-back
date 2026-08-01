from pydantic import BaseModel, Field
from typing import Literal


class ConfiguracoesGeraisEditar(BaseModel):
    nome_plataforma: str | None = Field(default=None, min_length=2, max_length=100)
    slogan: str | None = Field(default=None, max_length=200)
    descricao: str | None = None
    idioma: str | None = None
    timezone: str | None = None
    formato_data: str | None = None
    tema: Literal["claro", "escuro"] | None = None


class ConfiguracoesAutenticacaoEditar(BaseModel):
    tempo_sessao_min: int | None = Field(default=None, ge=1)
    login_google_ativo: bool | None = None
    login_microsoft_ativo: bool | None = None
    autenticacao_dois_fatores_ativo: bool | None = None
    reset_senha_ativo: bool | None = None
    senha_tamanho_minimo: int | None = Field(default=None, ge=4, le=64)
    senha_exigir_numero: bool | None = None
    senha_exigir_maiuscula: bool | None = None
    senha_exigir_caractere_especial: bool | None = None


class ConfiguracoesConteudoEditar(BaseModel):
    itens_por_pagina: int | None = Field(default=None, ge=1, le=100)
    tamanho_maximo_upload_mb: int | None = Field(default=None, ge=1)
    tipos_arquivo_permitidos: list[str] | None = None
    editor_padrao: Literal["rich-text", "markdown"] | None = None
    auto_salvamento_ativo: bool | None = None
    auto_salvamento_intervalo_seg: int | None = Field(default=None, ge=5)


class ConfiguracoesIaEditar(BaseModel):
    modelo: str | None = None
    temperatura: float | None = Field(default=None, ge=0, le=2)
    max_tokens: int | None = Field(default=None, ge=1, le=32000)
    prompt_base: str | None = None
    limite_geracoes_dia: int | None = Field(default=None, ge=0)


class ConfiguracoesIaTestar(BaseModel):
    modelo: str
    temperatura: float = Field(ge=0, le=2)
    max_tokens: int = Field(ge=1, le=32000)
    prompt_base: str
    prompt_teste: str = Field(min_length=1)


class ConfiguracoesNotificacoesEditar(BaseModel):
    email_ativo: bool | None = None
    push_ativo: bool | None = None
    alertas_internos_ativo: bool | None = None
    evento_novo_usuario: bool | None = None
    evento_questao_criada: bool | None = None
    evento_questao_editada: bool | None = None
    evento_lista_publicada: bool | None = None
    evento_prova_criada: bool | None = None
    evento_prova_publicada: bool | None = None
    evento_usuario_completou_lista: bool | None = None
    resumo_diario_email: bool | None = None
    resumo_semanal_email: bool | None = None


class IntegracaoEditar(BaseModel):
    ativo: bool | None = None
    api_key: str | None = None
    webhook_url: str | None = None
