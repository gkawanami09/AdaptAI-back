from fastapi import APIRouter, HTTPException, Depends, Query
from database import supabase_admin
from typing import Literal
from uuid import UUID
from utils.autenticacao import pegar_usuario_atual
from utils.textos import gerar_slug
from schemas.banco_questoes_schema import (
    BancoQuestoesFiltrosResponse,
    BancoQuestoesListasResponse,
    BancoQuestoesQuestoesRespondidasResponse,
    GerarListaIAResponse,
    RefazerListaResponse,
    RevisaoExecucaoResponse,
)
from services.ai.factory import get_ai_provider
from services.ai.base import AIIndisponivelError, AIRespostaInvalidaError

QUANTIDADE_QUESTOES_LISTA_IA = 10

router = APIRouter(
    prefix='/aluno/banco-questoes',
    tags=['Aluno - Banco de Questões']
)

DIFICULDADE_LABEL = {
    "facil": "Fácil",
    "medio": "Médio",
    "dificil": "Difícil",
}

DIFICULDADE_COR = {
    "facil": "teal",
    "medio": "blue",
    "dificil": "red",
}

ICONE_COR_PADRAO = "purple"
PROGRESSO_COR_PADRAO = "purple"


@router.get('/filtros', response_model=BancoQuestoesFiltrosResponse)
def obter_filtros(usuario_atual=Depends(pegar_usuario_atual)):
    try:
        vestibulares = (
            supabase_admin.table("tipos_prova")
            .select("slug, nome")
            .eq("ativo", True)
            .order("nome")
            .execute()
            .data or []
        )

        materias = (
            supabase_admin.table("materias")
            .select("slug, nome")
            .eq("ativo", True)
            .order("nome")
            .execute()
            .data or []
        )

        assuntos = (
            supabase_admin.table("topicos")
            .select("slug, nome")
            .eq("ativo", True)
            .order("nome")
            .execute()
            .data or []
        )

        return {
            "vestibulares": [
                {"value": v["slug"], "label": v["nome"]} for v in vestibulares
            ],
            "dificuldades": [
                {"value": valor, "label": label} for valor, label in DIFICULDADE_LABEL.items()
            ],
            "materias": [
                {"value": m["slug"], "label": m["nome"]} for m in materias
            ],
            "assuntos": [
                {"value": a["slug"], "label": a["nome"]} for a in assuntos
            ],
        }

    except Exception as erro:
        print(f"Erro ao obter filtros do banco de questões: {erro}")

        raise HTTPException(
            status_code=500,
            detail="Erro ao obter filtros do banco de questões"
        )


def _execucoes_atuais(usuario_id: str, ids_listas: list[str]) -> dict[str, dict]:
    """Última execução (linha de `progresso_lista_questoes_aluno`) de cada
    lista pro aluno — não tem constraint de unicidade em
    (usuario_id, lista_questoes_id) de propósito, pra "refazer" poder
    inserir uma execução nova sem apagar as anteriores (ver
    routers/visualizacao_questoes.py:obter_progresso).
    """
    if not ids_listas:
        return {}

    linhas = (
        supabase_admin.table("progresso_lista_questoes_aluno")
        .select("id, lista_questoes_id, status, iniciado_em")
        .eq("usuario_id", usuario_id)
        .in_("lista_questoes_id", ids_listas)
        .order("iniciado_em")
        .execute()
        .data or []
    )

    execucao_por_lista: dict[str, dict] = {}
    for linha in linhas:
        # Ordenado ascendente — a última sobrescrita no dict é sempre a
        # execução mais recente.
        execucao_por_lista[linha["lista_questoes_id"]] = linha
    return execucao_por_lista


def _respostas_por_lista(usuario_id: str, ids_listas: list[str]) -> dict[str, list[dict]]:
    if not ids_listas:
        return {}

    respostas = (
        supabase_admin.table("respostas_lista_questoes_aluno")
        .select("lista_questoes_id, questao_id, correta, respondido_em")
        .eq("usuario_id", usuario_id)
        .in_("lista_questoes_id", ids_listas)
        .execute()
        .data or []
    )

    agrupadas: dict[str, list[dict]] = {}
    for resposta in respostas:
        agrupadas.setdefault(resposta["lista_questoes_id"], []).append(resposta)
    return agrupadas


