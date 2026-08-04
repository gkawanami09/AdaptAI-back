from fastapi import APIRouter, HTTPException, Depends
from database import supabase_admin
from datetime import datetime, timezone, date, timedelta
from utils.autenticacao import pegar_usuario_atual
from schemas.aula_visualizacao_schema import (
    AulaVisualizacaoResponse,
    AtualizarProgressoAula,
    AtualizarProgressoAulaResponse,
    AtualizarConceitoAula,
    AtualizarConceitoAulaResponse,
)

router = APIRouter(
    prefix='/aluno/aulas',
    tags=['Aluno - Visualização de Aula']
)

DIFICULDADE_LABEL = {
    "basico": "Básico",
    "medio": "Médio",
    "dificil": "Difícil",
}


def obter_aula_por_slug(slug: str):
    resposta = (
        supabase_admin.table("aulas")
        .select("id, slug, titulo, materia_id, topico_id, resumo, dificuldade, ordem")
        .eq("slug", slug)
        .limit(1)
        .execute()
    )
    if not resposta.data:
        raise HTTPException(status_code=404, detail="Aula não encontrada")
    return resposta.data[0]


def montar_resposta_aula(aula: dict, id_usuario: str) -> dict:
    materia = (
        supabase_admin.table("materias")
        .select("nome, cor")
        .eq("id", aula["materia_id"])
        .limit(1)
        .execute()
    )
    if not materia.data:
        raise HTTPException(status_code=404, detail="Aula não encontrada")
    materia = materia.data[0]

    conteudos = (
        supabase_admin.table("aulas_conteudo")
        .select("id, duracao")
        .eq("aula_id", aula["id"])
        .eq("ativo", True)
        .execute()
        .data or []
    )
    duracao_min = sum(c["duracao"] for c in conteudos)
    ids_conteudo = [c["id"] for c in conteudos]

    video_url = None
    if ids_conteudo:
        videos = (
            supabase_admin.table("aulas_video")
            .select("aulas_conteudo_id, video_link")
            .in_("aulas_conteudo_id", ids_conteudo)
            .execute()
            .data or []
        )
        if videos:
            video_url = videos[0]["video_link"]

    progresso_resposta = (
        supabase_admin.table("progresso_aulas_usuario")
        .select("status, percentual_progresso")
        .eq("usuario_id", id_usuario)
        .eq("aula_id", aula["id"])
        .limit(1)
        .execute()
    )
    progresso = progresso_resposta.data[0] if progresso_resposta.data else None
    status = progresso["status"].replace("_", "-") if progresso else "nao-iniciada"
    percentual = int(progresso["percentual_progresso"]) if progresso else 0

    conceitos_banco = (
        supabase_admin.table("conceitos_aula")
        .select("id, titulo, ordem")
        .eq("aula_id", aula["id"])
        .order("ordem")
        .execute()
        .data or []
    )
    ids_conceitos = [c["id"] for c in conceitos_banco]
    conceitos_marcados = (
        supabase_admin.table("conceitos_aula_usuario")
        .select("conceito_aula_id")
        .eq("usuario_id", id_usuario)
        .in_("conceito_aula_id", ids_conceitos)
        .execute()
        .data or []
    ) if ids_conceitos else []
    ids_marcados = {c["conceito_aula_id"] for c in conceitos_marcados}

    conceitos = [
        {
            "id": c["id"],
            "label": c["titulo"],
            "concluido": c["id"] in ids_marcados,
        }
        for c in conceitos_banco
    ]

    modulo = None
    proxima_aula = None
    if aula["topico_id"]:
        aulas_topico = (
            supabase_admin.table("aulas")
            .select("id, slug, titulo, ordem, dificuldade")
            .eq("topico_id", aula["topico_id"])
            .eq("ativo", True)
            .order("ordem")
            .execute()
            .data or []
        )
        ids_aulas_topico = [a["id"] for a in aulas_topico]
        progresso_topico = (
            supabase_admin.table("progresso_aulas_usuario")
            .select("aula_id, status")
            .eq("usuario_id", id_usuario)
            .in_("aula_id", ids_aulas_topico)
            .execute()
            .data or []
        ) if ids_aulas_topico else []
        status_por_aula = {p["aula_id"]: p["status"] for p in progresso_topico}

        topico = (
            supabase_admin.table("topicos")
            .select("nome")
            .eq("topico_id", aula["topico_id"])
            .limit(1)
            .execute()
        )
        titulo_modulo = topico.data[0]["nome"] if topico.data else ""

        aulas_modulo = []
        for a in aulas_topico:
            if a["id"] == aula["id"]:
                status_item = "atual"
            elif status_por_aula.get(a["id"]) == "concluida":
                status_item = "concluida"
            else:
                status_item = "bloqueada"
            aulas_modulo.append({
                "ordem": a["ordem"],
                "titulo": a["titulo"],
                "status": status_item,
            })

        modulo = {"titulo": titulo_modulo, "aulas": aulas_modulo}

        posteriores = [a for a in aulas_topico if a["ordem"] > aula["ordem"]]
        if posteriores:
            proxima = posteriores[0]
            duracao_proxima = (
                supabase_admin.table("aulas_conteudo")
                .select("duracao")
                .eq("aula_id", proxima["id"])
                .eq("ativo", True)
                .execute()
                .data or []
            )
            proxima_aula = {
                "slug": proxima["slug"],
                "titulo": proxima["titulo"],
                "duracao_min": sum(d["duracao"] for d in duracao_proxima),
                "dificuldade": DIFICULDADE_LABEL.get(proxima["dificuldade"], proxima["dificuldade"]),
            }

    resumo = [linha.strip() for linha in (aula["resumo"] or "").split("\n") if linha.strip()]

    return {
        "slug": aula["slug"],
        "titulo": aula["titulo"],
        "materia": materia["nome"],
        "materia_cor": materia["cor"],
        "duracao_min": duracao_min,
        "dificuldade": DIFICULDADE_LABEL.get(aula["dificuldade"], aula["dificuldade"]),
        "progresso": percentual,
        "status": status,
        "video_url": video_url,
        "resumo": resumo,
        "conceitos": conceitos,
        "modulo": modulo,
        "proxima_aula": proxima_aula,
        "dica_ada": None,
    }


