import logging
from dataclasses import replace
from datetime import date

from services.ai.base import AIIndisponivelError, AIRespostaInvalidaError
from services.ai.factory import get_ai_provider
from services.ai.json_parsing import extrair_e_validar_json
from services.ai.prompts.plano_estudos import SYSTEM_PROMPT, montar_prompt_plano_estudos
from services.ai.schemas.plano_estudos_ia_schema import PlanoEstudosIA
from services.plano_estudos.contexto import (
    AulaContexto,
    DiaGerado,
    PlanoEstudosContexto,
    PlanoGerado,
    SessaoGerada,
)
from services.plano_estudos.deterministic_generator import DeterministicPlanGenerator
from services.plano_estudos.generator_base import PlanoEstudosGenerator
from services.plano_estudos.periodo import calcular_periodo, dias_calendario

logger = logging.getLogger("plano_estudos_ai_generator")

# Resposta vazia/malformada costuma ser um problema transitório do
# servidor de inferência (ex.: content vazio) — vale tentar de novo
# antes de desistir e cair no fallback determinístico.
MAX_TENTATIVAS_IA = 2


class AIPlanGenerator(PlanoEstudosGenerator):
    """Usa o modelo de IA já configurado no projeto (services/ai/,
    Ollama ou qualquer servidor OpenAI-compatible via AI_PROVIDER) para
    montar o cronograma.

    A IA só escolhe QUAIS aulas do catálogo real usar em cada dia — o
    título, a duração e a existência de cada aula são sempre resolvidos
    no backend a partir do banco, nunca aceitos como veio da IA. Depois
    da resposta, o backend ainda revalida server-side que nenhuma sessão
    usa aula fora do catálogo, fora do período, em dia não selecionado
    ou que estoura o tempo diário — a IA nunca pode violar essas regras,
    só decide a distribuição dentro delas.

    Se a IA estiver indisponível ou responder algo inválido, cai
    automaticamente para o DeterministicPlanGenerator em vez de falhar
    a geração do plano inteiro.
    """

    def __init__(self, fallback: PlanoEstudosGenerator | None = None):
        self._fallback = fallback if fallback is not None else DeterministicPlanGenerator()

    def gerar(self, contexto: PlanoEstudosContexto) -> PlanoGerado:
        try:
            return self._gerar_com_ia(contexto)
        except (AIIndisponivelError, AIRespostaInvalidaError):
            if self._fallback is None:
                raise

            logger.exception("Falha ao gerar plano de estudos via IA — usando fallback determinístico")
            plano_fallback = self._fallback.gerar(contexto)
            return replace(
                plano_fallback,
                avisos=[
                    "IA indisponível ou respondeu algo inválido — plano gerado pelo motor determinístico.",
                    *plano_fallback.avisos,
                ],
            )

    def _gerar_com_ia(self, contexto: PlanoEstudosContexto) -> PlanoGerado:
        hoje = contexto.data_inicio
        periodo_fim, provas_validas, avisos = calcular_periodo(contexto)

        catalogo_aulas, aula_por_id = self._montar_catalogo(contexto)
        if not catalogo_aulas:
            avisos.append("Nenhuma aula elegível encontrada no catálogo — plano gerado sem sessões.")
            return PlanoGerado(periodo_inicio=hoje, periodo_fim=periodo_fim, dias=[], avisos=avisos)

        prompt = montar_prompt_plano_estudos(
            provas=self._montar_provas_prompt(contexto.provas, provas_validas, hoje),
            catalogo_aulas=catalogo_aulas,
            tempo_por_dia_minutos=contexto.tempo_por_dia_minutos,
            dias_estudo=contexto.dias_estudo,
            data_inicio=hoje.isoformat(),
            data_fim=periodo_fim.isoformat(),
        )

        provider = get_ai_provider()
        mensagens = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ]

        plano_ia = None
        ultimo_erro: AIRespostaInvalidaError | None = None
        for tentativa in range(1, MAX_TENTATIVAS_IA + 1):
            conteudo = provider.responder_chat(mensagens)
            try:
                plano_ia = extrair_e_validar_json(conteudo, PlanoEstudosIA)
                break
            except AIRespostaInvalidaError as erro:
                ultimo_erro = erro
                logger.warning(
                    "Resposta da IA inválida na tentativa %d/%d: %s",
                    tentativa, MAX_TENTATIVAS_IA, erro,
                )

        if plano_ia is None:
            raise ultimo_erro

        dias_gerados = self._validar_e_montar_dias(
            plano_ia, aula_por_id, hoje, periodo_fim, contexto.dias_estudo, contexto.tempo_por_dia_minutos
        )

        if not dias_gerados:
            avisos.append("A IA não retornou nenhuma sessão aproveitável dentro das regras do plano.")

        return PlanoGerado(periodo_inicio=hoje, periodo_fim=periodo_fim, dias=dias_gerados, avisos=avisos)

    def _montar_catalogo(
        self, contexto: PlanoEstudosContexto
    ) -> tuple[list[dict], dict[str, AulaContexto]]:
        catalogo: list[dict] = []
        aula_por_id: dict[str, AulaContexto] = {}

        for materia in contexto.materias_selecionadas:
            for aula in contexto.aulas_por_materia.get(materia, []):
                if aula.duracao_minutos > contexto.tempo_por_dia_minutos:
                    continue

                catalogo.append({
                    "aula_id": aula.id,
                    "materia": aula.materia_slug,
                    "titulo": aula.titulo,
                    "duracao_minutos": aula.duracao_minutos,
                    "ordem_topico": aula.ordem_topico,
                    "ordem_aula": aula.ordem_aula,
                })
                aula_por_id[aula.id] = aula

        return catalogo, aula_por_id

    def _montar_provas_prompt(self, provas, provas_validas, hoje: date) -> list[dict]:
        dias_ate_por_slug = {prova.slug: (data_prova - hoje).days for prova, data_prova in provas_validas}
        return [
            {"slug": prova.slug, "nome": prova.nome, "dias_ate": dias_ate_por_slug.get(prova.slug)}
            for prova in provas
        ]

    def _validar_e_montar_dias(
        self,
        plano_ia: PlanoEstudosIA,
        aula_por_id: dict[str, AulaContexto],
        hoje: date,
        periodo_fim: date,
        dias_estudo: list[str],
        tempo_por_dia_minutos: int,
    ) -> list[DiaGerado]:
        dias_validos = set(dias_calendario(hoje, periodo_fim, dias_estudo))
        sessoes_por_dia: dict[date, list[SessaoGerada]] = {}

        for dia_ia in plano_ia.dias:
            try:
                dia_data = date.fromisoformat(dia_ia.data)
            except ValueError:
                continue

            if dia_data not in dias_validos:
                continue

            restante = tempo_por_dia_minutos
            sessoes_validadas: list[SessaoGerada] = []
            materias_usadas_no_dia: set[str] = set()

            for sessao_ia in dia_ia.sessoes:
                aula = aula_por_id.get(sessao_ia.aula_id)
                if aula is None or aula.duracao_minutos > restante:
                    continue
                # No máximo 1 sessão por matéria por dia — mesma regra do
                # gerador determinístico, mesmo motivo (não repetir a mesma
                # matéria/aula várias vezes no mesmo dia).
                if aula.materia_slug in materias_usadas_no_dia:
                    continue
                materias_usadas_no_dia.add(aula.materia_slug)

                sessoes_validadas.append(SessaoGerada(
                    materia=aula.materia_slug,
                    aula_id=aula.id,
                    titulo=aula.titulo,
                    duracao_minutos=aula.duracao_minutos,
                    tipo=sessao_ia.tipo,
                ))
                restante -= aula.duracao_minutos

            if sessoes_validadas:
                sessoes_por_dia.setdefault(dia_data, []).extend(sessoes_validadas)

        return [DiaGerado(data=dia, sessoes=sessoes_por_dia[dia]) for dia in sorted(sessoes_por_dia.keys())]
