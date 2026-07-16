from pydantic import BaseModel, Field
from typing import Literal


class MateriaCriar(BaseModel):
    nome: str = Field(min_length=2, max_length=100)

    area: Literal[
        "matematica",
        "natureza",
        "humanas",
        "linguagens",
        "redacao"
    ]

    icone: str
    cor: str

    ordem: int = Field(default=0, ge=0)
    ativo: bool = True
    
    
class MateriaEditar(BaseModel):
    nome: str | None = Field(
        default=None,
        min_length=2,
        max_length=100
    )

    area: Literal[
        "matematica",
        "natureza",
        "humanas",
        "linguagens",
        "redacao"
    ] | None = None

    icone: str | None = None
    cor: str | None = None
    ordem: int | None = Field(default=None, ge=0)
    ativo: bool | None = None