import random
from fastapi import APIRouter, HTTPException, Depends
from database import supabase_admin
from datetime import datetime, timezone
from uuid import UUID
from utils.autenticacao import pegar_usuario_atual
from schemas.simulados_schema import (
    SimuladosResponse,
    IniciarTentativaResponse,
    RecuperarTentativaResponse,
    ResponderTentativaPayload,
    ResponderTentativaResponse,
    FinalizarTentativaResponse,
    ResultadoTentativaResponse,
    RevisaoTentativaResponse,
    HistoricoTentativasResponse,
)
from services.simulados_service import selecionar_questoes_evitando, calcular_resultado, calcular_resultado_por_area
from services.gamificacao import EventoGamificacao, conceder_xp_e_atividade, registrar_evento_gamificacao

router = APIRouter(
    prefix='/aluno/simulados',
    tags=['Aluno - Simulados']
)

TAG_POR_TIPO_MODELO = {
    "completo": ("Completo", "purple"),
    "rapido": ("Rápido", "blue"),
    "treino_area": ("Treino por área", "teal"),
    "revisao_erros": ("Revisão de erros", "gold"),
    "personalizado": ("Personalizado", "green"),
}

ICONE_POR_TIPO_MODELO = {
    "completo": ("📋", "purple"),
    "rapido": ("⚡", "blue"),
    "treino_area": ("🎯", "teal"),
    "revisao_erros": ("🔁", "gold"),
    "personalizado": ("🧩", "green"),
}

# Status legados, gravados antes deste contrato — traduzidos na leitura
# pra API nunca expor nomenclatura antiga. Escrita sempre usa os valores
# novos (em_andamento/concluida/expirada/cancelada).
STATUS_LEGADO_PARA_ATUAL = {"concluido": "concluida", "abandonado": "cancelada"}


def _status_publico(status_db: str) -> str:
    return STATUS_LEGADO_PARA_ATUAL.get(status_db, status_db)


def formatar_duracao(minutos: int | None) -> str:
    if not minutos:
        return "0min"

    horas = minutos // 60
    restante = minutos % 60

    if horas and restante:
        return f"{horas}h{restante:02d}"
    if horas:
        return f"{horas}h"
    return f"{restante}min"


