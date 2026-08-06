"""Camada de IA para o módulo de Redação.

`corrigir_redacao` já delega para a camada de IA desacoplada em
services/ai/ (interface AIProvider + factory), que fala com o modelo
configurado (Ollama, vLLM ou outro servidor OpenAI-compatible) via
AI_PROVIDER/AI_BASE_URL/AI_MODEL no .env. Os demais métodos ainda não
foram implementados — cada um representa um ponto de integração
futuro e deve lançar NotImplementedError até ser conectado. Controllers
e rotas não precisam ser alterados quando a implementação for
adicionada — basta preencher o corpo destes métodos.
"""

from pydantic import BaseModel

from schemas.correcao_schema import RedacaoInput
from services.ai.factory import get_ai_provider
from services.correcao.orquestrador import CorrecaoOrquestrador


class CorrectionResult(BaseModel):
    nota_total: int
    competencia_1: int
    competencia_2: int
    competencia_3: int
    competencia_4: int
    competencia_5: int
    feedback_geral: str
    feedback_competencias: dict[str, str]
    pontos_fortes: list[str]
    pontos_fracos: list[str]
    erros_gramaticais: list[str]
    sugestoes: list[str]
    versao_revisada: str


class SuggestedTheme(BaseModel):
    titulo: str
    descricao: str
    motivo: str
    nivel: str


class WritingProblems(BaseModel):
    gramatica: list[str]
    coesao: list[str]
    coerencia: list[str]
    argumentacao: list[str]
    repertorio: list[str]
    intervencao: list[str]
    introducao: list[str]
    desenvolvimento: list[str]
    conclusao: list[str]
    pontuacao: list[str]
    ortografia: list[str]


class RedacaoAIService:
    """Serviço de IA para o módulo de Redação.

    `corrigir_redacao` roda o motor objetivo (services/correcao) e, com
    o relatório resultante, chama o AIProvider configurado para avaliar
    argumentação/coerência/proposta de intervenção. Os demais métodos
    ainda não estão implementados.
    """

    def __init__(self) -> None:
        self._orquestrador = CorrecaoOrquestrador()

    def corrigir_redacao(self, texto: str, tema_id: str) -> CorrectionResult:
        analise_objetiva = self._orquestrador.analisar(RedacaoInput(texto=texto))
        avaliacao_ia = get_ai_provider().corrigir_redacao(texto, analise_objetiva)

        nota = analise_objetiva.nota
        competencia_3 = round(avaliacao_ia.nota_argumentacao)
        competencia_4 = round(avaliacao_ia.nota_coerencia)
        competencia_5 = round(avaliacao_ia.nota_conclusao)

        return CorrectionResult(
            nota_total=nota.gramatica + nota.estrutura + nota.coesao + competencia_3 + competencia_4 + competencia_5,
            competencia_1=nota.gramatica,
            competencia_2=nota.estrutura,
            competencia_3=competencia_3,
            competencia_4=competencia_4,
            competencia_5=competencia_5,
            feedback_geral=avaliacao_ia.resumo_final,
            feedback_competencias={
                "competencia_3": ", ".join(avaliacao_ia.pontos_fracos) if avaliacao_ia.pontos_fracos else "",
            },
            pontos_fortes=avaliacao_ia.pontos_fortes,
            pontos_fracos=avaliacao_ia.pontos_fracos,
            erros_gramaticais=[erro.mensagem for erro in analise_objetiva.gramatica.erros],
            sugestoes=avaliacao_ia.sugestoes,
            versao_revisada="\n\n".join(avaliacao_ia.exemplos_de_reescrita),
        )

    def sugerir_temas(self, perfil_usuario: dict) -> list[SuggestedTheme]:
        raise NotImplementedError("IA ainda não implementada")

    def analisar_problemas(self, texto: str) -> WritingProblems:
        raise NotImplementedError("IA ainda não implementada")

    def gerar_feedback(self, texto: str, tema_id: str) -> str:
        raise NotImplementedError("IA ainda não implementada")

    def gerar_nota(self, texto: str, tema_id: str) -> int:
        raise NotImplementedError("IA ainda não implementada")

    def extrair_competencias(self, texto: str, tema_id: str) -> dict[str, int]:
        raise NotImplementedError("IA ainda não implementada")
