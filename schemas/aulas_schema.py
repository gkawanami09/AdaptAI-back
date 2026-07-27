from pydantic import BaseModel, Field, model_validator
from uuid import UUID
from typing import Literal


class ConteudoTextoDados(BaseModel):
    titulo: str = Field(min_length=2, max_length=150)
    descricao: str = Field(min_length=1)


class ConteudoVideoDados(BaseModel):
    titulo: str = Field(min_length=2, max_length=150)
    video_link: str
    descricao: str | None = None


class AulaConteudo(BaseModel):
    tipo: Literal["video", "texto"]
    ordem: int = Field(ge=0)
    duracao: int = Field(ge=0)
    ativo: bool = True
    texto: ConteudoTextoDados | None = None
    video: ConteudoVideoDados | None = None

    @model_validator(mode="after")
    def validar_detalhe(self):
        if self.tipo == "texto" and self.texto is None:
            raise ValueError("Conteúdo do tipo 'texto' precisa do campo 'texto'")
        if self.tipo == "video" and self.video is None:
            raise ValueError("Conteúdo do tipo 'video' precisa do campo 'video'")
        return self


class AulaCriar(BaseModel):
    materia_id: UUID
    topico_id: UUID | None = None
    titulo: str = Field(min_length=2, max_length=150)
    resumo: str | None = None
    dificuldade: Literal["basico", "medio", "dificil"] = "basico"
    mais_cobrado: bool = False
    ordem: int = Field(default=0, ge=0)
    ativo: bool = True
    conteudos: list[AulaConteudo] = []


class AulaEditar(BaseModel):
    materia_id: UUID | None = None
    topico_id: UUID | None = None
    titulo: str | None = Field(
        default=None,
        min_length=2,
        max_length=150
    )
    resumo: str | None = None
    dificuldade: Literal["basico", "medio", "dificil"] | None = None
    mais_cobrado: bool | None = None
    ordem: int | None = Field(default=None, ge=0)
    ativo: bool | None = None
    conteudos: list[AulaConteudo] | None = None