def montar_listas(
    usuario_id: str,
    vestibulares: list[str] | None,
    dificuldades: list[str] | None,
    materias: list[str] | None,
    apenas_erradas: bool,
    apenas_favoritas: bool,
):
    tipos_prova = (
        supabase_admin.table("tipos_prova")
        .select("id, slug, nome")
        .execute()
        .data or []
    )
    materias_banco = (
        supabase_admin.table("materias")
        .select("id, slug, nome, cor, icone")
        .execute()
        .data or []
    )

    tipos_prova_por_id = {t["id"]: t for t in tipos_prova}
    materias_por_id = {m["id"]: m for m in materias_banco}

    ids_tipo_prova = None
    if vestibulares:
        ids_tipo_prova = [t["id"] for t in tipos_prova if t["slug"] in vestibulares]
        if not ids_tipo_prova:
            return []

    ids_materia = None
    if materias:
        ids_materia = [m["id"] for m in materias_banco if m["slug"] in materias]
        if not ids_materia:
            return []

    consulta = supabase_admin.table("listas_questoes").select("*")

    if ids_tipo_prova is not None:
        consulta = consulta.in_("tipo_prova_id", ids_tipo_prova)
    if ids_materia is not None:
        consulta = consulta.in_("materia_id", ids_materia)
    if dificuldades:
        consulta = consulta.in_("dificuldade", dificuldades)

    listas_banco = consulta.execute().data or []

    if apenas_erradas:
        ids_questoes_erradas = {
            t["questao_id"]
            for t in (
                supabase_admin.table("tentativas_questoes")
                .select("questao_id, acertou")
                .eq("usuario_id", usuario_id)
                .eq("acertou", False)
                .execute()
                .data or []
            )
        }
        if not ids_questoes_erradas:
            return []

        ids_listas_com_erradas = {
            item["lista_questoes_id"]
            for item in (
                supabase_admin.table("itens_lista_questoes")
                .select("lista_questoes_id, questao_id")
                .in_("questao_id", list(ids_questoes_erradas))
                .execute()
                .data or []
            )
        }
        listas_banco = [lista for lista in listas_banco if lista["id"] in ids_listas_com_erradas]

    if apenas_favoritas:
        ids_questoes_favoritas = {
            f["questao_id"]
            for f in (
                supabase_admin.table("questoes_favoritas")
                .select("questao_id")
                .eq("usuario_id", usuario_id)
                .execute()
                .data or []
            )
        }
        if not ids_questoes_favoritas:
            return []

        ids_listas_com_favoritas = {
            item["lista_questoes_id"]
            for item in (
                supabase_admin.table("itens_lista_questoes")
                .select("lista_questoes_id, questao_id")
                .in_("questao_id", list(ids_questoes_favoritas))
                .execute()
                .data or []
            )
        }
        listas_banco = [lista for lista in listas_banco if lista["id"] in ids_listas_com_favoritas]

    ids_listas = [lista["id"] for lista in listas_banco]

    itens = (
        supabase_admin.table("itens_lista_questoes")
        .select("lista_questoes_id, questao_id")
        .in_("lista_questoes_id", ids_listas)
        .execute()
        .data or []
    ) if ids_listas else []

    questoes_por_lista: dict[str, list[str]] = {}
    for item in itens:
        questoes_por_lista.setdefault(item["lista_questoes_id"], []).append(item["questao_id"])

    execucao_por_lista = _execucoes_atuais(usuario_id, ids_listas)
    respostas_por_lista_todas = _respostas_por_lista(usuario_id, ids_listas)

    listas = []
    for lista in listas_banco:
        materia = materias_por_id.get(lista["materia_id"])
        tipo_prova = tipos_prova_por_id.get(lista["tipo_prova_id"])
        questoes_da_lista = questoes_por_lista.get(lista["id"], [])
        dificuldade = lista.get("dificuldade") or "medio"

        # Escopado à execução atual — sem isso, um "refazer" não zeraria
        # o progresso mostrado no card (ver routers/visualizacao_questoes.py:
        # calcular_progresso, mesma lógica espelhada aqui).
        execucao = execucao_por_lista.get(lista["id"])
        desde = execucao["iniciado_em"] if execucao else None
        respostas_lista = respostas_por_lista_todas.get(lista["id"], [])
        if desde:
            respostas_lista = [r for r in respostas_lista if r["respondido_em"] >= desde]

        resultado_por_questao: dict[str, bool] = {}
        for resposta in respostas_lista:
            resultado_por_questao[resposta["questao_id"]] = resposta["correta"]

        total = len(questoes_da_lista)
        concluidas = sum(1 for q in questoes_da_lista if q in resultado_por_questao)
        corretas = sum(1 for q in questoes_da_lista if resultado_por_questao.get(q) is True)

        if execucao is None or concluidas == 0:
            status_lista = "nao_iniciado"
        elif execucao["status"] == "finalizada" or (total > 0 and concluidas >= total):
            status_lista = "concluido"
        else:
            status_lista = "em_andamento"

        listas.append({
            "id": lista["id"],
            "slug": lista.get("slug"),
            "icone": materia["icone"] if materia else "📚",
            "icone_cor": materia["cor"] if materia else ICONE_COR_PADRAO,
            "titulo": lista["titulo"],
            "descricao": lista.get("descricao"),
            "dificuldade": DIFICULDADE_LABEL.get(dificuldade, dificuldade),
            "dificuldade_cor": DIFICULDADE_COR.get(dificuldade, "gray"),
            "vestibular": tipo_prova["nome"] if tipo_prova else "Geral",
            "status": status_lista,
            "questoes_concluidas": concluidas,
            "questoes_totais": total,
            "questoes_corretas": corretas,
            "progresso_cor": materia["cor"] if materia else PROGRESSO_COR_PADRAO,
            "ultima_execucao_id": execucao["id"] if execucao else None,
        })

    return listas


