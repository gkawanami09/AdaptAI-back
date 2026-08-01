from pydantic import BaseModel, Field, EmailStr
from typing import Literal


class UsuarioCriar(BaseModel):
    nome: str = Field(min_length=2, max_length=100)
    email: EmailStr
    cargo: Literal["aluno", "moderador", "editor", "administrador"] = "aluno"


class UsuarioEditar(BaseModel):
    nome: str | None = Field(default=None, min_length=2, max_length=100)
    email: EmailStr | None = None
    cargo: Literal["aluno", "moderador", "editor", "administrador"] | None = None


class UsuarioCargoEditar(BaseModel):
    cargo: Literal["aluno", "moderador", "editor", "administrador"]


class UsuarioSuspender(BaseModel):
    motivo: str = Field(min_length=3, max_length=500)
    duracao_dias: int = Field(ge=1, le=365)


class UsuarioBanir(BaseModel):
    motivo: str = Field(min_length=3, max_length=500)
