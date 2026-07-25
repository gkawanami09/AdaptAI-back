from pydantic import BaseModel, Field
from datetime import datetime
from uuid import UUID


class TopicoCriar(BaseModel):
    materia_id: UUID
    nome: str = Field(min_length=2, max_length=100)
    descricao: str | None = None
    ordem: int = Field(default=0, ge=0)
    icone: str | None = None
    ativo: bool = True


class TopicoEditar(BaseModel):
    materia_id: UUID | None = None
    nome: str | None = Field(
        default=None,
        min_length=2,
        max_length=100
    )
    descricao: str | None = None
    ordem: int | None = Field(default=None, ge=0)
    icone: str | None = None
    ativo: bool | None = None

class TopicoGet(BaseModel):
    topico_id: UUID
    materia_id: UUID
    nome: str | None = None
    slug: str
    descricao: str
    ordem: int
    atualizado_em: datetime
    icone: str | None = None
    ativo: bool