@router.get('/listas', response_model=BancoQuestoesListasResponse)
def listar_listas(
    vestibulares: list[str] | None = Query(default=None),
    dificuldades: list[str] | None = Query(default=None),
    materias: list[str] | None = Query(default=None),
    apenas_erradas: bool = Query(default=False),
    apenas_favoritas: bool = Query(default=False),
    usuario_atual=Depends(pegar_usuario_atual)
):
    try:
        listas = montar_listas(
            str(usuario_atual.id),
            vestibulares,
            dificuldades,
            materias,
            apenas_erradas,
            apenas_favoritas,
        )

        return {
            "total": len(listas),
            "listas": listas,
        }

    except HTTPException:
        raise

    except Exception as erro:
        print(f"Erro ao listar listas do banco de questões: {erro}")

        raise HTTPException(
            status_code=500,
            detail="Erro ao listar listas do banco de questões"
        )


@router.post('/listas/{lista_id}/refazer', response_model=RefazerListaResponse)
def refazer_lista(lista_id: UUID, usuario_atual=Depends(pegar_usuario_atual)):
    try:
        id_usuario = str(usuario_atual.id)

        lista = (
            supabase_admin.table("listas_questoes")
            .select("id, slug, usuario_id")
            .eq("id", str(lista_id))
            .limit(1)
            .execute()
        )
        if not lista.data:
            raise HTTPException(status_code=404, detail="Lista de questões não encontrada")

        lista = lista.data[0]
        if lista["usuario_id"] and lista["usuario_id"] != id_usuario:
            raise HTTPException(status_code=403, detail="Lista não pertence ao aluno autenticado")

        # Insere uma execução nova em vez de reaproveitar/atualizar a
        # existente — `progresso_lista_questoes_aluno` não tem constraint
        # de unicidade em (usuario_id, lista_questoes_id) de propósito,
        # justamente pra permitir isso sem apagar o histórico de execuções
        # e respostas anteriores (ver routers/visualizacao_questoes.py).
        nova_execucao = (
            supabase_admin.table("progresso_lista_questoes_aluno")
            .insert({
                "usuario_id": id_usuario,
                "lista_questoes_id": str(lista_id),
                "status": "em_andamento",
            })
            .execute()
        )
        if not nova_execucao.data:
            raise HTTPException(status_code=500, detail="Não foi possível reiniciar a lista")

        return {
            "execucao_id": nova_execucao.data[0]["id"],
            "lista_id": lista["id"],
            "slug": lista.get("slug"),
            "status": "em_andamento",
        }

    except HTTPException:
        raise

    except Exception as erro:
        print(f"Erro ao refazer lista de questões: {erro}")

        raise HTTPException(
            status_code=500,
            detail="Erro ao refazer lista de questões"
        )


