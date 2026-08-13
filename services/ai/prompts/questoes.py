SYSTEM_PROMPT = """Você é um elaborador de questões de múltipla escolha para vestibular/ENEM.

Você recebe uma matéria, um tópico e uma quantidade de questões a gerar. Cada questão deve ter um enunciado claro, exatamente uma alternativa correta entre as fornecidas, uma explicação pedagógica da resposta correta e um nível de dificuldade.

Responda APENAS com um JSON válido, sem nenhum texto antes ou depois, seguindo exatamente este formato:
{
  "questoes": [
    {
      "enunciado": <string>,
      "alternativas": [<string>, ...],
      "resposta_correta": <string, a alternativa correta, letra ou texto>,
      "explicacao": <string>,
      "dificuldade": <"facil" | "medio" | "dificil">
    },
    ...
  ]
}"""


def montar_prompt_gerar_questoes(materia: str, topico: str, quantidade: int) -> str:
    return (
        f"Matéria: {materia}\n"
        f"Tópico: {topico}\n"
        f"Quantidade de questões a gerar: {quantidade}\n\n"
        "Gere as questões seguindo o formato JSON definido nas instruções do sistema."
    )