def registrar_xp_e_ofensiva(id_usuario: str, xp_ganho: int, duracao: int, agora: datetime):
    hoje = agora.date().isoformat()

    atividade_hoje = (
        supabase_admin.table("atividade_diaria")
        .select("id, minutos_estudo, xp_ganho, aulas_concluidas")
        .eq("usuario_id", id_usuario)
        .eq("data_atividade", hoje)
        .limit(1)
        .execute()
    )
    if atividade_hoje.data:
        registro = atividade_hoje.data[0]
        supabase_admin.table("atividade_diaria").update({
            "minutos_estudo": registro["minutos_estudo"] + duracao,
            "xp_ganho": registro["xp_ganho"] + xp_ganho,
            "aulas_concluidas": registro["aulas_concluidas"] + 1,
            "atualizado_em": agora.isoformat(),
        }).eq("id", registro["id"]).execute()
    else:
        supabase_admin.table("atividade_diaria").insert({
            "usuario_id": id_usuario,
            "data_atividade": hoje,
            "minutos_estudo": duracao,
            "xp_ganho": xp_ganho,
            "aulas_concluidas": 1,
        }).execute()

    estatisticas = (
        supabase_admin.table("estatisticas_usuario")
        .select("usuario_id, xp_total, ofensiva_atual_dias, maior_ofensiva_dias, ultima_atividade_data, minutos_estudo_total")
        .eq("usuario_id", id_usuario)
        .limit(1)
        .execute()
    )
    hoje_data = agora.date()

    if estatisticas.data:
        registro = estatisticas.data[0]
        ultima_data = date.fromisoformat(registro["ultima_atividade_data"]) if registro["ultima_atividade_data"] else None

        if ultima_data == hoje_data:
            nova_ofensiva = registro["ofensiva_atual_dias"]
        elif ultima_data == hoje_data - timedelta(days=1):
            nova_ofensiva = registro["ofensiva_atual_dias"] + 1
        else:
            nova_ofensiva = 1

        supabase_admin.table("estatisticas_usuario").update({
            "xp_total": registro["xp_total"] + xp_ganho,
            "ofensiva_atual_dias": nova_ofensiva,
            "maior_ofensiva_dias": max(nova_ofensiva, registro["maior_ofensiva_dias"]),
            "ultima_atividade_data": hoje_data.isoformat(),
            "minutos_estudo_total": registro["minutos_estudo_total"] + duracao,
            "atualizado_em": agora.isoformat(),
        }).eq("usuario_id", id_usuario).execute()
    else:
        supabase_admin.table("estatisticas_usuario").insert({
            "usuario_id": id_usuario,
            "xp_total": xp_ganho,
            "ofensiva_atual_dias": 1,
            "maior_ofensiva_dias": 1,
            "ultima_atividade_data": hoje_data.isoformat(),
            "minutos_estudo_total": duracao,
        }).execute()