def _janela_da_execucao(usuario_id: str, lista_id: str, execucao_id: str, iniciado_em: str) -> str | None:
    """Fim (exclusivo) da janela de tempo dessa execução — o início da
    execução seguinte na mesma lista, se houver. Sem isso, revisar uma
    execução antiga misturaria respostas de execuções feitas depois dela
    (ver mesmo raciocínio em calcular_progresso, routers/visualizacao_questoes.py).
    """
    linhas = (
        supabase_admin.table("progresso_lista_questoes_aluno")
        .select("id, iniciado_em")
        .eq("usuario_id", usuario_id)
        .eq("lista_questoes_id", lista_id)
        .order("iniciado_em")
        .execute()
        .data or []
    )

    achou_atual = False
    for linha in linhas:
        if achou_atual:
            return linha["iniciado_em"]
        if linha["id"] == execucao_id:
            achou_atual = True
    return None


@router.get('/execucoes/{execucao_id}/revisao', response_model=RevisaoExecucaoResponse)
def revisar_execucao(
    execucao_id: UUID,
    status: Literal["acertada", "errada"] | None = Query(default=None),
    materia: str | None = Query(default=None),
    assunto: str | None = Query(default=None),
    dificuldade: str | None = Query(default=None),
    pagina: int = Query(default=1, ge=1),
    limite: int = Query(default=20, ge=1, le=100),
    usuario_atual=Depends(pegar_usuario_atual)
):
    try:
        id_usuario = str(usuario_atual.id)

        execucao = (
            supabase_admin.table("progresso_lista_questoes_aluno")
            .select("id, usuario_id, lista_questoes_id, status, iniciado_em")
            .eq("id", str(execucao_id))
            .limit(1)
            .execute()
        )
        # Nunca revela se a execução existe pra outro aluno — 404 pros
        # dois casos (não existe / não pertence ao usuário autenticado).
        if not execucao.data or execucao.data[0]["usuario_id"] != id_usuario:
            raise HTTPException(status_code=404, detail="Execução não encontrada")

        execucao = execucao.data[0]
        lista_id = execucao["lista_questoes_id"]

        lista = (
            supabase_admin.table("listas_questoes")
            .select("id, titulo")
            .eq("id", lista_id)
            .limit(1)
            .execute()
            .data
        )
        lista_titulo = lista[0]["titulo"] if lista else "Lista de questões"

        itens = (
            supabase_admin.table("itens_lista_questoes")
            .select("questao_id")
            .eq("lista_questoes_id", lista_id)
            .execute()
            .data or []
        )
        questoes_totais_lista = len(itens)

        fim_janela = _janela_da_execucao(id_usuario, lista_id, execucao["id"], execucao["iniciado_em"])

        consulta_respostas = (
            supabase_admin.table("respostas_lista_questoes_aluno")
            .select("questao_id, alternativa_selecionada_id, correta, respondido_em")
            .eq("usuario_id", id_usuario)
            .eq("lista_questoes_id", lista_id)
            .gte("respondido_em", execucao["iniciado_em"])
        )
        if fim_janela:
            consulta_respostas = consulta_respostas.lt("respondido_em", fim_janela)
        respostas = consulta_respostas.execute().data or []

        respondidas_total = len(respostas)
        acertadas_total = sum(1 for r in respostas if r["correta"])
        percentual_acerto = (
            round((acertadas_total / respondidas_total) * 100) if respondidas_total > 0 else None
        )

        materias_banco = supabase_admin.table("materias").select("id, slug, nome, cor").execute().data or []
        topicos_banco = supabase_admin.table("topicos").select("topico_id, slug, nome").execute().data or []
        materia_por_slug = {m["slug"]: m for m in materias_banco}
        topico_por_slug = {t["slug"]: t for t in topicos_banco}

        id_materia_filtro = materia_por_slug.get(materia)["id"] if materia and materia in materia_por_slug else None
        if materia and id_materia_filtro is None:
            return _revisao_vazia(execucao, lista_id, lista_titulo, questoes_totais_lista, respondidas_total, acertadas_total, percentual_acerto, pagina, limite)

        id_topico_filtro = topico_por_slug.get(assunto)["topico_id"] if assunto and assunto in topico_por_slug else None
        if assunto and id_topico_filtro is None:
            return _revisao_vazia(execucao, lista_id, lista_titulo, questoes_totais_lista, respondidas_total, acertadas_total, percentual_acerto, pagina, limite)

        ids_questoes = [r["questao_id"] for r in respostas]
        consulta_questoes = supabase_admin.table("questoes").select(
            "id, materia_id, topico_id, dificuldade, enunciado, alternativa_correta"
        )
        questoes_banco = (
            consulta_questoes.in_("id", ids_questoes).execute().data or []
        ) if ids_questoes else []
        questoes_por_id = {q["id"]: q for q in questoes_banco}
        materias_por_id = {m["id"]: m for m in materias_banco}
        topicos_por_id = {t["topico_id"]: t for t in topicos_banco}

        alvo_correta = {"acertada": True, "errada": False}.get(status)

        respostas_filtradas = []
        for resposta in respostas:
            questao = questoes_por_id.get(resposta["questao_id"])
            if not questao:
                continue
            if alvo_correta is not None and resposta["correta"] is not alvo_correta:
                continue
            if id_materia_filtro is not None and questao["materia_id"] != id_materia_filtro:
                continue
            if id_topico_filtro is not None and questao["topico_id"] != id_topico_filtro:
                continue
            if dificuldade and questao.get("dificuldade") != dificuldade:
                continue
            respostas_filtradas.append(resposta)

        ids_alternativas = {r["alternativa_selecionada_id"] for r in respostas_filtradas}
        for resposta in respostas_filtradas:
            questao = questoes_por_id[resposta["questao_id"]]
            if questao.get("alternativa_correta"):
                ids_alternativas.add(questao["alternativa_correta"])

        alternativas_banco = (
            supabase_admin.table("alternativas_questao")
            .select("id, questao_id, letra, conteudo, ordem")
            .in_("questao_id", [r["questao_id"] for r in respostas_filtradas])
            .order("ordem")
            .execute()
            .data or []
        ) if respostas_filtradas else []
        alternativas_por_questao: dict[str, list[dict]] = {}
        for alt in alternativas_banco:
            alternativas_por_questao.setdefault(alt["questao_id"], []).append(alt)
        letra_por_alternativa = {a["id"]: a["letra"] for a in alternativas_banco}

        questoes_resposta = []
        for resposta in respostas_filtradas:
            questao = questoes_por_id[resposta["questao_id"]]
            materia_questao = materias_por_id.get(questao["materia_id"])
            topico_questao = topicos_por_id.get(questao["topico_id"])
            dificuldade_questao = questao.get("dificuldade")

            questoes_resposta.append({
                "id": questao["id"],
                "enunciado": questao["enunciado"],
                "materia": materia_questao["nome"] if materia_questao else "Geral",
                "materia_cor": materia_questao["cor"] if materia_questao else ICONE_COR_PADRAO,
                "assunto": topico_questao["nome"] if topico_questao else None,
                "dificuldade": DIFICULDADE_LABEL.get(dificuldade_questao, dificuldade_questao),
                "dificuldade_cor": DIFICULDADE_COR.get(dificuldade_questao, "gray") if dificuldade_questao else None,
                "alternativas": [
                    {"letra": alt["letra"], "texto": alt.get("conteudo")}
                    for alt in sorted(alternativas_por_questao.get(questao["id"], []), key=lambda a: a["ordem"])
                ],
                "resposta_aluno": letra_por_alternativa.get(resposta["alternativa_selecionada_id"]),
                "resposta_correta": letra_por_alternativa.get(questao.get("alternativa_correta")),
                "acertou": resposta["correta"],
            })

        questoes_resposta.sort(key=lambda q: q["id"])

        total = len(questoes_resposta)
        total_paginas = (total + limite - 1) // limite
        inicio = (pagina - 1) * limite
        pagina_questoes = questoes_resposta[inicio:inicio + limite]

        return {
            "execucao": {
                "id": execucao["id"],
                "lista_id": lista_id,
                "lista_titulo": lista_titulo,
                "status": "concluido" if execucao["status"] == "finalizada" else "em_andamento",
                "questoes_totais": questoes_totais_lista,
                "respondidas": respondidas_total,
                "acertadas": acertadas_total,
                "percentual_acerto": percentual_acerto,
            },
            "questoes": pagina_questoes,
            "paginacao": {
                "pagina": pagina,
                "limite": limite,
                "total": total,
                "total_paginas": total_paginas,
            },
        }

    except HTTPException:
        raise

    except Exception as erro:
        print(f"Erro ao revisar execução: {erro}")

        raise HTTPException(
            status_code=500,
            detail="Erro ao revisar execução"
        )


