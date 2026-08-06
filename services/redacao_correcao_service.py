"""Orquestra a correção completa de um envio de redação: roda o motor
objetivo (services/correcao), chama a IA (services/ai) e persiste o
resultado no formato consumido por GET /aluno/redacao/envios/{id}.

Roda de forma síncrona, mas é disparado em background pelo router
(FastAPI BackgroundTasks) — o POST de envio responde imediatamente com
status "pendente" e este módulo atualiza o registro no Supabase quando
a correção terminar.
"""

from database import supabase_admin
from schemas.correcao_schema import RedacaoInput
from services.ai.base import AIIndisponivelError, AIRespostaInvalidaError
from services.ai.factory import get_ai_provider
from services.correcao.orquestrador import CorrecaoOrquestrador

COMPETENCIA_META = {
    1: ("Domínio da norma culta", "Gramática, ortografia e pontuação", "blue"),
    2: ("Compreensão da proposta", "Estrutura e desenvolvimento do tema", "teal"),
    3: ("Argumentação", "Seleção e organização de argumentos", "purple"),
    4: ("Coerência e coesão", "Mecanismos linguísticos e articulação textual", "gold"),
    5: ("Proposta de intervenção", "Solução detalhada e respeitosa", "red"),
}

INSIGHT_ICONES = [("💡", "purple"), ("📚", "blue"), ("🧱", "green"), ("✍️", "gold")]
MELHORIA_ICONES = [("⚠️", "red"), ("🔁", "gold"), ("🎯", "purple")]

DEGRAU_ENEM = 40


def _arredondar_para_degrau_enem(nota: int) -> int:
    """Arredonda para o múltiplo de 40 mais próximo, limitado a 0-200 —
    a escala usada pelo ENEM para cada uma das 5 competências."""
    arredondado = round(nota / DEGRAU_ENEM) * DEGRAU_ENEM
    return max(0, min(200, arredondado))


def _status_label(nota_total: int) -> str:
    if nota_total >= 800:
        return "Excelente desempenho 🎉"
    if nota_total >= 600:
        return "Bom desempenho"
    if nota_total >= 400:
        return "Desempenho regular"
    return "Precisa de mais prática"


def _mensagem_motivacional(nota_total: int) -> str:
    if nota_total >= 800:
        return "Muito bom! Continue praticando para chegar aos 1000 pontos."
    if nota_total >= 600:
        return "Bom trabalho! Foque nos pontos de melhoria para subir ainda mais."
    return "Continue treinando — cada redação é um passo para melhorar."


def processar_correcao(envio_id: str, texto: str) -> None:
    try:
        supabase_admin.table("redacoes_enviadas").update({
            "status": "corrigindo",
        }).eq("id", envio_id).execute()

        analise_objetiva = CorrecaoOrquestrador().analisar(RedacaoInput(texto=texto))
        avaliacao_ia = get_ai_provider().corrigir_redacao(texto, analise_objetiva)

        nota = analise_objetiva.nota
        notas_por_competencia = {
            1: _arredondar_para_degrau_enem(nota.gramatica),
            2: _arredondar_para_degrau_enem(nota.estrutura),
            3: _arredondar_para_degrau_enem(avaliacao_ia.nota_argumentacao),
            4: _arredondar_para_degrau_enem(avaliacao_ia.nota_coerencia),
            5: _arredondar_para_degrau_enem(avaliacao_ia.nota_conclusao),
        }
        nota_total = sum(notas_por_competencia.values())

        competencias = [
            {
                "number": numero,
                "title": COMPETENCIA_META[numero][0],
                "description": COMPETENCIA_META[numero][1],
                "color": COMPETENCIA_META[numero][2],
                "nota": nota_valor,
                "notaMaxima": 200,
            }
            for numero, nota_valor in notas_por_competencia.items()
        ]

        insights = [
            {
                "id": str(indice + 1),
                "icon": INSIGHT_ICONES[indice % len(INSIGHT_ICONES)][0],
                "iconColor": INSIGHT_ICONES[indice % len(INSIGHT_ICONES)][1],
                "title": ponto,
                "description": ponto,
            }
            for indice, ponto in enumerate(avaliacao_ia.pontos_fortes)
        ]

        pontos_melhoria = [
            {
                "id": str(indice + 1),
                "icon": MELHORIA_ICONES[indice % len(MELHORIA_ICONES)][0],
                "iconColor": MELHORIA_ICONES[indice % len(MELHORIA_ICONES)][1],
                "title": ponto,
                "description": ponto,
            }
            for indice, ponto in enumerate(avaliacao_ia.pontos_fracos)
        ]

        repertorios_sugeridos = [
            {"id": str(indice + 1), "nome": sugestao, "descricao": sugestao}
            for indice, sugestao in enumerate(avaliacao_ia.sugestoes)
        ]

        analise_ia = {
            "notaTotal": nota_total,
            "notaMaxima": 1000,
            "statusLabel": _status_label(nota_total),
            "mensagemMotivacional": _mensagem_motivacional(nota_total),
            "competencias": competencias,
            "insights": insights,
            "pontosMelhoria": pontos_melhoria,
            "repertoriosSugeridos": repertorios_sugeridos,
            "resumoAda": avaliacao_ia.resumo_final,
        }

        supabase_admin.table("redacoes_enviadas").update({
            "status": "corrigida",
            "nota_total": nota_total,
            "feedback_geral": avaliacao_ia.resumo_final,
            "analise_ia": analise_ia,
        }).eq("id", envio_id).execute()

    except (AIIndisponivelError, AIRespostaInvalidaError) as erro:
        print(f"Erro ao corrigir redação {envio_id}: {erro}")
        supabase_admin.table("redacoes_enviadas").update({
            "status": "erro",
        }).eq("id", envio_id).execute()

    except Exception as erro:
        print(f"Erro inesperado ao corrigir redação {envio_id}: {erro}")
        supabase_admin.table("redacoes_enviadas").update({
            "status": "erro",
        }).eq("id", envio_id).execute()