@router.get('/{slug}', response_model=AulaVisualizacaoResponse)
def obter_aula(
    slug: str,
    usuario_atual=Depends(pegar_usuario_atual)
):
    try:
        aula = obter_aula_por_slug(slug)
        return montar_resposta_aula(aula, str(usuario_atual.id))

    except HTTPException:
        raise

    except Exception as erro:
        print(f"Erro ao buscar aula: {erro}")
        raise HTTPException(status_code=500, detail="Erro ao buscar aula")


@router.patch('/{slug}/concluir', response_model=AulaVisualizacaoResponse)
def concluir_aula(
    slug: str,
    usuario_atual=Depends(pegar_usuario_atual)
):
    try:
        id_usuario = str(usuario_atual.id)
        agora = datetime.now(timezone.utc)
        aula = obter_aula_por_slug(slug)

        progresso_atual = (
            supabase_admin.table("progresso_aulas_usuario")
            .select("id, status")
            .eq("usuario_id", id_usuario)
            .eq("aula_id", aula["id"])
            .limit(1)
            .execute()
        )

        ja_concluida = bool(progresso_atual.data) and progresso_atual.data[0]["status"] == "concluida"

        if progresso_atual.data:
            supabase_admin.table("progresso_aulas_usuario").update({
                "status": "concluida",
                "percentual_progresso": 100,
                "concluido_em": agora.isoformat(),
                "ultimo_acesso_em": agora.isoformat(),
                "atualizado_em": agora.isoformat(),
            }).eq("id", progresso_atual.data[0]["id"]).execute()
        else:
            supabase_admin.table("progresso_aulas_usuario").insert({
                "usuario_id": id_usuario,
                "aula_id": aula["id"],
                "status": "concluida",
                "percentual_progresso": 100,
                "iniciado_em": agora.isoformat(),
                "concluido_em": agora.isoformat(),
                "ultimo_acesso_em": agora.isoformat(),
            }).execute()

        if not ja_concluida:
            duracao_conteudos = (
                supabase_admin.table("aulas_conteudo")
                .select("duracao")
                .eq("aula_id", aula["id"])
                .eq("ativo", True)
                .execute()
                .data or []
            )
            duracao = sum(c["duracao"] for c in duracao_conteudos)
            registrar_xp_e_ofensiva(id_usuario, 10, duracao, agora)

        return montar_resposta_aula(aula, id_usuario)

    except HTTPException:
        raise

    except Exception as erro:
        print(f"Erro ao concluir aula: {erro}")
        raise HTTPException(status_code=500, detail="Erro ao concluir aula")