def _revisao_vazia(execucao, lista_id, lista_titulo, questoes_totais_lista, respondidas_total, acertadas_total, percentual_acerto, pagina, limite):
    return {
        "execucao": {
            "id": execucao["id"],
            "lista_id": lista_id,
            "lista_titulo": lista_titulo,
            "status": "concluido" if execucao["status"] == "finalizada" else "em_andamento",
            "questoes_totais": questoes_totais_lista,
            "respondidas": respondidas_total,
            "acertadas": acertadas_total,
            "percentual_acerto": percentual_acerto,
        },
        "questoes": [],
        "paginacao": {"pagina": pagina, "limite": limite, "total": 0, "total_paginas": 0},
    }


@router.get('/questoes-respondidas', response_model=BancoQuestoesQuestoesRespondidasResponse)
def listar_questoes_respondidas(
    status: Literal["corretas", "erradas"] = Query(...),
    vestibulares: list[str] | None = Query(default=None),
    dificuldades: list[str] | None = Query(default=None),
    materias: list[str] | None = Query(default=None),
    assuntos: list[str] | None = Query(default=None),
    apenas_favoritas: bool = Query(default=False),
    pagina: int = Query(default=1, ge=1),
    limite: int = Query(default=20, ge=1, le=100),
    usuario_atual=Depends(pegar_usuario_atual)
):
    try:
        id_usuario = str(usuario_atual.id)

        def vazio():
            return {
                "questoes": [],
                "paginacao": {"pagina": pagina, "limite": limite, "total": 0, "total_paginas": 0},
            }

        tipos_prova = (
            supabase_admin.table("tipos_prova").select("id, slug, nome").execute().data or []
        )
        materias_banco = (
            supabase_admin.table("materias").select("id, slug, nome, cor").execute().data or []
        )
        topicos_banco = (
            supabase_admin.table("topicos").select("topico_id, slug, nome").execute().data or []
        )
        tipos_prova_por_id = {t["id"]: t for t in tipos_prova}
        materias_por_id = {m["id"]: m for m in materias_banco}
        topicos_por_id = {t["topico_id"]: t for t in topicos_banco}

        ids_tipo_prova = None
        if vestibulares:
            ids_tipo_prova = [t["id"] for t in tipos_prova if t["slug"] in vestibulares]
            if not ids_tipo_prova:
                return vazio()

        ids_materia = None
        if materias:
            ids_materia = [m["id"] for m in materias_banco if m["slug"] in materias]
            if not ids_materia:
                return vazio()

        ids_topico = None
        if assuntos:
            ids_topico = [t["topico_id"] for t in topicos_banco if t["slug"] in assuntos]
            if not ids_topico:
                return vazio()

        consulta = supabase_admin.table("questoes").select(
            "id, materia_id, tipo_prova_id, topico_id, dificuldade, enunciado, alternativa_correta"
        )
        if ids_tipo_prova is not None:
            consulta = consulta.in_("tipo_prova_id", ids_tipo_prova)
        if ids_materia is not None:
            consulta = consulta.in_("materia_id", ids_materia)
        if ids_topico is not None:
            consulta = consulta.in_("topico_id", ids_topico)
        if dificuldades:
            consulta = consulta.in_("dificuldade", dificuldades)

        questoes_banco = consulta.execute().data or []
        if not questoes_banco:
            return vazio()

        if apenas_favoritas:
            ids_favoritas = {
                f["questao_id"]
                for f in (
                    supabase_admin.table("questoes_favoritas")
                    .select("questao_id")
                    .eq("usuario_id", id_usuario)
                    .execute()
                    .data or []
                )
            }
            questoes_banco = [q for q in questoes_banco if q["id"] in ids_favoritas]
            if not questoes_banco:
                return vazio()

        questoes_por_id = {q["id"]: q for q in questoes_banco}

        # Respostas de verdade ficam em respostas_lista_questoes_aluno (é
        # o que routers/visualizacao_questoes.py grava ao responder uma
        # questão dentro de uma lista) — tentativas_questoes é só do fluxo
        # de simulado, não cobre questões respondidas por lista.
        respostas = (
            supabase_admin.table("respostas_lista_questoes_aluno")
            .select("lista_questoes_id, questao_id, alternativa_selecionada_id, correta, respondido_em")
            .eq("usuario_id", id_usuario)
            .in_("questao_id", list(questoes_por_id.keys()))
            .order("respondido_em")
            .execute()
            .data or []
        )

        # Resposta mais recente por questão — se a mesma questão foi
        # respondida em mais de uma lista/execução, prevalece a última.
        resposta_mais_recente_por_questao: dict[str, dict] = {}
        for resposta in respostas:
            resposta_mais_recente_por_questao[resposta["questao_id"]] = resposta

        alvo = status == "corretas"
        respostas_alvo = {
            questao_id: resposta
            for questao_id, resposta in resposta_mais_recente_por_questao.items()
            if resposta["correta"] is alvo
        }
        if not respostas_alvo:
            return vazio()

        ids_listas = list({r["lista_questoes_id"] for r in respostas_alvo.values()})
        listas_banco = (
            supabase_admin.table("listas_questoes")
            .select("id, slug, titulo")
            .in_("id", ids_listas)
            .execute()
            .data or []
        ) if ids_listas else []
        listas_por_id = {l["id"]: l for l in listas_banco}

        ids_alternativas = {r["alternativa_selecionada_id"] for r in respostas_alvo.values()}
        for questao_id in respostas_alvo:
            id_correta = questoes_por_id[questao_id].get("alternativa_correta")
            if id_correta:
                ids_alternativas.add(id_correta)

        alternativas_banco = (
            supabase_admin.table("alternativas_questao")
            .select("id, letra")
            .in_("id", list(ids_alternativas))
            .execute()
            .data or []
        ) if ids_alternativas else []
        letra_por_alternativa = {a["id"]: a["letra"] for a in alternativas_banco}

        questoes_resposta = []
        for questao_id, resposta in respostas_alvo.items():
            questao = questoes_por_id[questao_id]
            materia = materias_por_id.get(questao["materia_id"])
            tipo_prova = tipos_prova_por_id.get(questao["tipo_prova_id"])
            topico = topicos_por_id.get(questao["topico_id"])
            lista = listas_por_id.get(resposta["lista_questoes_id"])
            dificuldade = questao.get("dificuldade") or "medio"

            questoes_resposta.append({
                "id": questao["id"],
                "lista_id": lista["id"] if lista else None,
                "lista_slug": lista.get("slug") if lista else None,
                "lista_titulo": lista.get("titulo") if lista else None,
                "subject": materia["nome"] if materia else "Geral",
                "subjectColor": materia["cor"] if materia else ICONE_COR_PADRAO,
                "assunto": topico["nome"] if topico else None,
                "question": questao["enunciado"],
                "vestibular": tipo_prova["nome"] if tipo_prova else "Geral",
                "dificuldade": DIFICULDADE_LABEL.get(dificuldade, dificuldade),
                "dificuldade_cor": DIFICULDADE_COR.get(dificuldade, "gray"),
                "correta": alvo,
                "resposta_aluno": letra_por_alternativa.get(resposta["alternativa_selecionada_id"]),
                "resposta_correta": letra_por_alternativa.get(questao.get("alternativa_correta")),
                "respondida_em": resposta["respondido_em"],
            })

        questoes_resposta.sort(key=lambda q: q["respondida_em"] or "", reverse=True)

        total = len(questoes_resposta)
        total_paginas = (total + limite - 1) // limite
        inicio = (pagina - 1) * limite
        pagina_questoes = questoes_resposta[inicio:inicio + limite]

        return {
            "questoes": pagina_questoes,
            "paginacao": {
                "pagina": pagina,
                "limite": limite,
                "total": total,
                "total_paginas": total_paginas,
            },
        }

    except HTTPException:
        raise

    except Exception as erro:
        print(f"Erro ao listar questões respondidas: {erro}")

        raise HTTPException(
            status_code=500,
            detail="Erro ao listar questões respondidas"
        )


