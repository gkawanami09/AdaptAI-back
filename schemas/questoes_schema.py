from pydantic import BaseModel, Field, model_validator
from typing import Literal
from uuid import UUID


class AlternativaCriar(BaseModel):
    letra: Literal["A", "B", "C", "D", "E"]
    texto: str
    correta: bool = False


class QuestaoCriar(BaseModel):
    tipo_prova_id: UUID | None = None
    materia_id: UUID
    topico_id: UUID | None = None
    aula_id: UUID | None = None
    ano: int | None = None
    dificuldade: Literal["facil", "medio", "dificil"] = "medio"
    enunciado: str = Field(min_length=1)
    imagem_url: str | None = None
    dica: str | None = None
    explicacao: str | None = None
    ativo: bool = True
    alternativas: list[AlternativaCriar]

    @model_validator(mode="after")
    def validar_alternativas(self):
        if len(self.alternativas) < 2:
            raise ValueError("A questão deve ter no mínimo 2 alternativas")

        corretas = [alt for alt in self.alternativas if alt.correta]

        if len(corretas) != 1:
            raise ValueError("A questão deve ter exatamente 1 alternativa correta")

        letras = [alt.letra for alt in self.alternativas]

        if len(letras) != len(set(letras)):
            raise ValueError("Não pode haver alternativas com a mesma letra")

        return self


class QuestaoEditar(BaseModel):
    tipo_prova_id: UUID | None = None
    materia_id: UUID | None = None
    topico_id: UUID | None = None
    aula_id: UUID | None = None
    ano: int | None = None
    dificuldade: Literal["facil", "medio", "dificil"] | None = None
    enunciado: str | None = Field(default=None, min_length=1)
    imagem_url: str | None = None
    dica: str | None = None
    explicacao: str | None = None
    ativo: bool | None = None
    alternativas: list[AlternativaCriar] | None = None

    @model_validator(mode="after")
    def validar_alternativas(self):
        if self.alternativas is None:
            return self

        if len(self.alternativas) < 2:
            raise ValueError("A questão deve ter no mínimo 2 alternativas")

        corretas = [alt for alt in self.alternativas if alt.correta]

        if len(corretas) != 1:
            raise ValueError("A questão deve ter exatamente 1 alternativa correta")

        letras = [alt.letra for alt in self.alternativas]

        if len(letras) != len(set(letras)):
            raise ValueError("Não pode haver alternativas com a mesma letra")

        return self


class TipoProvaCriar(BaseModel):
    nome: str = Field(min_length=2, max_length=100)
    descricao: str | None = None
    ativo: bool = True


class TipoProvaEditar(BaseModel):
    nome: str | None = Field(default=None, min_length=2, max_length=100)
    descricao: str | None = None
    ativo: bool | None = None


class ItemListaCriar(BaseModel):
    questao_id: UUID
    ordem: int = Field(default=0, ge=0)


class ListaQuestoesCriar(BaseModel):
    titulo: str = Field(min_length=2, max_length=150)
    descricao: str | None = None
    tipo_prova_id: UUID | None = None
    materia_id: UUID | None = None
    topico_id: UUID | None = None
    dificuldade: Literal["facil", "medio", "dificil"] | None = None
    tipo_lista: Literal[
        "fixa",
        "gerada_ia",
        "questoes_erradas",
        "favoritas",
        "revisao",
    ]
    itens: list[ItemListaCriar] = Field(default_factory=list)


class ListaQuestoesEditar(BaseModel):
    titulo: str | None = Field(default=None, min_length=2, max_length=150)
    descricao: str | None = None
    tipo_prova_id: UUID | None = None
    materia_id: UUID | None = None
    topico_id: UUID | None = None
    dificuldade: Literal["facil", "medio", "dificil"] | None = None
    tipo_lista: Literal[
        "fixa",
        "gerada_ia",
        "questoes_erradas",
        "favoritas",
        "revisao",
    ] | None = None
    itens: list[ItemListaCriar] | None = None


class ItemListaAdicionar(BaseModel):
    questao_id: UUID
    ordem: int = Field(default=0, ge=0)


class ItemListaReordenar(BaseModel):
    questao_id: UUID
    ordem: int = Field(ge=0)


class ItensListaReordenarLote(BaseModel):
    itens: list[ItemListaReordenar] = Field(min_length=1)
