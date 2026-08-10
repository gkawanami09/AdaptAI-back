from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from database import supabase_admin
from utils.autenticacao import pegar_usuario_atual
from schemas.redacao_schema import (
    GetRedacaoTemasResponse,
    GetRedacaoTemaResponse,
    PostRedacaoEnvioParams,
    PostRedacaoEnvioResponse,
    GetRedacaoCorrecaoResponse,
)
from services.redacao_correcao_service import processar_correcao
from services.gamificacao import EventoGamificacao, registrar_evento_gamificacao

router = APIRouter(
    prefix='/aluno/redacao',
    tags=['Aluno - Redação']
)


def obter_tema_por_slug(slug: str):
    resposta = (
        supabase_admin.table("temas_redacao")
        .select("id, slug, titulo, tag, tag_cor, proposta, dica_ada")
        .eq("slug", slug)
        .limit(1)
        .execute()
    )
    if not resposta.data:
        raise HTTPException(status_code=404, detail="Tema de redação não encontrado")
    return resposta.data[0]


@router.get('/temas', response_model=GetRedacaoTemasResponse)
def listar_temas(usuario_atual=Depends(pegar_usuario_atual)):
    try:
        temas = (
            supabase_admin.table("temas_redacao")
            .select("id, slug, titulo, tag, tag_cor, proposta")
            .eq("ativo", True)
            .execute()
            .data or []
        )

        return {
            "temas": [
                {
                    "id": tema["id"],
                    "slug": tema["slug"],
                    "titulo": tema["titulo"],
                    "tag": tema["tag"],
                    "tag_cor": tema["tag_cor"],
                    "descricao": tema["proposta"],
                }
                for tema in temas
            ]
        }

    except HTTPException:
        raise

    except Exception as erro:
        print(f"Erro ao listar temas de redação: {erro}")
        raise HTTPException(status_code=500, detail="Erro ao listar temas de redação")


@router.get('/temas/{slug}', response_model=GetRedacaoTemaResponse)
def obter_tema(slug: str, usuario_atual=Depends(pegar_usuario_atual)):
    try:
        tema = obter_tema_por_slug(slug)

        competencias = (
            supabase_admin.table("competencias_redacao")
            .select("number, title, description, color")
            .eq("tema_redacao_id", tema["id"])
            .order("number")
            .execute()
            .data or []
        )

        repertorios = (
            supabase_admin.table("repertorios")
            .select("titulo, descricao")
            .eq("tema_redacao_id", tema["id"])
            .eq("ativo", True)
            .execute()
            .data or []
        )

        return {
            "slug": tema["slug"],
            "titulo": tema["titulo"],
            "tag": tema["tag"],
            "tag_cor": tema["tag_cor"],
            "descricao": tema["proposta"],
            "competencias": competencias,
            "repertorios": [
                f"{r['titulo']} — {r['descricao']}" if r.get("descricao") else r["titulo"]
                for r in repertorios
            ],
            "dica_ada": tema.get("dica_ada"),
        }

    except HTTPException:
        raise

    except Exception as erro:
        print(f"Erro ao buscar tema de redação: {erro}")
        raise HTTPException(status_code=500, detail="Erro ao buscar tema de redação")


@router.post('/temas/{slug}/envios', response_model=PostRedacaoEnvioResponse)
def enviar_redacao(
    slug: str,
    dados: PostRedacaoEnvioParams,
    background_tasks: BackgroundTasks,
    usuario_atual=Depends(pegar_usuario_atual)
):
    try:
        if not dados.texto.strip():
            raise HTTPException(status_code=422, detail="O texto da redação não pode estar vazio")

        tema = obter_tema_por_slug(slug)

        envio = (
            supabase_admin.table("redacoes_enviadas")
            .insert({
                "usuario_id": str(usuario_atual.id),
                "tema_redacao_id": tema["id"],
                "texto": dados.texto,
                "status": "pendente",
            })
            .execute()
        )

        registro = envio.data[0]

        registrar_evento_gamificacao(str(usuario_atual.id), EventoGamificacao.REDACAO_ENVIADA)
        background_tasks.add_task(processar_correcao, registro["id"], dados.texto, str(usuario_atual.id))

        return {
            "id": registro["id"],
            "slug": tema["slug"],
            "status": registro["status"],
            "texto": registro["texto"],
        }

    except HTTPException:
        raise

    except Exception as erro:
        print(f"Erro ao enviar redação: {erro}")
        raise HTTPException(status_code=500, detail="Erro ao enviar redação")


STATUS_LABEL_PENDENTE = {
    "pendente": "Aguardando correção",
    "processando": "Corrigindo sua redação",
    "erro": "Não foi possível corrigir sua redação",
}

# O banco usa "corrigindo"/"corrigida" (ver migrations/redacao_temas.sql);
# o contrato da API usa "processando"/"concluida".
STATUS_BANCO_PARA_API = {
    "pendente": "pendente",
    "corrigindo": "processando",
    "corrigida": "concluida",
    "erro": "erro",
}


@router.get('/envios/{envio_id}', response_model=GetRedacaoCorrecaoResponse)
def obter_correcao_envio(envio_id: str, usuario_atual=Depends(pegar_usuario_atual)):
    try:
        envio_resposta = (
            supabase_admin.table("redacoes_enviadas")
            .select("id, status, tema_redacao_id, usuario_id, analise_ia")
            .eq("id", envio_id)
            .limit(1)
            .execute()
        )
        if not envio_resposta.data:
            raise HTTPException(status_code=404, detail="Envio de redação não encontrado")
        envio = envio_resposta.data[0]

        tema_resposta = (
            supabase_admin.table("temas_redacao")
            .select("slug")
            .eq("id", envio["tema_redacao_id"])
            .limit(1)
            .execute()
        )
        slug = tema_resposta.data[0]["slug"] if tema_resposta.data else ""

        status = STATUS_BANCO_PARA_API.get(envio["status"], "pendente")
        analise_ia = envio.get("analise_ia")

        if status == "concluida" and analise_ia:
            return {
                "id": envio["id"],
                "slug": slug,
                "status": status,
                **analise_ia,
            }

        return {
            "id": envio["id"],
            "slug": slug,
            "status": status,
            "notaTotal": 0,
            "notaMaxima": 1000,
            "statusLabel": STATUS_LABEL_PENDENTE.get(status, "Aguardando correção"),
            "mensagemMotivacional": "",
            "competencias": [],
            "insights": [],
            "pontosMelhoria": [],
            "repertoriosSugeridos": [],
            "resumoAda": "",
        }

    except HTTPException:
        raise

    except Exception as erro:
        print(f"Erro ao buscar correção da redação: {erro}")
        raise HTTPException(status_code=500, detail="Erro ao buscar correção da redação")
