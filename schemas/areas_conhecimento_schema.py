from pydantic import BaseModel, Field


class AreaConhecimentoCriar(BaseModel):
    nome: str = Field(min_length=2, max_length=100)
    descricao: str | None = None
    ativo: bool = True


class AreaConhecimentoEditar(BaseModel):
    nome: str | None = Field(default=None, min_length=2, max_length=100)
    descricao: str | None = None
    ativo: bool | None = None
