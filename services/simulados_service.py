"""Cálculo puro do resultado de um simulado — sem I/O, testável em
isolamento. Persistência e orquestração ficam em routers/simulados.py,
seguindo a mesma separação já usada em services/redacao_correcao_service.py
(cálculo separado de gravação no banco).
"""

import random


def selecionar_questoes(pool_ids: list[str], quantidade: int) -> list[str]:
    """Amostra aleatória sem repetição. Se o pool for menor que a
    quantidade pedida, devolve o pool inteiro (não inventa questão)."""
    if quantidade >= len(pool_ids):
        return list(pool_ids)

    return random.sample(pool_ids, quantidade)


def selecionar_questoes_evitando(pool_ids: list[str], quantidade: int, evitar: set[str] | None = None) -> list[str]:
    """Como `selecionar_questoes`, mas prioriza não repetir IDs de
    `evitar` (ex.: questões já usadas na tentativa anterior do mesmo
    aluno, ao "refazer" um simulado) — só recorre a eles se o pool sem
    repetição não tiver questões suficientes."""
    evitar = evitar or set()
    preferidas = [q for q in pool_ids if q not in evitar]

    if len(preferidas) >= quantidade:
        return random.sample(preferidas, quantidade)

    reserva = [q for q in pool_ids if q in evitar]
    faltam = quantidade - len(preferidas)
    complemento = random.sample(reserva, faltam) if faltam < len(reserva) else reserva

    return preferidas + complemento


def calcular_resultado(respostas: list[bool]) -> dict:
    total = len(respostas)
    corretas = sum(1 for r in respostas if r)
    percentual = round((corretas / total) * 100) if total > 0 else 0
    nota_estimada = max(0, min(1000, round(percentual * 10)))

    return {
        "total_questoes": total,
        "respostas_corretas": corretas,
        "percentual_acerto": percentual,
        "nota_estimada": nota_estimada,
    }


def calcular_resultado_por_area(respostas_por_area: dict[str, list[bool]]) -> list[dict]:
    resultados = []
    for area, respostas in respostas_por_area.items():
        resultado = calcular_resultado(respostas)
        resultados.append({
            "area": area,
            "total_questoes": resultado["total_questoes"],
            "respostas_corretas": resultado["respostas_corretas"],
            "percentual_acerto": resultado["percentual_acerto"],
            "nota": resultado["nota_estimada"],
        })

    return resultados
