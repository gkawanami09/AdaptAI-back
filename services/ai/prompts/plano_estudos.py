import json

SYSTEM_PROMPT = (
    "Você é um planejador pedagógico que monta cronogramas de estudo "
    "personalizados para estudantes brasileiros se preparando para "
    "vestibulares e o ENEM. Você só pode usar as aulas fornecidas no "
    "catálogo — nunca invente aulas, títulos ou durações. Responda "
    "SEMPRE com um único objeto JSON, sem texto fora do JSON, seguindo "
    "exatamente o formato pedido."
)

_FORMATO_JSON = """
Formato de resposta obrigatório (JSON), usando apenas aula_id do catálogo:
{
  "dias": [
    {
      "data": "AAAA-MM-DD",
      "sessoes": [
        {"aula_id": "<id do catálogo>", "tipo": "teoria"},
        {"aula_id": "<id do catálogo>", "tipo": "revisao"}
      ]
    }
  ]
}
"""


def montar_prompt_plano_estudos(
    provas: list[dict],
    catalogo_aulas: list[dict],
    tempo_por_dia_minutos: int,
    dias_estudo: list[str],
    data_inicio: str,
    data_fim: str,
) -> str:
    contexto = {
        "provas": provas,
        "catalogo_aulas": catalogo_aulas,
        "tempo_por_dia_minutos": tempo_por_dia_minutos,
        "dias_estudo": dias_estudo,
        "data_inicio": data_inicio,
        "data_fim": data_fim,
    }

    return (
        "Monte um cronograma de estudos com base neste contexto do aluno:\n"
        f"{json.dumps(contexto, ensure_ascii=False, indent=2)}\n\n"
        "Regras:\n"
        "- Use SOMENTE dias da semana listados em \"dias_estudo\" (valores em inglês).\n"
        "- Use SOMENTE datas entre \"data_inicio\" e \"data_fim\" (inclusive).\n"
        "- Use SOMENTE aula_id que existam em \"catalogo_aulas\" — nunca invente um id.\n"
        "- A soma das durações (campo \"duracao_minutos\" de cada aula no catálogo) das "
        "sessões de um mesmo dia não pode ultrapassar \"tempo_por_dia_minutos\".\n"
        "- Priorize matérias ligadas às provas com menos dias restantes "
        "(campo \"dias_ate\" de cada prova); provas sem \"dias_ate\" têm prioridade baixa.\n"
        "- Respeite a ordem de \"ordem_topico\"/\"ordem_aula\" de cada matéria no catálogo "
        "— não estude uma aula fora de ordem antes das anteriores da mesma matéria.\n"
        "- Nos primeiros dias do período, prefira conteúdo novo (\"tipo\": \"teoria\"). "
        "Conforme a prova mais próxima se aproxima, intercale com revisão "
        "(\"tipo\": \"revisao\") reutilizando um aula_id já usado antes para a mesma "
        "matéria.\n"
        "- Se não houver aula suficiente para preencher um dia inteiro, deixe o dia com "
        "menos sessões ou de fora — nunca repita uma aula nova como se fosse inédita.\n"
        f"{_FORMATO_JSON}"
    )