# Matéria com a maior taxa de erro do usuário, a partir de tentativas_questoes
# join questoes.materia_id. Retorna None se não houver erros o suficiente.
def materia_com_mais_erros(id_usuario: str) -> dict | None:
    tentativas_erradas = (
        supabase_admin.table("tentativas_questoes")
        .select("questao_id")
        .eq("usuario_id", id_usuario)
        .eq("acertou", False)
        .execute()
        .data or []
    )

    if not tentativas_erradas:
        return None

    ids_questoes = list({t["questao_id"] for t in tentativas_erradas})

    questoes = (
        supabase_admin.table("questoes")
        .select("id, materia_id")
        .in_("id", ids_questoes)
        .execute()
        .data or []
    )

    contagem_por_materia: dict[str, int] = {}
    for questao in questoes:
        materia_id = questao["materia_id"]
        contagem_por_materia[materia_id] = contagem_por_materia.get(materia_id, 0) + 1

    if not contagem_por_materia:
        return None

    materia_id_mais_errada = max(contagem_por_materia, key=contagem_por_materia.get)

    materia = (
        supabase_admin.table("materias")
        .select("id, nome")
        .eq("id", materia_id_mais_errada)
        .limit(1)
        .execute()
        .data
    )

    return materia[0] if materia else None


