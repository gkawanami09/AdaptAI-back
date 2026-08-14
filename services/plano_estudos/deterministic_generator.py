from collections import deque
from datetime import date

from services.plano_estudos.contexto import (
    AulaContexto,
    DiaGerado,
    PlanoEstudosContexto,
    PlanoGerado,
    ProvaContexto,
    SessaoGerada,
)
from services.plano_estudos.generator_base import PlanoEstudosGenerator
from services.plano_estudos.periodo import calcular_periodo, dias_calendario

PESO_PROVA_SEM_DATA = 0.2
# Deve ficar sempre abaixo de 1/dias_ate para qualquer prova real, mesmo
# uma muito distante — garante que matéria sem relação com prova nenhuma
# nunca ultrapasse a prioridade de uma matéria realmente cobrada.
PESO_MATERIA_SEM_PROVA_RELACIONADA = 1e-6

LIMITE_DIAS_FASE_MISTA = 60
LIMITE_DIAS_FASE_REVISAO = 30

# Aulas mais cobradas no vestibular vão primeiro na fila de cada matéria;
# dentro do mesmo nível de importância, as mais básicas vêm antes das
# difíceis — empates remanescentes preservam a ordem curricular original
# (ordem_topico, ordem_aula).
DIFICULDADE_PESO = {"basico": 0, "medio": 1, "dificil": 2}


def _prioridade_aula(aula: AulaContexto) -> tuple:
    return (
        0 if aula.mais_cobrado else 1,
        DIFICULDADE_PESO.get(aula.dificuldade, 1),
        aula.ordem_topico,
        aula.ordem_aula,
    )


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

    def gerar(
        self,
        contexto: PlanoEstudosContexto,
        historico_inicial: dict[str, list[AulaContexto]] | None = None,
        aulas_ja_usadas: set[str] | None = None,
        data_inicio_override: date | None = None,
    ) -> PlanoGerado:
        """`historico_inicial`/`aulas_ja_usadas`/`data_inicio_override` existem
        para o replanejamento (services/plano_estudos_wizard_service.py:
        `replanejar_apos_conclusao`) retomar a partir do que o aluno já
        estudou de verdade, em vez de gerar o cronograma do zero. Na criação
        do plano, esses parâmetros ficam com o padrão (geração do zero).
        """
        hoje = data_inicio_override or contexto.data_inicio
        periodo_fim, provas_validas, avisos = calcular_periodo(contexto)

        materias_ordenadas = self._priorizar_materias(contexto, provas_validas, hoje)
        aulas_ja_usadas = aulas_ja_usadas or set()

        filas: dict[str, deque[AulaContexto]] = {}
        for materia in materias_ordenadas:
            aulas = contexto.aulas_por_materia.get(materia, [])
            candidatas = [a for a in aulas if a.id not in aulas_ja_usadas]
            aptas = [a for a in candidatas if a.duracao_minutos <= contexto.tempo_por_dia_minutos]

            ignoradas = len(candidatas) - len(aptas)
            if ignoradas:
                avisos.append(
                    f"{ignoradas} aula(s) de '{materia}' ignorada(s): duração maior que o "
                    "tempo diário disponível."
                )

            if not aulas:
                avisos.append(f"Matéria '{materia}' não possui aulas cadastradas no banco.")

            aptas.sort(key=_prioridade_aula)
            filas[materia] = deque(aptas)

        historico: dict[str, list[AulaContexto]] = {
            materia: list((historico_inicial or {}).get(materia, []))
            for materia in materias_ordenadas
        }
        # Cursor de rotação da revisão por matéria — evita repetir sempre a
        # mesma aula (ver _sessao_revisao).
        indice_revisao: dict[str, int] = {materia: 0 for materia in materias_ordenadas}

        dias_gerados: list[DiaGerado] = []
        for dia in dias_calendario(hoje, periodo_fim, contexto.dias_estudo):
            fase = _fase_do_dia(dia, provas_validas)
            sessoes = self._distribuir_dia(
                fase, materias_ordenadas, filas, historico, indice_revisao, contexto.tempo_por_dia_minutos
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

    def _distribuir_dia(
        self,
        fase: str,
        materias_ordenadas: list[str],
        filas: dict[str, deque[AulaContexto]],
        historico: dict[str, list[AulaContexto]],
        indice_revisao: dict[str, int],
        tempo_por_dia_minutos: int,
    ) -> list[SessaoGerada]:
        if not materias_ordenadas:
            return []

        # No máximo 1 sessão por matéria por dia — sem isso, uma matéria com
        # pouco conteúdo (ou nenhum novo) acaba reaproveitando a mesma aula
        # como revisão em todas as voltas do round-robin do dia, repetindo-a
        # várias vezes seguidas sem nenhum ganho pedagógico.
        sessoes: list[SessaoGerada] = []
        restante = tempo_por_dia_minutos

        for materia in materias_ordenadas:
            if restante <= 0:
                break

            sessao = None

            if fase == "revisao" and historico[materia]:
                sessao = self._sessao_revisao(materia, historico, indice_revisao, restante)

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
                sessao = self._sessao_revisao(materia, historico, indice_revisao, restante)

            if sessao is not None:
                sessoes.append(sessao)
                restante -= sessao.duracao_minutos

        return sessoes

    def _sessao_revisao(
        self,
        materia: str,
        historico: dict[str, list[AulaContexto]],
        indice_revisao: dict[str, int],
        restante: int,
    ) -> SessaoGerada | None:
        aulas_vistas = historico[materia]
        if not aulas_vistas:
            return None

        # Circula por todas as aulas já vistas da matéria em vez de sempre
        # repetir a última — sem isso, a fase de revisão (que pode durar
        # semanas) mostra a mesma aula todo santo dia.
        indice = indice_revisao[materia] % len(aulas_vistas)
        aula = aulas_vistas[indice]
        if aula.duracao_minutos > restante:
            return None

        indice_revisao[materia] = indice + 1

        return SessaoGerada(
            materia=materia,
            aula_id=aula.id,
            titulo=aula.titulo,
            duracao_minutos=aula.duracao_minutos,
            tipo="revisao",
        )
