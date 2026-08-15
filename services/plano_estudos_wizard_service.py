import logging
from datetime import date, datetime, timezone

from fastapi import HTTPException

from database import supabase_admin
from utils.data_brasil import hoje_brasil
from schemas.plano_estudos_schema import PostCriarPlanoEstudosParams
from services.plano_estudos.ai_generator import AIPlanGenerator
from services.plano_estudos.contexto import (
    AulaContexto,
    DiaGerado,
    ListaContexto,
    PlanoEstudosContexto,
    ProvaContexto,
)
from services.plano_estudos.deterministic_generator import DeterministicPlanGenerator
from services.plano_estudos.generator_base import PlanoEstudosGenerator

logger = logging.getLogger("plano_estudos_wizard_service")


class PlanoEstudosWizardService:
    """Orquestra o wizard de criação de plano de estudos: valida as
    preferências do aluno contra o catálogo de provas/matérias, busca o
    contexto real do banco (provas, matérias, aulas) e delega a
    distribuição das sessões ao gerador.

    O motor determinístico é o padrão — instantâneo, gratuito e sempre
    correto (datas, limites diários etc. são garantidos em código). A
    IA só é usada quando o aluno pede explicitamente (`usar_ia=True`),
    e mesmo assim com fallback automático para o motor determinístico
    se ela falhar. Trocar/ajustar geradores não exige nenhuma mudança
    em router ou schema.
    """

    def __init__(
        self,
        deterministic_generator: PlanoEstudosGenerator | None = None,
        ai_generator: PlanoEstudosGenerator | None = None,
    ):
        self._deterministic_generator = deterministic_generator or DeterministicPlanGenerator()
        self._ai_generator = ai_generator or AIPlanGenerator(fallback=self._deterministic_generator)

    def _escolher_generator(self, dados) -> PlanoEstudosGenerator:
        if getattr(dados, "usar_ia", False):
            return self._ai_generator
        return self._deterministic_generator

    def listar_opcoes(self) -> dict:
        provas = (
            supabase_admin
            .table("tipos_prova")
            .select("slug, nome, descricao, data_prova")
            .eq("ativo", True)
            .order("nome")
            .execute()
            .data or []
        )

        materias = (
            supabase_admin
            .table("materias")
            .select("slug, nome")
            .eq("ativo", True)
            .order("ordem")
            .execute()
            .data or []
        )

        return {"provas": provas, "materias": materias}

    def _validar_slugs(self, provas: list[str], materias: list[str]) -> None:
        provas_validas = {
            p["slug"] for p in
            supabase_admin.table("tipos_prova").select("slug").in_("slug", provas).execute().data or []
        }
        materias_validas = {
            m["slug"] for m in
            supabase_admin.table("materias").select("slug").in_("slug", materias).execute().data or []
        }

        provas_invalidas = set(provas) - provas_validas
        materias_invalidas = set(materias) - materias_validas

        if provas_invalidas or materias_invalidas:
            partes = []
            if provas_invalidas:
                partes.append(f"provas inválidas: {sorted(provas_invalidas)}")
            if materias_invalidas:
                partes.append(f"matérias inválidas: {sorted(materias_invalidas)}")

            raise HTTPException(status_code=422, detail="; ".join(partes))

    def _montar_contexto(self, usuario_id: str, dados) -> PlanoEstudosContexto:
        hoje = hoje_brasil()

        provas_rows = (
            supabase_admin
            .table("tipos_prova")
            .select("id, slug, nome, data_prova")
            .in_("slug", dados.provas)
            .execute()
            .data or []
        )

        materias_rows = (
            supabase_admin
            .table("materias")
            .select("id, slug, nome")
            .in_("slug", dados.materias)
            .execute()
            .data or []
        )
        materia_id_para_slug = {m["id"]: m["slug"] for m in materias_rows}

        provas = [
            ProvaContexto(
                slug=p["slug"],
                nome=p["nome"],
                data_prova=date.fromisoformat(p["data_prova"]) if p.get("data_prova") else None,
            )
            for p in provas_rows
        ]

        ids_provas = [p["id"] for p in provas_rows]
        materias_por_prova = self._materias_relacionadas_por_prova(
            provas_rows, ids_provas, materia_id_para_slug
        )

        aulas_por_materia = self._aulas_por_materia(materias_rows)
        taxa_erro_por_materia, taxa_erro_por_topico = self._desempenho_por_materia_e_topico(
            usuario_id, materia_id_para_slug
        )
        listas_por_materia = self._listas_por_materia(materias_rows)

        return PlanoEstudosContexto(
            data_inicio=hoje,
            provas=provas,
            materias_selecionadas=dados.materias,
            materias_por_prova=materias_por_prova,
            aulas_por_materia=aulas_por_materia,
            tempo_por_dia_minutos=dados.tempo_por_dia_minutos,
            dias_estudo=dados.dias_estudo,
            taxa_erro_por_materia=taxa_erro_por_materia,
            taxa_erro_por_topico=taxa_erro_por_topico,
            listas_por_materia=listas_por_materia,
        )

    # Abaixo desse número de tentativas em uma matéria/tópico, a taxa de
    # erro não é confiável o bastante pra influenciar o plano — mesmo
    # limiar usado no gerador (services/plano_estudos/deterministic_generator.py).
    _MIN_TENTATIVAS_CONFIAVEL = 5

    def _desempenho_por_materia_e_topico(
        self, usuario_id: str, materia_id_para_slug: dict[str, str]
    ) -> tuple[dict[str, float], dict[str, float]]:
        """Taxa de erro (0-1) do aluno por matéria (chaveada por slug, pra
        casar com o resto do contexto) e por tópico (chaveada por
        topico_id), calculada a partir de tentativas_questoes — mesmo
        padrão de routers/dashboard.py (join `questoes!inner(...)`).
        """
        tentativas = (
            supabase_admin
            .table("tentativas_questoes")
            .select("acertou, questoes!inner(materia_id, topico_id)")
            .eq("usuario_id", usuario_id)
            .execute()
            .data or []
        )

        total_materia: dict[str, int] = {}
        erros_materia: dict[str, int] = {}
        total_topico: dict[str, int] = {}
        erros_topico: dict[str, int] = {}

        for tentativa in tentativas:
            questao = tentativa.get("questoes") or {}
            materia_id = questao.get("materia_id")
            topico_id = questao.get("topico_id")
            errou = tentativa.get("acertou") is False

            if materia_id:
                total_materia[materia_id] = total_materia.get(materia_id, 0) + 1
                if errou:
                    erros_materia[materia_id] = erros_materia.get(materia_id, 0) + 1

            if topico_id:
                total_topico[topico_id] = total_topico.get(topico_id, 0) + 1
                if errou:
                    erros_topico[topico_id] = erros_topico.get(topico_id, 0) + 1

        taxa_erro_por_materia = {
            materia_id_para_slug[materia_id]: erros_materia.get(materia_id, 0) / total
            for materia_id, total in total_materia.items()
            if total >= self._MIN_TENTATIVAS_CONFIAVEL and materia_id in materia_id_para_slug
        }

        taxa_erro_por_topico = {
            topico_id: erros_topico.get(topico_id, 0) / total
            for topico_id, total in total_topico.items()
            if total >= self._MIN_TENTATIVAS_CONFIAVEL
        }

        return taxa_erro_por_materia, taxa_erro_por_topico

    def _listas_por_materia(self, materias_rows: list[dict]) -> dict[str, ListaContexto]:
        """Uma lista de questões candidata por matéria (a primeira
        encontrada), usada nas sessões de reforço para matérias em que o
        aluno erra muito.
        """
        ids_materias = [m["id"] for m in materias_rows]
        if not ids_materias:
            return {}

        materia_id_para_slug = {m["id"]: m["slug"] for m in materias_rows}

        listas = (
            supabase_admin
            .table("listas_questoes")
            .select("id, materia_id")
            .in_("materia_id", ids_materias)
            .execute()
            .data or []
        )

        listas_por_materia: dict[str, ListaContexto] = {}
        for lista in listas:
            materia_slug = materia_id_para_slug.get(lista.get("materia_id"))
            if not materia_slug or materia_slug in listas_por_materia:
                continue
            listas_por_materia[materia_slug] = ListaContexto(id=lista["id"], materia_slug=materia_slug)

        return listas_por_materia

    def _materias_relacionadas_por_prova(
        self, provas_rows: list[dict], ids_provas: list[str], materia_id_para_slug: dict[str, str]
    ) -> dict[str, set[str]]:
        slug_por_prova_id = {p["id"]: p["slug"] for p in provas_rows}
        relacionadas: dict[str, set[str]] = {p["slug"]: set() for p in provas_rows}

        if not ids_provas:
            return relacionadas

        questoes = (
            supabase_admin
            .table("questoes")
            .select("materia_id, tipo_prova_id")
            .in_("tipo_prova_id", ids_provas)
            .eq("ativo", True)
            .execute()
            .data or []
        )

        listas = (
            supabase_admin
            .table("listas_questoes")
            .select("materia_id, tipo_prova_id")
            .in_("tipo_prova_id", ids_provas)
            .execute()
            .data or []
        )

        for linha in questoes + listas:
            materia_id = linha.get("materia_id")
            tipo_prova_id = linha.get("tipo_prova_id")
            materia_slug = materia_id_para_slug.get(materia_id)
            prova_slug = slug_por_prova_id.get(tipo_prova_id)

            if materia_slug and prova_slug:
                relacionadas[prova_slug].add(materia_slug)

        return relacionadas

    def _aulas_por_materia(self, materias_rows: list[dict]) -> dict[str, list[AulaContexto]]:
        ids_materias = [m["id"] for m in materias_rows]
        materia_id_para_slug = {m["id"]: m["slug"] for m in materias_rows}

        aulas_por_materia: dict[str, list[AulaContexto]] = {m["slug"]: [] for m in materias_rows}

        if not ids_materias:
            return aulas_por_materia

        topicos = (
            supabase_admin
            .table("topicos")
            .select("topico_id, materia_id, ordem")
            .in_("materia_id", ids_materias)
            .execute()
            .data or []
        )
        ordem_por_topico = {t["topico_id"]: t["ordem"] for t in topicos}

        aulas = (
            supabase_admin
            .table("aulas")
            .select("id, materia_id, topico_id, titulo, ordem, mais_cobrado, dificuldade")
            .in_("materia_id", ids_materias)
            .eq("ativo", True)
            .execute()
            .data or []
        )

        if not aulas:
            return aulas_por_materia

        ids_aulas = [a["id"] for a in aulas]
        conteudos = (
            supabase_admin
            .table("aulas_conteudo")
            .select("aula_id, duracao")
            .in_("aula_id", ids_aulas)
            .eq("ativo", True)
            .execute()
            .data or []
        )

        duracao_por_aula: dict[str, int] = {}
        for c in conteudos:
            duracao_por_aula[c["aula_id"]] = duracao_por_aula.get(c["aula_id"], 0) + c["duracao"]

        candidatas: dict[str, list[AulaContexto]] = {m["slug"]: [] for m in materias_rows}
        for aula in aulas:
            duracao = duracao_por_aula.get(aula["id"], 0)
            if duracao <= 0:
                continue

            materia_slug = materia_id_para_slug.get(aula["materia_id"])
            if not materia_slug:
                continue

            candidatas[materia_slug].append(AulaContexto(
                id=aula["id"],
                materia_slug=materia_slug,
                titulo=aula["titulo"],
                duracao_minutos=duracao,
                ordem_topico=ordem_por_topico.get(aula["topico_id"], 999999),
                ordem_aula=aula["ordem"],
                mais_cobrado=bool(aula.get("mais_cobrado")),
                dificuldade=aula.get("dificuldade") or "medio",
                topico_id=aula.get("topico_id"),
            ))

        for slug, lista in candidatas.items():
            lista.sort(key=lambda a: (a.ordem_topico, a.ordem_aula))
            aulas_por_materia[slug] = lista

        return aulas_por_materia

    def criar_plano(self, usuario_id: str, dados) -> dict:
        self._validar_slugs(dados.provas, dados.materias)

        # Só pode existir um plano ativo por vez — sem isso, cada plano
        # novo se soma aos anteriores em vez de substituí-los, e a mesma
        # aula acaba aparecendo duplicada no mesmo dia na tela do aluno.
        supabase_admin.table("planos_estudo").update({
            "status": "arquivado",
            "atualizado_em": datetime.now(timezone.utc).isoformat(),
        }).eq("usuario_id", usuario_id).eq("status", "ativo").execute()

        novo_plano = (
            supabase_admin
            .table("planos_estudo")
            .insert({
                "usuario_id": usuario_id,
                "titulo": "Plano de estudos",
                "status": "ativo",
                "criado_por": "ia" if dados.usar_ia else "sistema",
                "provas_selecionadas": dados.provas,
                "materias_selecionadas": dados.materias,
                "tempo_por_dia_minutos": dados.tempo_por_dia_minutos,
                "dias_estudo": dados.dias_estudo,
                "status_geracao": "gerando",
            })
            .execute()
        )

        if not novo_plano.data:
            raise HTTPException(status_code=500, detail="Não foi possível criar o plano de estudos")

        plano = novo_plano.data[0]

        try:
            self._gerar_e_persistir(plano["id"], usuario_id, dados)
        except Exception:
            logger.exception("Erro ao gerar plano de estudos plano_id=%s", plano["id"])
            supabase_admin.table("planos_estudo").update({
                "status_geracao": "erro",
                "mensagem_erro": "Não foi possível gerar o plano. Tente novamente.",
                "atualizado_em": datetime.now(timezone.utc).isoformat(),
            }).eq("id", plano["id"]).execute()
            plano["status_geracao"] = "erro"
            return plano

        plano["status_geracao"] = "concluido"
        return plano

    def _gerar_e_persistir(self, plano_id: str, usuario_id: str, dados) -> None:
        contexto = self._montar_contexto(usuario_id, dados)
        plano_gerado = self._escolher_generator(dados).gerar(contexto)

        if plano_gerado.avisos:
            logger.info(
                "plano_estudos_avisos plano_id=%s avisos=%s", plano_id, plano_gerado.avisos
            )

        materia_id_por_slug = self._materia_id_por_slug(dados.materias)
        self._persistir_sessoes_e_tarefas(plano_id, usuario_id, materia_id_por_slug, plano_gerado.dias)

        supabase_admin.table("planos_estudo").update({
            "status_geracao": "concluido",
            "data_inicio": plano_gerado.periodo_inicio.isoformat(),
            "data_fim": plano_gerado.periodo_fim.isoformat(),
            "atualizado_em": datetime.now(timezone.utc).isoformat(),
        }).eq("id", plano_id).execute()

    def _materia_id_por_slug(self, slugs: list[str]) -> dict[str, str]:
        materias_rows = (
            supabase_admin
            .table("materias")
            .select("id, slug")
            .in_("slug", slugs)
            .execute()
            .data or []
        )
        return {m["slug"]: m["id"] for m in materias_rows}

    def _persistir_sessoes_e_tarefas(
        self,
        plano_id: str,
        usuario_id: str,
        materia_id_por_slug: dict[str, str],
        dias: list[DiaGerado],
    ) -> None:
        sessoes_para_inserir = []
        tarefas_para_inserir = []
        for dia in dias:
            for indice, sessao in enumerate(dia.sessoes):
                sessoes_para_inserir.append({
                    "plano_estudo_id": plano_id,
                    "materia_slug": sessao.materia,
                    "data_agendada": dia.data.isoformat(),
                    "duracao_minutos": sessao.duracao_minutos,
                    "tipo": sessao.tipo,
                    "ordem": indice,
                    "aula_id": sessao.aula_id,
                    "titulo": sessao.titulo,
                    "lista_questoes_id": sessao.lista_questoes_id,
                })

                materia_id = materia_id_por_slug.get(sessao.materia)
                if materia_id is None:
                    continue

                tarefas_para_inserir.append(self._montar_tarefa(
                    plano_id=plano_id,
                    usuario_id=usuario_id,
                    materia_id=materia_id,
                    aula_id=sessao.aula_id,
                    lista_questoes_id=sessao.lista_questoes_id,
                    titulo=sessao.titulo,
                    tipo=sessao.tipo,
                    data_agendada=dia.data.isoformat(),
                    duracao_minutos=sessao.duracao_minutos,
                    ordem=indice,
                ))

        if sessoes_para_inserir:
            supabase_admin.table("planos_estudo_sessoes").insert(sessoes_para_inserir).execute()

        if tarefas_para_inserir:
            supabase_admin.table("tarefas_estudo").insert(tarefas_para_inserir).execute()

    _TIPO_SESSAO_PARA_TIPO_TAREFA = {
        "teoria": "aula",
        "revisao": "revisao",
        "questoes": "questoes",
    }

    def _montar_tarefa(
        self, plano_id: str, usuario_id: str, materia_id: str, aula_id: str | None,
        titulo: str | None, tipo: str, data_agendada: str, duracao_minutos: int, ordem: int,
        lista_questoes_id: str | None = None,
    ) -> dict:
        return {
            "plano_estudo_id": plano_id,
            "usuario_id": usuario_id,
            "materia_id": materia_id,
            "aula_id": aula_id,
            "lista_questoes_id": lista_questoes_id,
            "titulo": titulo or "Sessão de estudo",
            "tipo_tarefa": self._TIPO_SESSAO_PARA_TIPO_TAREFA.get(tipo, "revisao"),
            "data_agendada": data_agendada,
            "duracao_minutos": duracao_minutos,
            "ordem": ordem,
            "origem": "sistema",
        }

    def replanejar_apos_conclusao(self, plano_id: str, usuario_id: str) -> None:
        """Regera os dias futuros (ainda não realizados) de um plano ativo
        depois que o aluno conclui uma aula — para que o restante do
        cronograma reflita o que já foi de fato estudado, em vez de manter
        aulas já concluídas planejadas de novo ou seguir repetindo a mesma
        aula de revisão fixada no momento da criação do plano.

        Tarefas já concluídas nunca são tocadas (viram histórico/base da
        revisão). Tarefas pendentes com data no passado também não são
        tocadas — tratamento de aula perdida/esquecida é um problema
        separado, ainda não implementado.

        Sempre usa o motor determinístico, independente de como o plano
        foi originalmente criado — é o mesmo raciocínio já documentado na
        criação do plano: instantâneo e não depende de um provider de IA
        disponível no meio do fluxo de estudo do aluno.
        """
        plano_resposta = (
            supabase_admin
            .table("planos_estudo")
            .select("id, status, provas_selecionadas, materias_selecionadas, tempo_por_dia_minutos, dias_estudo")
            .eq("id", plano_id)
            .eq("usuario_id", usuario_id)
            .eq("status", "ativo")
            .limit(1)
            .execute()
        )

        if not plano_resposta.data:
            return

        plano = plano_resposta.data[0]
        if not plano["dias_estudo"] or not plano["materias_selecionadas"] or not plano["provas_selecionadas"]:
            return

        dados = PostCriarPlanoEstudosParams(
            provas=plano["provas_selecionadas"],
            materias=plano["materias_selecionadas"],
            tempo_por_dia_minutos=plano["tempo_por_dia_minutos"],
            dias_estudo=plano["dias_estudo"],
            usar_ia=False,
        )

        contexto = self._montar_contexto(usuario_id, dados)
        aulas_por_id: dict[str, AulaContexto] = {
            aula.id: aula
            for aulas in contexto.aulas_por_materia.values()
            for aula in aulas
        }
        materia_id_por_slug = self._materia_id_por_slug(dados.materias)
        materia_slug_por_id = {v: k for k, v in materia_id_por_slug.items()}

        hoje = hoje_brasil()

        tarefas = (
            supabase_admin
            .table("tarefas_estudo")
            .select("id, materia_id, aula_id, status, data_agendada, concluido_em")
            .eq("plano_estudo_id", plano_id)
            .execute()
            .data or []
        )

        concluidas = sorted(
            (t for t in tarefas if t["status"] == "concluida" and t.get("aula_id")),
            key=lambda t: t.get("concluido_em") or "",
        )

        historico_inicial: dict[str, list[AulaContexto]] = {}
        aulas_ja_usadas: set[str] = set()
        for tarefa in concluidas:
            aula = aulas_por_id.get(tarefa["aula_id"])
            materia_slug = materia_slug_por_id.get(tarefa["materia_id"])
            if not aula or not materia_slug:
                continue
            historico_inicial.setdefault(materia_slug, []).append(aula)
            aulas_ja_usadas.add(aula.id)

        # Remove só as tarefas/sessões futuras ainda pendentes — passado e
        # concluídas ficam intactos.
        supabase_admin.table("tarefas_estudo") \
            .delete() \
            .eq("plano_estudo_id", plano_id) \
            .eq("status", "pendente") \
            .gte("data_agendada", hoje.isoformat()) \
            .execute()

        supabase_admin.table("planos_estudo_sessoes") \
            .delete() \
            .eq("plano_estudo_id", plano_id) \
            .gte("data_agendada", hoje.isoformat()) \
            .execute()

        plano_gerado = DeterministicPlanGenerator().gerar(
            contexto,
            historico_inicial=historico_inicial,
            aulas_ja_usadas=aulas_ja_usadas,
            data_inicio_override=hoje,
        )

        if plano_gerado.avisos:
            logger.info(
                "plano_estudos_replanejamento_avisos plano_id=%s avisos=%s", plano_id, plano_gerado.avisos
            )

        self._persistir_sessoes_e_tarefas(plano_id, usuario_id, materia_id_por_slug, plano_gerado.dias)

        supabase_admin.table("planos_estudo").update({
            "atualizado_em": datetime.now(timezone.utc).isoformat(),
        }).eq("id", plano_id).execute()

    def sincronizar_tarefas(self, plano_id: str, usuario_id: str) -> int:
        """Recria as tarefas_estudo (usadas pela tela do dia) a partir das
        sessões já salvas em planos_estudo_sessoes. Necessário para planos
        gerados antes de o service passar a criar as tarefas junto — e
        seguro de rodar de novo, pois não duplica se já existirem tarefas
        para o plano.
        """
        plano = (
            supabase_admin
            .table("planos_estudo")
            .select("id, usuario_id, status_geracao")
            .eq("id", plano_id)
            .eq("usuario_id", usuario_id)
            .limit(1)
            .execute()
        )

        if not plano.data:
            raise HTTPException(status_code=404, detail="Plano não encontrado")

        if plano.data[0]["status_geracao"] != "concluido":
            raise HTTPException(status_code=409, detail="Plano ainda não foi concluído")

        tarefas_existentes = (
            supabase_admin
            .table("tarefas_estudo")
            .select("id")
            .eq("plano_estudo_id", plano_id)
            .limit(1)
            .execute()
        )

        if tarefas_existentes.data:
            raise HTTPException(status_code=409, detail="Este plano já possui tarefas sincronizadas")

        sessoes = (
            supabase_admin
            .table("planos_estudo_sessoes")
            .select("materia_slug, data_agendada, duracao_minutos, tipo, ordem, aula_id, titulo, lista_questoes_id")
            .eq("plano_estudo_id", plano_id)
            .order("data_agendada")
            .order("ordem")
            .execute()
            .data or []
        )

        if not sessoes:
            return 0

        slugs = list({s["materia_slug"] for s in sessoes})
        materias_rows = (
            supabase_admin
            .table("materias")
            .select("id, slug")
            .in_("slug", slugs)
            .execute()
            .data or []
        )
        materia_id_por_slug = {m["slug"]: m["id"] for m in materias_rows}

        tarefas_para_inserir = []
        for sessao in sessoes:
            materia_id = materia_id_por_slug.get(sessao["materia_slug"])
            if materia_id is None:
                continue

            tarefas_para_inserir.append(self._montar_tarefa(
                plano_id=plano_id,
                usuario_id=usuario_id,
                materia_id=materia_id,
                aula_id=sessao.get("aula_id"),
                lista_questoes_id=sessao.get("lista_questoes_id"),
                titulo=sessao.get("titulo"),
                tipo=sessao["tipo"],
                data_agendada=sessao["data_agendada"],
                duracao_minutos=sessao["duracao_minutos"],
                ordem=sessao["ordem"],
            ))

        if tarefas_para_inserir:
            supabase_admin.table("tarefas_estudo").insert(tarefas_para_inserir).execute()

        return len(tarefas_para_inserir)

    def obter_plano(self, plano_id: str, usuario_id: str) -> dict | None:
        resposta = (
            supabase_admin
            .table("planos_estudo")
            .select("id, usuario_id, status_geracao, mensagem_erro, data_inicio, data_fim")
            .eq("id", plano_id)
            .eq("usuario_id", usuario_id)
            .limit(1)
            .execute()
        )

        if not resposta.data:
            return None

        plano = resposta.data[0]

        if plano["status_geracao"] != "concluido":
            return plano

        sessoes = (
            supabase_admin
            .table("planos_estudo_sessoes")
            .select("materia_slug, data_agendada, duracao_minutos, tipo, ordem, aula_id, titulo, lista_questoes_id")
            .eq("plano_estudo_id", plano_id)
            .order("data_agendada")
            .order("ordem")
            .execute()
            .data or []
        )

        plano["sessoes"] = sessoes
        return plano

    def montar_resposta_gerado(self, plano: dict) -> dict:
        if plano["status_geracao"] == "gerando":
            return {"id": plano["id"], "status": "gerando"}

        if plano["status_geracao"] == "erro":
            return {
                "id": plano["id"],
                "status": "erro",
                "mensagem": plano.get("mensagem_erro") or "Não foi possível gerar o plano. Tente novamente.",
            }

        dias_por_data: dict[str, list] = {}
        for sessao in plano.get("sessoes", []):
            dias_por_data.setdefault(sessao["data_agendada"], []).append(sessao)

        data_inicio = date.fromisoformat(plano["data_inicio"]) if plano["data_inicio"] else hoje_brasil()

        semanas_por_numero: dict[int, dict] = {}
        for data_iso in sorted(dias_por_data.keys()):
            data_dia = date.fromisoformat(data_iso)
            numero_semana = ((data_dia - data_inicio).days // 7) + 1

            semana = semanas_por_numero.setdefault(numero_semana, {"numero": numero_semana, "dias": []})
            semana["dias"].append({
                "dia": data_dia.strftime("%A").lower(),
                "data": data_iso,
                "sessoes": [
                    {
                        "materia": s["materia_slug"],
                        "aula_id": s.get("aula_id"),
                        "titulo": s.get("titulo"),
                        "duracao_minutos": s["duracao_minutos"],
                        "tipo": s["tipo"],
                    }
                    for s in dias_por_data[data_iso]
                ],
            })

        return {
            "id": plano["id"],
            "status": "concluido",
            "plano": {
                "periodo": {
                    "inicio": plano["data_inicio"],
                    "fim": plano["data_fim"],
                },
                "semanas": [semanas_por_numero[n] for n in sorted(semanas_por_numero.keys())],
            },
        }
