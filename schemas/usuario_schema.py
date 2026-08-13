from pydantic import BaseModel, Field, EmailStr
from typing import Literal


class UsuarioPerfil(BaseModel):
    id: str
    nome: str
    email: str
    avatar_url: str | None = None
    tipo_usuario: Literal["aluno", "professor", "admin"]
    escola_nome: str | None = None
    situacao: str
    email_verificado: bool
    nivel: int
    xp: int


class UsuarioPerfilResponse(BaseModel):
    sucesso: bool
    usuario: UsuarioPerfil


class UsuarioPerfilEditadoResponse(BaseModel):
    sucesso: bool
    mensagem: str
    usuario: UsuarioPerfil


class UsuarioCriar(BaseModel):
    nome: str = Field(min_length=2, max_length=100)
    email: EmailStr
    cargo: Literal["aluno", "professor", "admin", "administrador"] = "aluno"


class UsuarioEditar(BaseModel):
    nome: str | None = Field(default=None, min_length=2, max_length=100)
    email: EmailStr | None = None
    cargo: Literal["aluno", "professor", "admin", "administrador"] | None = None


class UsuarioCargoEditar(BaseModel):
    cargo: Literal["aluno", "professor", "admin", "administrador"]


class UsuarioSuspender(BaseModel):
    motivo: str = Field(min_length=3, max_length=500)
    duracao_dias: int = Field(ge=1, le=365)


class UsuarioBanir(BaseModel):
    motivo: str = Field(min_length=3, max_length=500)