def gerar_slug_unico_lista(titulo: str) -> str:
    slug_base = gerar_slug(titulo)
    slug = slug_base
    sufixo = 1

    while (
        supabase_admin.table("listas_questoes")
        .select("id")
        .eq("slug", slug)
        .limit(1)
        .execute()
        .data
    ):
        sufixo += 1
        slug = f"{slug_base}-{sufixo}"

    return slug


@router.post('/listas/gerar-ia', status_code=201, response_model=GerarListaIAResponse)
def gerar_lista_ia(usuario_atual=Depends(pegar_usuario_atual)):
    try:
        id_usuario = str(usuario_atual.id)

        tentativas = (
            supabase_admin.table("tentativas_questoes")
            .select("id", count="exact")
            .eq("usuario_id", id_usuario)
            .execute()
        )

        if not tentativas.count:
            raise HTTPException(
                status_code=422,
                detail="Não há dados suficientes para gerar uma lista personalizada"
            )

        materia = materia_com_mais_erros(id_usuario)
        if not materia:
            raise HTTPException(
                status_code=422,
                detail="Não há dados suficientes para gerar uma lista personalizada"
            )

        try:
            questoes_geradas = get_ai_provider().gerar_questoes(
                materia=materia["nome"],
                topico=materia["nome"],
                quantidade=QUANTIDADE_QUESTOES_LISTA_IA,
            )
        except (AIIndisponivelError, AIRespostaInvalidaError) as erro:
            raise HTTPException(
                status_code=502,
                detail=f"Não foi possível gerar questões com IA: {erro}"
            )

        if not questoes_geradas:
            raise HTTPException(
                status_code=502,
                detail="A IA não retornou nenhuma questão"
            )

        titulo = f"Lista personalizada — {materia['nome']}"
        nova_lista = {
            "titulo": titulo,
            "slug": gerar_slug_unico_lista(titulo),
            "materia_id": materia["id"],
            "tipo_prova_id": None,
            "topico_id": None,
            "dificuldade": None,
            "tipo_lista": "gerada_ia",
        }

        resposta_lista = supabase_admin.table("listas_questoes").insert(nova_lista).execute()

        if not resposta_lista.data:
            raise HTTPException(
                status_code=500,
                detail="Não foi possível criar a lista de questões"
            )

        lista_id = resposta_lista.data[0]["id"]

        for ordem, questao_gerada in enumerate(questoes_geradas):
            nova_questao = {
                "materia_id": materia["id"],
                "dificuldade": questao_gerada.get("dificuldade") or "medio",
                "enunciado": questao_gerada["enunciado"],
                "explicacao": questao_gerada.get("explicacao"),
                "ativo": True,
                "alternativa_correta": None,
            }

            resposta_questao = supabase_admin.table("questoes").insert(nova_questao).execute()
            if not resposta_questao.data:
                continue

            questao_id = resposta_questao.data[0]["id"]

            letras = ["A", "B", "C", "D", "E"]
            id_alternativa_correta = None
            for indice, texto_alternativa in enumerate(questao_gerada.get("alternativas", [])):
                letra = letras[indice] if indice < len(letras) else str(indice)
                resposta_alternativa = (
                    supabase_admin.table("alternativas_questao")
                    .insert({
                        "questao_id": questao_id,
                        "letra": letra,
                        "conteudo": texto_alternativa,
                        "ordem": indice,
                    })
                    .execute()
                )
                if letra == questao_gerada.get("resposta_correta"):
                    id_alternativa_correta = resposta_alternativa.data[0]["id"]

            if id_alternativa_correta:
                supabase_admin.table("questoes").update(
                    {"alternativa_correta": id_alternativa_correta}
                ).eq("id", questao_id).execute()

            supabase_admin.table("itens_lista_questoes").insert({
                "lista_questoes_id": lista_id,
                "questao_id": questao_id,
                "ordem": ordem,
            }).execute()

        lista_criada = (
            supabase_admin.table("listas_questoes")
            .select("*")
            .eq("id", lista_id)
            .limit(1)
            .execute()
            .data[0]
        )

        return {
            "id": lista_criada["id"],
            "slug": lista_criada.get("slug"),
        }

    except HTTPException:
        raise

    except Exception as erro:
        print(f"Erro ao gerar lista com IA: {erro}")

        raise HTTPException(
            status_code=500,
            detail="Erro ao gerar lista com IA"
        )