@router.patch('/{slug}/progresso', response_model=AtualizarProgressoAulaResponse)
def atualizar_progresso(
    slug: str,
    dados: AtualizarProgressoAula,
    usuario_atual=Depends(pegar_usuario_atual)
):
    try:
        id_usuario = str(usuario_atual.id)
        agora = datetime.now(timezone.utc)
        aula = obter_aula_por_slug(slug)

        if dados.progresso == 0:
            status = "nao_iniciada"
        elif dados.progresso == 100:
            status = "concluida"
        else:
            status = "em_andamento"

        progresso_atual = (
            supabase_admin.table("progresso_aulas_usuario")
            .select("id, percentual_progresso")
            .eq("usuario_id", id_usuario)
            .eq("aula_id", aula["id"])
            .limit(1)
            .execute()
        )

        if progresso_atual.data:
            registro = progresso_atual.data[0]
            if int(registro["percentual_progresso"]) != dados.progresso:
                dados_atualizacao = {
                    "status": status,
                    "percentual_progresso": dados.progresso,
                    "ultimo_acesso_em": agora.isoformat(),
                    "atualizado_em": agora.isoformat(),
                }
                if status == "concluida":
                    dados_atualizacao["concluido_em"] = agora.isoformat()
                supabase_admin.table("progresso_aulas_usuario").update(
                    dados_atualizacao
                ).eq("id", registro["id"]).execute()
        else:
            dados_insercao = {
                "usuario_id": id_usuario,
                "aula_id": aula["id"],
                "status": status,
                "percentual_progresso": dados.progresso,
                "iniciado_em": agora.isoformat(),
                "ultimo_acesso_em": agora.isoformat(),
            }
            if status == "concluida":
                dados_insercao["concluido_em"] = agora.isoformat()
            supabase_admin.table("progresso_aulas_usuario").insert(dados_insercao).execute()

        return {
            "slug": aula["slug"],
            "progresso": dados.progresso,
            "status": status.replace("_", "-"),
        }

    except HTTPException:
        raise

    except Exception as erro:
        print(f"Erro ao atualizar progresso da aula: {erro}")
        raise HTTPException(status_code=500, detail="Erro ao atualizar progresso da aula")


@router.patch('/{slug}/conceitos/{conceito_id}', response_model=AtualizarConceitoAulaResponse)
def atualizar_conceito(
    slug: str,
    conceito_id: str,
    dados: AtualizarConceitoAula,
    usuario_atual=Depends(pegar_usuario_atual)
):
    try:
        id_usuario = str(usuario_atual.id)
        aula = obter_aula_por_slug(slug)

        conceito = (
            supabase_admin.table("conceitos_aula")
            .select("id, titulo")
            .eq("id", conceito_id)
            .eq("aula_id", aula["id"])
            .limit(1)
            .execute()
        )
        if not conceito.data:
            raise HTTPException(status_code=404, detail="Conceito não encontrado")
        conceito = conceito.data[0]

        marcado = (
            supabase_admin.table("conceitos_aula_usuario")
            .select("id")
            .eq("usuario_id", id_usuario)
            .eq("conceito_aula_id", conceito_id)
            .limit(1)
            .execute()
        )

        if dados.concluido and not marcado.data:
            supabase_admin.table("conceitos_aula_usuario").insert({
                "usuario_id": id_usuario,
                "conceito_aula_id": conceito_id,
            }).execute()
        elif not dados.concluido and marcado.data:
            supabase_admin.table("conceitos_aula_usuario").delete().eq(
                "id", marcado.data[0]["id"]
            ).execute()

        return {
            "id": conceito["id"],
            "label": conceito["titulo"],
            "concluido": dados.concluido,
        }

    except HTTPException:
        raise

    except Exception as erro:
        print(f"Erro ao atualizar conceito da aula: {erro}")
        raise HTTPException(status_code=500, detail="Erro ao atualizar conceito da aula")
