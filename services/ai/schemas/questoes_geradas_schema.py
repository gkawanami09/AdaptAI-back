from pydantic import BaseModel, Field


class QuestaoGeradaIA(BaseModel):
    """Uma questão de múltipla escolha gerada pela IA para uma matéria/tópico.

    `resposta_correta` é a letra da alternativa correta (ex.: "A"), e deve
    corresponder a um item presente em `alternativas`.
    """

    enunciado: str
    alternativas: list[str] = Field(default_factory=list)
    resposta_correta: str
    explicacao: str = ""
    dificuldade: str = "medio"


class QuestoesGeradasIA(BaseModel):
    """Contrato de resposta que a IA deve retornar ao gerar novas questões."""

    questoes: list[QuestaoGeradaIA] = Field(default_factory=list)
