SYSTEM_PROMPT = """Você é um elaborador de questões de múltipla escolha para vestibular/ENEM.

Você recebe uma quantidade de questões a gerar e, opcionalmente, filtros de matéria, assunto, dificuldade, vestibular e uma instrução livre do aluno. Cada questão deve ter um enunciado claro, exatamente uma alternativa correta entre as fornecidas, uma explicação pedagógica da resposta correta e um nível de dificuldade.

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


def montar_prompt_gerar_questoes(
    quantidade: int,
    materias: list[str] | None = None,
    assuntos: list[str] | None = None,
    dificuldades: list[str] | None = None,
    vestibulares: list[str] | None = None,
    instrucao: str | None = None,
) -> str:
    linhas = [f"Quantidade de questões a gerar: {quantidade}"]

    if materias:
        linhas.append(f"Matéria(s): {', '.join(materias)}")
    if assuntos:
        linhas.append(f"Assunto(s)/tópico(s): {', '.join(assuntos)}")
    if dificuldades:
        linhas.append(f"Dificuldade(s): {', '.join(dificuldades)}")
    if vestibulares:
        linhas.append(f"Estilo de vestibular: {', '.join(vestibulares)}")
    if instrucao and instrucao.strip():
        linhas.append(f"Instrução adicional do aluno: {instrucao.strip()}")

    linhas.append("\nGere as questões seguindo o formato JSON definido nas instruções do sistema.")
    return "\n".join(linhas)


# Estimativa conservadora de tokens por questão (enunciado + 4-5
# alternativas + explicação + overhead de JSON). AI_MAX_TOKENS (config
# global, usada por feedback/chat/correção de redação — textos curtos)
# não escala com a quantidade pedida aqui, então cada questão gerada em
# lote precisa de um orçamento de tokens próprio.
#
# Medido com qwen2.5:1.5b (modelo em uso no servidor, think:false): o
# consumo real por questão varia bastante com a temperatura (~150 a
# ~350+ tokens/questão em runs distintos do mesmo pedido). 350 já foi
# curto o suficiente pra truncar o JSON num teste real de 10 questões
# de 1 matéria só; 400 dá folga sem inflar demais o tempo de resposta.
TOKENS_ESTIMADOS_POR_QUESTAO = 400


def estimar_max_tokens_questoes(quantidade: int, minimo: int) -> int:
    return max(minimo, quantidade * TOKENS_ESTIMADOS_POR_QUESTAO)