def formatar_duracao_segundos(segundos: int | None) -> str:
    if not segundos:
        return "0min"

    return formatar_duracao(segundos // 60)


def montar_resumo(usuario_id: str):
    sessoes_concluidas = (
        supabase_admin.table("sessoes_simulado")
        .select("nota_estimada, duracao_segundos, percentual_acerto")
        .eq("usuario_id", usuario_id)
        .in_("status", ["concluido", "concluida"])
        .execute()
        .data or []
    )

    if not sessoes_concluidas:
        return {
            "nota_estimada": 0,
            "tempo_medio": "0min",
            "taxa_acerto_percentual": 0,
        }

    notas = [s["nota_estimada"] for s in sessoes_concluidas if s["nota_estimada"] is not None]
    duracoes = [s["duracao_segundos"] for s in sessoes_concluidas if s["duracao_segundos"] is not None]
    percentuais = [s["percentual_acerto"] for s in sessoes_concluidas if s["percentual_acerto"] is not None]

    nota_estimada = round(sum(notas) / len(notas)) if notas else 0
    tempo_medio_segundos = round(sum(duracoes) / len(duracoes)) if duracoes else 0
    taxa_acerto = round(sum(percentuais) / len(percentuais)) if percentuais else 0

    return {
        "nota_estimada": nota_estimada,
        "tempo_medio": formatar_duracao_segundos(tempo_medio_segundos),
        "taxa_acerto_percentual": taxa_acerto,
    }


def montar_catalogo():
    modelos = (
        supabase_admin.table("modelos_simulado")
        .select("id, slug, titulo, descricao, tipo_modelo, total_questoes, duracao_minutos")
        .eq("ativo", True)
        .execute()
        .data or []
    )

    if not modelos:
        return []

    ids_modelos = [m["id"] for m in modelos]
    areas_config = (
        supabase_admin.table("modelos_simulado_areas")
        .select("modelo_simulado_id, area, quantidade_questoes")
        .in_("modelo_simulado_id", ids_modelos)
        .execute()
        .data or []
    ) if ids_modelos else []
    areas_por_modelo: dict[str, list[dict]] = {}
    for linha in areas_config:
        areas_por_modelo.setdefault(linha["modelo_simulado_id"], []).append(linha)

    catalogo = []
    for modelo in modelos:
        icone, icone_cor = ICONE_POR_TIPO_MODELO.get(modelo["tipo_modelo"], ("📋", "gray"))
        tag, tag_cor = TAG_POR_TIPO_MODELO.get(modelo["tipo_modelo"], (modelo["tipo_modelo"], "gray"))

        descricao = modelo.get("descricao")
        if not descricao:
            total_questoes = modelo.get("total_questoes") or 0
            descricao = f"{total_questoes} questões"

        # Config por área é opcional (ver migrations/simulados_tentativas.sql) —
        # sem ela, "materias"/"total_questoes" caem pro que já existia no
        # cadastro do modelo (só total_questoes; sem breakdown por área).
        config = areas_por_modelo.get(modelo["id"], [])
        total_questoes_extra = sum(c["quantidade_questoes"] for c in config) if config else modelo.get("total_questoes")
        materias_extra = [c["area"] for c in config] if config else None

        catalogo.append({
            "slug": modelo["slug"],
            "titulo": modelo["titulo"],
            "descricao": descricao,
            "icone": icone,
            "icone_cor": icone_cor,
            "tag": tag,
            "tag_cor": tag_cor,
            "duracao": formatar_duracao(modelo.get("duracao_minutos")),
            "duracao_minutos": modelo.get("duracao_minutos"),
            "total_questoes": total_questoes_extra,
            "materias": materias_extra,
        })

    return catalogo


def montar_historico(usuario_id: str):
    sessoes = (
        supabase_admin.table("sessoes_simulado")
        .select("id, concluido_em, duracao_segundos, nota_estimada, percentual_acerto, modelo_simulado_id")
        .eq("usuario_id", usuario_id)
        .in_("status", ["concluido", "concluida"])
        .order("concluido_em", desc=True)
        .execute()
        .data or []
    )

    if not sessoes:
        return []

    ids_modelos = list({s["modelo_simulado_id"] for s in sessoes if s["modelo_simulado_id"]})
    modelos = (
        supabase_admin.table("modelos_simulado")
        .select("id, titulo")
        .in_("id", ids_modelos)
        .execute()
        .data or []
    ) if ids_modelos else []
    modelos_por_id = {m["id"]: m for m in modelos}

    historico = []
    for sessao in sessoes:
        modelo = modelos_por_id.get(sessao["modelo_simulado_id"])
        modelo_titulo = modelo["titulo"] if modelo else "Simulado"

        concluido_em = sessao["concluido_em"]
        dia = "--"
        titulo = modelo_titulo

        if concluido_em:
            data_concluido = concluido_em[:10]
            ano, mes, dia_numero = data_concluido.split("-")
            dia = dia_numero
            titulo = f"{modelo_titulo} — {dia_numero}/{mes}"

        historico.append({
            "id": sessao["id"],
            "dia": dia,
            "titulo": titulo,
            "tempo": formatar_duracao_segundos(sessao.get("duracao_segundos")),
            "nota": sessao.get("nota_estimada") or 0,
            "acertos_percentual": round(sessao["percentual_acerto"]) if sessao.get("percentual_acerto") is not None else 0,
        })

    return historico


@router.get('', response_model=SimuladosResponse)
def obter_simulados(usuario_atual=Depends(pegar_usuario_atual)):
    try:
        id_usuario = str(usuario_atual.id)

        return {
            "resumo": montar_resumo(id_usuario),
            "catalogo": montar_catalogo(),
            "historico": montar_historico(id_usuario),
        }

    except Exception as erro:
        print(f"Erro ao obter simulados: {erro}")

        raise HTTPException(
            status_code=500,
            detail="Erro ao obter simulados"
        )


# --- Tentativas -----------------------------------------------------------

def _materias_banco() -> list[dict]:
    return supabase_admin.table("materias").select("id, slug, nome, cor, area").execute().data or []


def _buscar_modelo_ativo(slug: str) -> dict:
    resposta = (
        supabase_admin.table("modelos_simulado")
        .select("id, slug, titulo, tipo_prova_id, total_questoes, duracao_minutos")
        .eq("slug", slug)
        .eq("ativo", True)
        .limit(1)
        .execute()
    )
    if not resposta.data:
        raise HTTPException(status_code=404, detail="Simulado não encontrado")
    return resposta.data[0]


def _buscar_modelo_por_id(modelo_id: str | None) -> dict | None:
    if not modelo_id:
        return None
    resposta = (
        supabase_admin.table("modelos_simulado")
        .select("id, slug, titulo")
        .eq("id", modelo_id)
        .limit(1)
        .execute()
    )
    return resposta.data[0] if resposta.data else None


def _buscar_tentativa(tentativa_id: str, id_usuario: str) -> dict:
    resposta = (
        supabase_admin.table("sessoes_simulado")
        .select(
            "id, usuario_id, modelo_simulado_id, status, iniciado_em, tempo_limite_segundos, "
            "concluido_em, duracao_segundos, total_questoes, questoes_respondidas, "
            "respostas_corretas, percentual_acerto, nota_estimada"
        )
        .eq("id", tentativa_id)
        .limit(1)
        .execute()
    )
    # Nunca revela se a tentativa existe pra outro aluno — 404 pros dois casos.
    if not resposta.data or resposta.data[0]["usuario_id"] != id_usuario:
        raise HTTPException(status_code=404, detail="Tentativa não encontrada")

    tentativa = dict(resposta.data[0])
    tentativa["status"] = _status_publico(tentativa["status"])
    return tentativa


def _config_areas(modelo_id: str) -> dict[str, int]:
    linhas = (
        supabase_admin.table("modelos_simulado_areas")
        .select("area, quantidade_questoes")
        .eq("modelo_simulado_id", modelo_id)
        .execute()
        .data or []
    )
    return {linha["area"]: linha["quantidade_questoes"] for linha in linhas}


def _questoes_ultima_tentativa(modelo_id: str, usuario_id: str) -> set[str]:
    """IDs das questões usadas na última tentativa do aluno pra esse
    modelo — usado só como preferência de "não repetir" ao gerar uma
    tentativa nova (ver services/simulados_service.py:selecionar_questoes_evitando)."""
    ultima = (
        supabase_admin.table("sessoes_simulado")
        .select("id")
        .eq("usuario_id", usuario_id)
        .eq("modelo_simulado_id", modelo_id)
        .order("iniciado_em", desc=True)
        .limit(1)
        .execute()
        .data
    )
    if not ultima:
        return set()

    itens = (
        supabase_admin.table("questoes_sessao_simulado")
        .select("questao_id")
        .eq("sessao_simulado_id", ultima[0]["id"])
        .execute()
        .data or []
    )
    return {i["questao_id"] for i in itens}


def _selecionar_questoes_tentativa(modelo: dict, id_usuario: str) -> list[dict]:
    """Sorteia as questões de uma tentativa nova. Se o modelo tiver
    distribuição por área configurada (modelos_simulado_areas), sorteia
    por área; senão cai no sorteio "achatado" contra o banco inteiro
    (comportamento anterior, mantido pra modelos ainda não configurados).
    Sempre embaralha a ordem final entre as áreas."""
    evitar = _questoes_ultima_tentativa(modelo["id"], id_usuario)
    distribuicao = _config_areas(modelo["id"])
    materias = _materias_banco()

    selecionadas: list[dict] = []

    if distribuicao:
        materias_por_area: dict[str, list[str]] = {}
        for materia in materias:
            materias_por_area.setdefault(materia["area"], []).append(materia["id"])

        for area, quantidade in distribuicao.items():
            ids_materias_area = materias_por_area.get(area, [])
            pool: list[str] = []
            if ids_materias_area:
                pool_query = supabase_admin.table("questoes").select("id").eq("ativo", True).in_(
                    "materia_id", ids_materias_area
                )
                if modelo.get("tipo_prova_id"):
                    pool_query = pool_query.eq("tipo_prova_id", modelo["tipo_prova_id"])
                pool = [q["id"] for q in (pool_query.execute().data or [])]

            if not pool:
                raise HTTPException(
                    status_code=422,
                    detail=f"Não há questões suficientes de '{area}' para montar esse simulado"
                )

            escolhidas = selecionar_questoes_evitando(pool, quantidade, evitar)
            selecionadas.extend({"questao_id": qid, "area": area} for qid in escolhidas)
    else:
        materia_por_id = {m["id"]: m for m in materias}
        pool_query = supabase_admin.table("questoes").select("id, materia_id").eq("ativo", True)
        if modelo.get("tipo_prova_id"):
            pool_query = pool_query.eq("tipo_prova_id", modelo["tipo_prova_id"])
        questoes_banco = pool_query.execute().data or []

        if not questoes_banco:
            raise HTTPException(status_code=422, detail="Não há questões suficientes para montar esse simulado")

        pool = [q["id"] for q in questoes_banco]
        quantidade = modelo.get("total_questoes") or len(pool)
        escolhidas = selecionar_questoes_evitando(pool, quantidade, evitar)

        materia_por_questao = {q["id"]: q["materia_id"] for q in questoes_banco}
        for qid in escolhidas:
            materia = materia_por_id.get(materia_por_questao.get(qid))
            selecionadas.append({"questao_id": qid, "area": materia["area"] if materia else "matematica"})

    random.shuffle(selecionadas)
    for indice, item in enumerate(selecionadas):
        item["numero"] = indice + 1

    return selecionadas


def _montar_questoes_tentativa(tentativa_id: str, id_usuario: str, incluir_marcada: bool) -> list[dict]:
    itens = (
        supabase_admin.table("questoes_sessao_simulado")
        .select("questao_id, area, ordem")
        .eq("sessao_simulado_id", tentativa_id)
        .order("ordem")
        .execute()
        .data or []
    )
    ids_questoes = [i["questao_id"] for i in itens]

    questoes_banco = (
        supabase_admin.table("questoes")
        .select("id, materia_id, enunciado")
        .in_("id", ids_questoes)
        .execute()
        .data or []
    ) if ids_questoes else []
    questoes_por_id = {q["id"]: q for q in questoes_banco}

    alternativas = (
        supabase_admin.table("alternativas_questao")
        .select("id, questao_id, conteudo, letra, ordem")
        .in_("questao_id", ids_questoes)
        .order("ordem")
        .execute()
        .data or []
    ) if ids_questoes else []
    alternativas_por_questao: dict[str, list[dict]] = {}
    for alt in alternativas:
        alternativas_por_questao.setdefault(alt["questao_id"], []).append(alt)

    materias_por_id = {m["id"]: m for m in _materias_banco()}

    marcadas: dict[str, str] = {}
    if incluir_marcada:
        respostas = (
            supabase_admin.table("tentativas_questoes")
            .select("questao_id, alternativa_escolhida")
            .eq("usuario_id", id_usuario)
            .eq("sessao_simulado_id", tentativa_id)
            .execute()
            .data or []
        )
        marcadas = {r["questao_id"]: r["alternativa_escolhida"] for r in respostas}

    resultado = []
    for item in itens:
        questao = questoes_por_id.get(item["questao_id"])
        if not questao:
            continue

        materia = materias_por_id.get(questao["materia_id"])
        alts = sorted(alternativas_por_questao.get(questao["id"], []), key=lambda a: a["ordem"])

        questao_item = {
            "id": questao["id"],
            "numero": item["ordem"],
            "materia": materia["slug"] if materia else "geral",
            "materia_cor": materia["cor"] if materia else None,
            "enunciado": questao["enunciado"],
            "alternativas": [{"id": a["letra"].lower(), "texto": a.get("conteudo")} for a in alts],
        }
        if incluir_marcada:
            letra = marcadas.get(questao["id"])
            questao_item["alternativa_marcada"] = letra.lower() if letra else None

        resultado.append(questao_item)

    return resultado


def _resultado_ja_persistido(tentativa: dict) -> dict:
    """Monta o payload de resultado a partir do que já está gravado —
    usado tanto pra idempotência de `finalizar` quanto por `resultado` —
    nunca recalcula em cima de tentativas_questoes de novo."""
    total_questoes = tentativa.get("total_questoes") or 0
    respondidas = tentativa.get("questoes_respondidas") or 0
    acertos = tentativa.get("respostas_corretas") or 0
    percentual = tentativa.get("percentual_acerto") or 0
    tempo_gasto = tentativa.get("duracao_segundos") or 0

    areas = (
        supabase_admin.table("resultados_area_simulado")
        .select("area, total_questoes, respondidas, respostas_corretas, percentual_acerto")
        .eq("sessao_simulado_id", tentativa["id"])
        .execute()
        .data or []
    )

    return {
        "status": tentativa["status"],
        "total_questoes": total_questoes,
        "respondidas": respondidas,
        "acertos": acertos,
        "erros": respondidas - acertos,
        "nao_respondidas": total_questoes - respondidas,
        "percentual_acerto": percentual,
        "tempo_gasto_segundos": tempo_gasto,
        "desempenho_materias": [
            {
                "materia": a["area"],
                "total": a.get("total_questoes") or 0,
                "acertos": a.get("respostas_corretas") or 0,
                "erros": (a.get("respondidas") or 0) - (a.get("respostas_corretas") or 0),
                "percentual_acerto": a.get("percentual_acerto") or 0,
            }
            for a in areas
        ],
    }


def _finalizar_tentativa(tentativa: dict, id_usuario: str) -> dict:
    """Calcula e persiste o resultado final de uma tentativa em_andamento
    — o backend é a fonte de verdade do tempo (nunca confia num
    "tempo_gasto" vindo do cliente)."""
    agora = datetime.now(timezone.utc)
    iniciado_em = datetime.fromisoformat(tentativa["iniciado_em"].replace("Z", "+00:00"))
    tempo_limite = tentativa.get("tempo_limite_segundos") or 0
    segundos_decorridos = (agora - iniciado_em).total_seconds()

    tempo_gasto = max(0, int(segundos_decorridos))
    if tempo_limite:
        tempo_gasto = min(tempo_gasto, tempo_limite)

    status_final = "expirada" if (tempo_limite and segundos_decorridos > tempo_limite) else "concluida"

    itens = (
        supabase_admin.table("questoes_sessao_simulado")
        .select("questao_id, area")
        .eq("sessao_simulado_id", tentativa["id"])
        .execute()
        .data or []
    )
    area_por_questao = {i["questao_id"]: i["area"] for i in itens}
    total_por_area: dict[str, int] = {}
    for area in area_por_questao.values():
        total_por_area[area] = total_por_area.get(area, 0) + 1

    respostas_banco = (
        supabase_admin.table("tentativas_questoes")
        .select("questao_id, acertou")
        .eq("usuario_id", id_usuario)
        .eq("sessao_simulado_id", tentativa["id"])
        .execute()
        .data or []
    )

    resultado = calcular_resultado([bool(r["acertou"]) for r in respostas_banco])

    respostas_por_area: dict[str, list[bool]] = {}
    for resposta in respostas_banco:
        area = area_por_questao.get(resposta["questao_id"])
        if area:
            respostas_por_area.setdefault(area, []).append(bool(resposta["acertou"]))
    resultados_area = calcular_resultado_por_area(respostas_por_area)

    total_questoes = len(itens)
    respondidas = resultado["total_questoes"]
    acertos = resultado["respostas_corretas"]

    supabase_admin.table("sessoes_simulado").update({
        "status": status_final,
        "concluido_em": agora.isoformat(),
        "duracao_segundos": tempo_gasto,
        "total_questoes": total_questoes,
        "questoes_respondidas": respondidas,
        "respostas_corretas": acertos,
        "percentual_acerto": resultado["percentual_acerto"],
        "nota_estimada": resultado["nota_estimada"],
        "atualizado_em": agora.isoformat(),
    }).eq("id", tentativa["id"]).execute()

    if resultados_area:
        supabase_admin.table("resultados_area_simulado").insert([
            {
                "sessao_simulado_id": tentativa["id"],
                "area": r["area"],
                # `r["total_questoes"]` do cálculo é, na prática, a
                # contagem de RESPONDIDAS daquela área (só entram
                # respostas de fato dadas) — total_por_area é o total
                # atribuído à área na montagem da tentativa.
                "total_questoes": total_por_area.get(r["area"], r["total_questoes"]),
                "respondidas": r["total_questoes"],
                "respostas_corretas": r["respostas_corretas"],
                "percentual_acerto": r["percentual_acerto"],
                "nota": r["nota"],
            }
            for r in resultados_area
        ]).execute()

    conceder_xp_e_atividade(
        id_usuario, 20, minutos_estudo=tempo_gasto // 60, agora=agora, simulados_concluidos=1
    )
    registrar_evento_gamificacao(id_usuario, EventoGamificacao.SIMULADO_CONCLUIDO)

    return {
        "status": status_final,
        "total_questoes": total_questoes,
        "respondidas": respondidas,
        "acertos": acertos,
        "erros": respondidas - acertos,
        "nao_respondidas": total_questoes - respondidas,
        "percentual_acerto": resultado["percentual_acerto"],
        "tempo_gasto_segundos": tempo_gasto,
        "desempenho_materias": [
            {
                "materia": r["area"],
                "total": total_por_area.get(r["area"], r["total_questoes"]),
                "acertos": r["respostas_corretas"],
                "erros": r["total_questoes"] - r["respostas_corretas"],
                "percentual_acerto": r["percentual_acerto"],
            }
            for r in resultados_area
        ],
    }


def _expirar_se_necessario(tentativa: dict, id_usuario: str) -> dict:
    """Checa e finaliza automaticamente uma tentativa que estourou o
    tempo limite mas nunca foi finalizada explicitamente — chamado no
    início de qualquer leitura/escrita sobre a tentativa, pra isso nunca
    depender só do cliente avisar."""
    if tentativa["status"] != "em_andamento":
        return tentativa

    tempo_limite = tentativa.get("tempo_limite_segundos")
    if not tempo_limite:
        return tentativa

    iniciado_em = datetime.fromisoformat(tentativa["iniciado_em"].replace("Z", "+00:00"))
    agora = datetime.now(timezone.utc)
    if (agora - iniciado_em).total_seconds() <= tempo_limite:
        return tentativa

    _finalizar_tentativa(tentativa, id_usuario)
    return _buscar_tentativa(tentativa["id"], id_usuario)


@router.post('/{slug}/tentativas', response_model=IniciarTentativaResponse)
def iniciar_tentativa(slug: str, usuario_atual=Depends(pegar_usuario_atual)):
    try:
        id_usuario = str(usuario_atual.id)
        modelo = _buscar_modelo_ativo(slug)

        selecionadas = _selecionar_questoes_tentativa(modelo, id_usuario)
        agora = datetime.now(timezone.utc)
        tempo_limite = (modelo.get("duracao_minutos") or 0) * 60

        nova = (
            supabase_admin.table("sessoes_simulado")
            .insert({
                "usuario_id": id_usuario,
                "modelo_simulado_id": modelo["id"],
                "status": "em_andamento",
                "iniciado_em": agora.isoformat(),
                "tempo_limite_segundos": tempo_limite,
                "total_questoes": len(selecionadas),
            })
            .execute()
        )
        tentativa_id = nova.data[0]["id"]

        itens_payload = [
            {
                "sessao_simulado_id": tentativa_id,
                "questao_id": item["questao_id"],
                "area": item["area"],
                "ordem": item["numero"],
            }
            for item in selecionadas
        ]
        supabase_admin.table("questoes_sessao_simulado").insert(itens_payload).execute()

        questoes = _montar_questoes_tentativa(tentativa_id, id_usuario, incluir_marcada=False)

        return {
            "id": tentativa_id,
            "simulado": {"slug": modelo["slug"], "nome": modelo["titulo"]},
            "status": "em_andamento",
            "iniciado_em": agora.isoformat(),
            "tempo_limite_segundos": tempo_limite,
            "total_questoes": len(selecionadas),
            "questao_atual": 1,
            "questoes": questoes,
        }

    except HTTPException:
        raise

    except Exception as erro:
        print(f"Erro ao iniciar tentativa de simulado: {erro}")

        raise HTTPException(
            status_code=500,
            detail="Erro ao iniciar tentativa de simulado"
        )


@router.get('/tentativas', response_model=HistoricoTentativasResponse)
def historico_tentativas(usuario_atual=Depends(pegar_usuario_atual)):
    try:
        id_usuario = str(usuario_atual.id)

        sessoes = (
            supabase_admin.table("sessoes_simulado")
            .select(
                "id, modelo_simulado_id, status, iniciado_em, total_questoes, "
                "respostas_corretas, percentual_acerto, duracao_segundos"
            )
            .eq("usuario_id", id_usuario)
            .order("iniciado_em", desc=True)
            .execute()
            .data or []
        )

        ids_modelos = list({s["modelo_simulado_id"] for s in sessoes if s["modelo_simulado_id"]})
        modelos = (
            supabase_admin.table("modelos_simulado")
            .select("id, slug, titulo")
            .in_("id", ids_modelos)
            .execute()
            .data or []
        ) if ids_modelos else []
        modelos_por_id = {m["id"]: m for m in modelos}

        tentativas = []
        for sessao in sessoes:
            modelo = modelos_por_id.get(sessao["modelo_simulado_id"])
            tentativas.append({
                "id": sessao["id"],
                "simulado_slug": modelo["slug"] if modelo else "",
                "simulado_nome": modelo["titulo"] if modelo else "Simulado",
                "status": _status_publico(sessao["status"]),
                "data": sessao["iniciado_em"],
                "total_questoes": sessao.get("total_questoes") or 0,
                "acertos": sessao.get("respostas_corretas") or 0,
                "percentual_acerto": sessao.get("percentual_acerto") or 0,
                "tempo_gasto_segundos": sessao.get("duracao_segundos") or 0,
            })

        return {"tentativas": tentativas}

    except Exception as erro:
        print(f"Erro ao listar histórico de tentativas: {erro}")

        raise HTTPException(
            status_code=500,
            detail="Erro ao listar histórico de tentativas"
        )


@router.get('/tentativas/{tentativa_id}', response_model=RecuperarTentativaResponse)
def recuperar_tentativa(tentativa_id: UUID, usuario_atual=Depends(pegar_usuario_atual)):
    try:
        id_usuario = str(usuario_atual.id)
        tentativa = _buscar_tentativa(str(tentativa_id), id_usuario)
        tentativa = _expirar_se_necessario(tentativa, id_usuario)

        modelo = _buscar_modelo_por_id(tentativa["modelo_simulado_id"])
        questoes = _montar_questoes_tentativa(str(tentativa_id), id_usuario, incluir_marcada=True)

        if tentativa["status"] == "em_andamento":
            iniciado_em = datetime.fromisoformat(tentativa["iniciado_em"].replace("Z", "+00:00"))
            agora = datetime.now(timezone.utc)
            tempo_gasto = max(0, int((agora - iniciado_em).total_seconds()))
        else:
            tempo_gasto = tentativa.get("duracao_segundos") or 0

        respondidas = sum(1 for q in questoes if q.get("alternativa_marcada"))

        return {
            "id": tentativa["id"],
            "simulado": {"slug": modelo["slug"] if modelo else "", "nome": modelo["titulo"] if modelo else "Simulado"},
            "status": tentativa["status"],
            "iniciado_em": tentativa["iniciado_em"],
            "tempo_limite_segundos": tentativa.get("tempo_limite_segundos") or 0,
            "tempo_gasto_segundos": tempo_gasto,
            "total_questoes": tentativa.get("total_questoes") or len(questoes),
            "respondidas": respondidas,
            "questoes": questoes,
        }

    except HTTPException:
        raise

    except Exception as erro:
        print(f"Erro ao recuperar tentativa de simulado: {erro}")

        raise HTTPException(
            status_code=500,
            detail="Erro ao recuperar tentativa de simulado"
        )


@router.post('/tentativas/{tentativa_id}/respostas', response_model=ResponderTentativaResponse)
def responder_tentativa(
    tentativa_id: UUID,
    dados: ResponderTentativaPayload,
    usuario_atual=Depends(pegar_usuario_atual)
):
    try:
        id_usuario = str(usuario_atual.id)
        tentativa = _buscar_tentativa(str(tentativa_id), id_usuario)
        tentativa = _expirar_se_necessario(tentativa, id_usuario)

        if tentativa["status"] != "em_andamento":
            raise HTTPException(status_code=409, detail="Tentativa já finalizada")

        item = (
            supabase_admin.table("questoes_sessao_simulado")
            .select("questao_id")
            .eq("sessao_simulado_id", str(tentativa_id))
            .eq("questao_id", dados.questao_id)
            .limit(1)
            .execute()
        )
        if not item.data:
            raise HTTPException(status_code=404, detail="Questão não encontrada nessa tentativa")

        questao = (
            supabase_admin.table("questoes")
            .select("id, alternativa_correta")
            .eq("id", dados.questao_id)
            .limit(1)
            .execute()
        )
        if not questao.data:
            raise HTTPException(status_code=404, detail="Questão não encontrada")

        alternativas = (
            supabase_admin.table("alternativas_questao")
            .select("id, letra")
            .eq("questao_id", dados.questao_id)
            .execute()
            .data or []
        )
        letra_alvo = dados.alternativa_id.upper()
        alternativa_escolhida = next((a for a in alternativas if a["letra"] == letra_alvo), None)
        if not alternativa_escolhida:
            raise HTTPException(status_code=422, detail="Alternativa inválida")

        correta = alternativa_escolhida["id"] == questao.data[0]["alternativa_correta"]

        existente = (
            supabase_admin.table("tentativas_questoes")
            .select("id")
            .eq("usuario_id", id_usuario)
            .eq("sessao_simulado_id", str(tentativa_id))
            .eq("questao_id", dados.questao_id)
            .limit(1)
            .execute()
        )

        agora = datetime.now(timezone.utc).isoformat()

        if existente.data:
            supabase_admin.table("tentativas_questoes").update({
                "alternativa_escolhida": letra_alvo,
                "acertou": correta,
                "respondido_em": agora,
            }).eq("id", existente.data[0]["id"]).execute()
        else:
            supabase_admin.table("tentativas_questoes").insert({
                "usuario_id": id_usuario,
                "questao_id": dados.questao_id,
                "sessao_simulado_id": str(tentativa_id),
                "alternativa_escolhida": letra_alvo,
                "acertou": correta,
            }).execute()

        return {
            "questao_id": dados.questao_id,
            "alternativa_id": dados.alternativa_id.lower(),
            "salva": True,
        }

    except HTTPException:
        raise

    except Exception as erro:
        print(f"Erro ao responder questão do simulado: {erro}")

        raise HTTPException(
            status_code=500,
            detail="Erro ao responder questão do simulado"
        )


@router.post('/tentativas/{tentativa_id}/finalizar', response_model=FinalizarTentativaResponse)
def finalizar_tentativa_endpoint(tentativa_id: UUID, usuario_atual=Depends(pegar_usuario_atual)):
    try:
        id_usuario = str(usuario_atual.id)
        tentativa = _buscar_tentativa(str(tentativa_id), id_usuario)

        if tentativa["status"] == "em_andamento":
            resultado = _finalizar_tentativa(tentativa, id_usuario)
        else:
            resultado = _resultado_ja_persistido(tentativa)

        return {"id": tentativa["id"], **resultado}

    except HTTPException:
        raise

    except Exception as erro:
        print(f"Erro ao finalizar tentativa de simulado: {erro}")

        raise HTTPException(
            status_code=500,
            detail="Erro ao finalizar tentativa de simulado"
        )


@router.get('/tentativas/{tentativa_id}/resultado', response_model=ResultadoTentativaResponse)
def resultado_tentativa(tentativa_id: UUID, usuario_atual=Depends(pegar_usuario_atual)):
    try:
        id_usuario = str(usuario_atual.id)
        tentativa = _buscar_tentativa(str(tentativa_id), id_usuario)
        tentativa = _expirar_se_necessario(tentativa, id_usuario)

        if tentativa["status"] == "em_andamento":
            raise HTTPException(status_code=409, detail="Tentativa ainda em andamento")

        modelo = _buscar_modelo_por_id(tentativa["modelo_simulado_id"])
        resultado = _resultado_ja_persistido(tentativa)

        return {
            "id": tentativa["id"],
            "simulado": {"slug": modelo["slug"] if modelo else "", "nome": modelo["titulo"] if modelo else "Simulado"},
            **resultado,
            "iniciado_em": tentativa["iniciado_em"],
            "finalizado_em": tentativa.get("concluido_em"),
        }

    except HTTPException:
        raise

    except Exception as erro:
        print(f"Erro ao obter resultado da tentativa: {erro}")

        raise HTTPException(
            status_code=500,
            detail="Erro ao obter resultado da tentativa"
        )


@router.get('/tentativas/{tentativa_id}/revisao', response_model=RevisaoTentativaResponse)
def revisar_tentativa(tentativa_id: UUID, usuario_atual=Depends(pegar_usuario_atual)):
    try:
        id_usuario = str(usuario_atual.id)
        tentativa = _buscar_tentativa(str(tentativa_id), id_usuario)
        tentativa = _expirar_se_necessario(tentativa, id_usuario)

        if tentativa["status"] == "em_andamento":
            raise HTTPException(status_code=409, detail="Tentativa ainda em andamento")

        itens = (
            supabase_admin.table("questoes_sessao_simulado")
            .select("questao_id, ordem")
            .eq("sessao_simulado_id", str(tentativa_id))
            .order("ordem")
            .execute()
            .data or []
        )
        ids_questoes = [i["questao_id"] for i in itens]

        questoes_banco = (
            supabase_admin.table("questoes")
            .select("id, materia_id, enunciado, alternativa_correta, explicacao")
            .in_("id", ids_questoes)
            .execute()
            .data or []
        ) if ids_questoes else []
        questoes_por_id = {q["id"]: q for q in questoes_banco}

        alternativas = (
            supabase_admin.table("alternativas_questao")
            .select("id, questao_id, conteudo, letra, ordem")
            .in_("questao_id", ids_questoes)
            .order("ordem")
            .execute()
            .data or []
        ) if ids_questoes else []
        alternativas_por_questao: dict[str, list[dict]] = {}
        for alt in alternativas:
            alternativas_por_questao.setdefault(alt["questao_id"], []).append(alt)

        respostas = (
            supabase_admin.table("tentativas_questoes")
            .select("questao_id, alternativa_escolhida, acertou")
            .eq("usuario_id", id_usuario)
            .eq("sessao_simulado_id", str(tentativa_id))
            .execute()
            .data or []
        )
        resposta_por_questao = {r["questao_id"]: r for r in respostas}

        materias_por_id = {m["id"]: m for m in _materias_banco()}

        questoes_resposta = []
        for item in itens:
            questao = questoes_por_id.get(item["questao_id"])
            if not questao:
                continue

            materia = materias_por_id.get(questao["materia_id"])
            alts = sorted(alternativas_por_questao.get(questao["id"], []), key=lambda a: a["ordem"])
            letra_por_id_alternativa = {a["id"]: a["letra"] for a in alts}
            resposta = resposta_por_questao.get(questao["id"])

            questao_item = {
                "numero": item["ordem"],
                "questao_id": questao["id"],
                "materia": materia["slug"] if materia else "geral",
                "enunciado": questao["enunciado"],
                "alternativas": [{"id": a["letra"].lower(), "texto": a.get("conteudo")} for a in alts],
                "alternativa_correta": (
                    letra_por_id_alternativa.get(questao.get("alternativa_correta"), "").lower() or None
                ),
                "alternativa_marcada": resposta["alternativa_escolhida"].lower() if resposta else None,
                "acertou": bool(resposta["acertou"]) if resposta else False,
            }
            if questao.get("explicacao"):
                questao_item["explicacao"] = questao["explicacao"]

            questoes_resposta.append(questao_item)

        return {"id": tentativa["id"], "questoes": questoes_resposta}

    except HTTPException:
        raise

    except Exception as erro:
        print(f"Erro ao revisar tentativa de simulado: {erro}")

        raise HTTPException(
            status_code=500,
            detail="Erro ao revisar tentativa de simulado"
        )
