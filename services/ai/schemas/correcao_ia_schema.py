from pydantic import BaseModel, Field


class AvaliacaoArgumentativaIA(BaseModel):
    """Contrato de resposta que a IA deve retornar ao avaliar uma redação.

    Cobre apenas o que o motor Python (services/correcao) não avalia:
    argumentação, coerência e proposta de intervenção/conclusão. A IA
    nunca deve recalcular gramática, estrutura ou estatísticas — esses
    dados já vêm prontos no relatório enviado a ela como entrada.
    """

    nota_argumentacao: int = Field(ge=0, le=200)
    nota_coerencia: int = Field(ge=0, le=200)
    nota_conclusao: int = Field(ge=0, le=200)
    pontos_fortes: list[str] = Field(default_factory=list)
    pontos_fracos: list[str] = Field(default_factory=list)
    sugestoes: list[str] = Field(default_factory=list)
    exemplos_de_reescrita: list[str] = Field(default_factory=list)
    resumo_final: str = ""
