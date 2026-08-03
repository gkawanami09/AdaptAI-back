from pydantic import BaseModel
from typing import Literal, Optional
from uuid import UUID


class CategoriaBiblioteca(BaseModel):
    id: UUID
    nome: str


class AulaBiblioteca(BaseModel):
    id: UUID
    slug: Optional[str] = None
    titulo: str
    materia: str
    materia_cor: str
    icone: str
    icone_cor: str
    duracao_min: int
    dificuldade: str
    progresso: int
    status: Literal["concluida", "em-andamento", "nao-iniciada"]
    destaque: bool


class BibliotecaAulasResponse(BaseModel):
    total_aulas: int
    total_concluidas: int
    subtitulo: str
    categorias: list[CategoriaBiblioteca]
    aulas: list[AulaBiblioteca]


class ConteudoAulaBiblioteca(BaseModel):
    tipo: Literal["video", "texto"]
    ordem: int
    duracao_min: int
    titulo: str
    descricao: str
    video_link: Optional[str] = None


class AulaBibliotecaDetalhe(BaseModel):
    id: UUID
    slug: Optional[str] = None
    titulo: str
    materia: str
    materia_cor: str
    dificuldade: str
    progresso: int
    status: Literal["concluida", "em-andamento", "nao-iniciada"]
    conteudos: list[ConteudoAulaBiblioteca]
