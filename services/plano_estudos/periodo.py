from datetime import date, timedelta

from services.plano_estudos.contexto import PlanoEstudosContexto, ProvaContexto

# Compartilhado entre os geradores (determinístico e IA) para que ambos
# calculem o mesmo período e tratem provas sem data / já ocorridas da
# mesma forma — regra de negócio, não detalhe de um gerador específico.


def calcular_periodo(
    contexto: PlanoEstudosContexto,
) -> tuple[date, list[tuple[ProvaContexto, date]], list[str]]:
    avisos: list[str] = []
    hoje = contexto.data_inicio

    provas_validas: list[tuple[ProvaContexto, date]] = []
    for prova in contexto.provas:
        if prova.data_prova is None:
            avisos.append(f"Prova '{prova.slug}' sem data cadastrada — ignorada na priorização por proximidade.")
            continue
        if prova.data_prova <= hoje:
            avisos.append(f"Prova '{prova.slug}' já ocorreu — ignorada na geração do cronograma.")
            continue
        provas_validas.append((prova, prova.data_prova))

    if provas_validas:
        periodo_fim = max(data_prova for _, data_prova in provas_validas)
    else:
        periodo_fim = hoje + timedelta(weeks=contexto.duracao_maxima_semanas)
        avisos.append(
            "Nenhuma prova selecionada possui data válida — usando período padrão de "
            f"{contexto.duracao_maxima_semanas} semanas."
        )

    return periodo_fim, provas_validas, avisos


def dias_calendario(inicio: date, fim: date, dias_estudo: list[str]) -> list[date]:
    dias_estudo_set = set(dias_estudo)
    dias: list[date] = []
    cursor = inicio

    while cursor <= fim:
        if cursor.strftime("%A").lower() in dias_estudo_set:
            dias.append(cursor)
        cursor += timedelta(days=1)

    return dias
