from collections import deque
from datetime import date, timedelta

from services.plano_estudos.contexto import (
    AulaContexto,
    DiaGerado,
    PlanoEstudosContexto,
    PlanoGerado,
    ProvaContexto,
    SessaoGerada,
)
from services.plano_estudos.generator_base import PlanoEstudosGenerator

PESO_PROVA_SEM_DATA = 0.2
# Deve ficar sempre abaixo de 1/dias_ate para qualquer prova real, mesmo
# uma muito distante — garante que matéria sem relação com prova nenhuma
# nunca ultrapasse a prioridade de uma matéria realmente cobrada.
PESO_MATERIA_SEM_PROVA_RELACIONADA = 1e-6

LIMITE_DIAS_FASE_MISTA = 60
LIMITE_DIAS_FASE_REVISAO = 30


def _peso_prova(dias_ate: int | None) -> float:
    if dias_ate is None:
        return PESO_PROVA_SEM_DATA
    return 1.0 / dias_ate


def _dias_ate(hoje: date, data_prova: date | None) -> int | None:
    if data_prova is None:
        return None
    dias = (data_prova - hoje).days
    return dias if dias > 0 else None


def _fase_do_dia(dia: date, provas_validas: list[tuple[ProvaContexto, date]]) -> str:
    dias_restantes = [
        (data_prova - dia).days for _, data_prova in provas_validas
        if (data_prova - dia).days > 0
    ]

    if not dias_restantes:
        return "novo"

    dias_ate_mais_proxima = min(dias_restantes)

    if dias_ate_mais_proxima <= LIMITE_DIAS_FASE_REVISAO:
        return "revisao"
    if dias_ate_mais_proxima <= LIMITE_DIAS_FASE_MISTA:
        return "misto"
    return "novo"


class DeterministicPlanGenerator(PlanoEstudosGenerator):
    """Distribui aulas reais do banco em um cronograma, priorizando
    matérias pela proximidade das provas selecionadas. Não usa IA —
    100% determinístico e testável com dados fixos.
    """

    def gerar(self, contexto: PlanoEstudosContexto) -> PlanoGerado:
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

        materias_ordenadas = self._priorizar_materias(contexto, provas_validas, hoje)

        filas: dict[str, deque[AulaContexto]] = {}
        for materia in materias_ordenadas:
            aulas = contexto.aulas_por_materia.get(materia, [])
            aptas = [a for a in aulas if a.duracao_minutos <= contexto.tempo_por_dia_minutos]

            ignoradas = len(aulas) - len(aptas)
            if ignoradas:
                avisos.append(
                    f"{ignoradas} aula(s) de '{materia}' ignorada(s): duração maior que o "
                    "tempo diário disponível."
                )

            if not aulas:
                avisos.append(f"Matéria '{materia}' não possui aulas cadastradas no banco.")

            filas[materia] = deque(aptas)

        historico: dict[str, list[AulaContexto]] = {materia: [] for materia in materias_ordenadas}

        dias_gerados: list[DiaGerado] = []
        for dia in self._dias_calendario(hoje, periodo_fim, contexto.dias_estudo):
            fase = _fase_do_dia(dia, provas_validas)
            sessoes = self._distribuir_dia(
                fase, materias_ordenadas, filas, historico, contexto.tempo_por_dia_minutos
            )
            if sessoes:
                dias_gerados.append(DiaGerado(data=dia, sessoes=sessoes))

        return PlanoGerado(
            periodo_inicio=hoje,
            periodo_fim=periodo_fim,
            dias=dias_gerados,
            avisos=avisos,
        )

    def _priorizar_materias(
        self,
        contexto: PlanoEstudosContexto,
        provas_validas: list[tuple[ProvaContexto, date]],
        hoje: date,
    ) -> list[str]:
        scores: dict[str, float] = {}

        for materia in contexto.materias_selecionadas:
            score = 0.0
            for prova, data_prova in provas_validas:
                relacionadas = contexto.materias_por_prova.get(prova.slug, set())
                if materia in relacionadas:
                    score += _peso_prova(_dias_ate(hoje, data_prova))

            for prova in contexto.provas:
                if prova.data_prova is not None:
                    continue
                relacionadas = contexto.materias_por_prova.get(prova.slug, set())
                if materia in relacionadas:
                    score += _peso_prova(None)

            if score == 0.0:
                score = PESO_MATERIA_SEM_PROVA_RELACIONADA

            scores[materia] = score

        return sorted(
            contexto.materias_selecionadas,
            key=lambda m: (-scores[m], contexto.materias_selecionadas.index(m)),
        )

    def _dias_calendario(self, inicio: date, fim: date, dias_estudo: list[str]) -> list[date]:
        dias_estudo_set = set(dias_estudo)
        dias: list[date] = []
        cursor = inicio

        while cursor <= fim:
            if cursor.strftime("%A").lower() in dias_estudo_set:
                dias.append(cursor)
            cursor += timedelta(days=1)

        return dias

    def _distribuir_dia(
        self,
        fase: str,
        materias_ordenadas: list[str],
        filas: dict[str, deque[AulaContexto]],
        historico: dict[str, list[AulaContexto]],
        tempo_por_dia_minutos: int,
    ) -> list[SessaoGerada]:
        if not materias_ordenadas:
            return []

        sessoes: list[SessaoGerada] = []
        restante = tempo_por_dia_minutos
        indice = 0
        sem_progresso = 0
        rodada = 0

        while restante > 0 and sem_progresso < len(materias_ordenadas):
            materia = materias_ordenadas[indice % len(materias_ordenadas)]
            indice += 1
            rodada += 1

            sessao = None

            preferir_revisao = fase == "revisao" and rodada % 2 == 0 and historico[materia]
            if preferir_revisao:
                sessao = self._sessao_revisao(materia, historico, restante)

            if sessao is None and filas[materia] and filas[materia][0].duracao_minutos <= restante:
                aula = filas[materia].popleft()
                sessao = SessaoGerada(
                    materia=materia,
                    aula_id=aula.id,
                    titulo=aula.titulo,
                    duracao_minutos=aula.duracao_minutos,
                    tipo="teoria",
                )
                historico[materia].append(aula)

            if sessao is None and fase in ("misto", "revisao"):
                sessao = self._sessao_revisao(materia, historico, restante)

            if sessao is not None:
                sessoes.append(sessao)
                restante -= sessao.duracao_minutos
                sem_progresso = 0
            else:
                sem_progresso += 1

        return sessoes

    def _sessao_revisao(
        self, materia: str, historico: dict[str, list[AulaContexto]], restante: int
    ) -> SessaoGerada | None:
        if not historico[materia]:
            return None

        aula = historico[materia][-1]
        if aula.duracao_minutos > restante:
            return None

        return SessaoGerada(
            materia=materia,
            aula_id=aula.id,
            titulo=aula.titulo,
            duracao_minutos=aula.duracao_minutos,
            tipo="revisao",
        )
