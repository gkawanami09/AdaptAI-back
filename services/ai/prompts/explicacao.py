SYSTEM_PROMPT = """Você é um tutor pedagógico especializado em explicar, de forma clara e didática, por que a resposta de um aluno a uma questão de múltipla escolha está errada.

Você recebe a questão (enunciado, alternativas e a resposta correta) e a resposta que o aluno escolheu. Explique o raciocínio correto, aponte o provável erro de raciocínio do aluno e ajude-o a entender o conceito — sem ser condescendente.

Responda em texto corrido, em português, sem formato JSON."""


def montar_prompt_explicacao_erro(questao: dict, resposta_aluno: str) -> str:
    enunciado = questao.get("enunciado", "")
    alternativas = questao.get("alternativas", [])
    resposta_correta = questao.get("resposta_correta", "")

    partes = [
        f"Enunciado da questão:\n{enunciado}",
        f"Alternativas:\n{alternativas}",
        f"Resposta correta: {resposta_correta}",
        f"Resposta do aluno: {resposta_aluno}",
        "Explique por que a resposta do aluno está incorreta e qual é o raciocínio certo.",
    ]
    return "\n\n".join(partes)
