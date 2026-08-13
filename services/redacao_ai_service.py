"""Camada de IA para o módulo de Redação.

Todos os métodos delegam para a camada de IA desacoplada em
services/ai/ (interface AIProvider + factory), que fala com o modelo
configurado (Ollama, vLLM ou outro servidor OpenAI-compatible) via
AI_PROVIDER/AI_BASE_URL/AI_MODEL no .env. `sugerir_temas` e
`analisar_problemas` usam `responder_chat` + extração/validação local de
JSON (mesma técnica usada por `corrigir_redacao`, mas composta aqui na
camada de serviço, sem adicionar métodos novos à interface AIProvider).
"""

import json

from pydantic import BaseModel

from schemas.correcao_schema import RedacaoInput
from services.ai.factory import get_ai_provider
from services.ai.json_parsing import extrair_e_validar_json
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


class _SuggestedThemesWrapper(BaseModel):
    """Envelope interno usado apenas para validar a lista de temas que a
    IA retorna — `extrair_e_validar_json` espera um objeto JSON, não uma
    lista solta."""

    temas: list[SuggestedTheme]


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
    argumentação/coerência/proposta de intervenção. `gerar_nota` e
    `extrair_competencias` reaproveitam esse mesmo pipeline. `sugerir_temas`
    e `analisar_problemas` chamam `responder_chat` com um prompt próprio e
    validam a resposta como JSON. `gerar_feedback` delega diretamente para
    `AIProvider.gerar_feedback`.
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
        mensagens = [
            {
                "role": "system",
                "content": (
                    "Você é um professor de redação que sugere temas de redação dissertativo-"
                    "argumentativa (modelo ENEM) adequados ao perfil do aluno. Responda APENAS "
                    "com um JSON válido, sem texto antes ou depois, no formato:\n"
                    '{"temas": [{"titulo": <string>, "descricao": <string>, '
                    '"motivo": <string, por que esse tema é adequado a este aluno>, '
                    '"nivel": <"facil" | "medio" | "dificil">}, ...]}'
                ),
            },
            {
                "role": "user",
                "content": (
                    "Perfil do aluno:\n"
                    f"{json.dumps(perfil_usuario, ensure_ascii=False, indent=2)}\n\n"
                    "Sugira temas de redação adequados a este perfil."
                ),
            },
        ]

        resposta = get_ai_provider().responder_chat(mensagens)
        resultado = extrair_e_validar_json(resposta, _SuggestedThemesWrapper)
        return resultado.temas

    def analisar_problemas(self, texto: str) -> WritingProblems:
        mensagens = [
            {
                "role": "system",
                "content": (
                    "Você é um revisor de redações dissertativo-argumentativas (modelo ENEM). "
                    "Analise o texto do aluno e liste os problemas encontrados, agrupados por "
                    "categoria. Responda APENAS com um JSON válido, sem texto antes ou depois, "
                    "no formato:\n"
                    "{"
                    '"gramatica": [<string>, ...], "coesao": [<string>, ...], '
                    '"coerencia": [<string>, ...], "argumentacao": [<string>, ...], '
                    '"repertorio": [<string>, ...], "intervencao": [<string>, ...], '
                    '"introducao": [<string>, ...], "desenvolvimento": [<string>, ...], '
                    '"conclusao": [<string>, ...], "pontuacao": [<string>, ...], '
                    '"ortografia": [<string>, ...]'
                    "}\n"
                    "Se não houver problemas em uma categoria, retorne uma lista vazia para ela."
                ),
            },
            {
                "role": "user",
                "content": f'Redação do aluno:\n"""\n{texto}\n"""\n\nAnalise os problemas deste texto.',
            },
        ]

        resposta = get_ai_provider().responder_chat(mensagens)
        return extrair_e_validar_json(resposta, WritingProblems)

    def gerar_feedback(self, texto: str, tema_id: str) -> str:
        return get_ai_provider().gerar_feedback(texto, contexto={"tema_id": tema_id})

    def gerar_nota(self, texto: str, tema_id: str) -> int:
        return self.corrigir_redacao(texto, tema_id).nota_total

    def extrair_competencias(self, texto: str, tema_id: str) -> dict[str, int]:
        resultado = self.corrigir_redacao(texto, tema_id)
        return {
            "competencia_1": resultado.competencia_1,
            "competencia_2": resultado.competencia_2,
            "competencia_3": resultado.competencia_3,
            "competencia_4": resultado.competencia_4,
            "competencia_5": resultado.competencia_5,
        }
