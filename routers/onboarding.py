from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException

from database import supabase_admin
from schemas.onboarding_schema import OnboardingConcluir
from utils.autenticacao import pegar_usuario_atual


router = APIRouter(
    prefix="/onboarding",
    tags=["Onboarding"],
)


SLUG_TIPO_PROVA = {
    "enem": "enem",
    "fuvest": "fuvest",
    "unicamp": "unicamp",
    "vestibulares": "vestibulares-gerais",
}

MINUTOS_ESTUDO = {
    "30-minutos": 30,
    "1-hora": 60,
    "2-horas": 120,
    "3-horas-ou-mais": 180,
}

OBJETIVO_PRINCIPAL = {
    "melhorar-nota": "melhorar_nota",
    "universidade-publica": "passar_publica",
    "estudar-do-zero": "estudar_do_zero",
    "revisar": "revisar_conteudos",
    "treinar-redacao": "treinar_redacao",
}

SLUG_MATERIA = {
    "matematica": "math",
    "fisica": "fisica",
    "quimica": "quimica",
    "biologia": "biologia",
    "historia": "historia",
    "geografia": "geografia",
    "portugues": "portugues",
    "redacao": "redacao",
    "ingles": "ingles",
}


def buscar_tipo_prova(slug: str):
    resposta = (
        supabase_admin.table("tipos_prova")
        .select("id, nome, slug")
        .eq("slug", slug)
        .eq("ativo", True)
        .limit(1)
        .execute()
    )

    if not resposta.data:
        raise HTTPException(
            status_code=400,
            detail="O objetivo selecionado não está disponível.",
        )

    return resposta.data[0]


def buscar_materias(slugs: list[str]):
    resposta = (
        supabase_admin.table("materias")
        .select("id, nome, slug")
        .in_("slug", slugs)
        .eq("ativo", True)
        .execute()
    )

    materias_por_slug = {
        materia["slug"]: materia
        for materia in resposta.data or []
    }

    if any(slug not in materias_por_slug for slug in slugs):
        raise HTTPException(
            status_code=400,
            detail="Uma ou mais matérias selecionadas não estão disponíveis.",
        )

    return [materias_por_slug[slug] for slug in slugs]


def montar_onboarding(usuario_id: str):
    resposta_preferencias = (
        supabase_admin.table("preferencias_aluno")
        .select(
            "tipo_prova_id, objetivo_principal, minutos_estudo_dia, "
            "onboarding_concluido_em"
        )
        .eq("usuario_id", usuario_id)
        .limit(1)
        .execute()
    )

    preferencias = (
        resposta_preferencias.data[0]
        if resposta_preferencias.data
        else None
    )

    resposta_dificuldades = (
        supabase_admin.table("dificuldades_aluno_materias")
        .select("materia_id")
        .eq("usuario_id", usuario_id)
        .execute()
    )

    ids_materias = [
        dificuldade["materia_id"]
        for dificuldade in resposta_dificuldades.data or []
    ]
    materias = []

    if ids_materias:
        resposta_materias = (
            supabase_admin.table("materias")
            .select("id, nome, slug, icone, cor")
            .in_("id", ids_materias)
            .execute()
        )
        materias_por_id = {
            materia["id"]: materia
            for materia in resposta_materias.data or []
        }
        materias = [
            materias_por_id[materia_id]
            for materia_id in ids_materias
            if materia_id in materias_por_id
        ]

    resposta_plano = (
        supabase_admin.table("planos_estudo")
        .select(
            "id, tipo_prova_id, titulo, data_inicio, data_fim, status, criado_por"
        )
        .eq("usuario_id", usuario_id)
        .eq("criado_por", "ia")
        .order("criado_em", desc=True)
        .limit(1)
        .execute()
    )

    resposta_configuracoes = (
        supabase_admin.table("configuracoes_usuario")
        .select("personalizacao_ia_ativa")
        .eq("usuario_id", usuario_id)
        .limit(1)
        .execute()
    )

    return {
        "concluido": bool(
            preferencias
            and preferencias.get("onboarding_concluido_em")
        ),
        "preferencias": preferencias,
        "materias_dificuldade": materias,
        "plano": (
            resposta_plano.data[0]
            if resposta_plano.data
            else None
        ),
        "personalizacao_ia_ativa": bool(
            resposta_configuracoes.data
            and resposta_configuracoes.data[0]["personalizacao_ia_ativa"]
        ),
    }


@router.get("")
def obter_onboarding(usuario=Depends(pegar_usuario_atual)):
    try:
        return {
            "sucesso": True,
            "onboarding": montar_onboarding(str(usuario.id)),
        }

    except HTTPException:
        raise

    except Exception as erro:
        print(f"Erro ao buscar onboarding: {erro}")
        raise HTTPException(
            status_code=500,
            detail="Erro ao buscar onboarding.",
        )


@router.post("/concluir")
def concluir_onboarding(
    dados: OnboardingConcluir,
    usuario=Depends(pegar_usuario_atual),
):
    try:
        usuario_id = str(usuario.id)

        resposta_perfil = (
            supabase_admin.table("perfis")
            .select("id")
            .eq("id", usuario_id)
            .limit(1)
            .execute()
        )

        if not resposta_perfil.data:
            raise HTTPException(
                status_code=404,
                detail="Perfil não encontrado.",
            )

        tipo_prova = buscar_tipo_prova(
            SLUG_TIPO_PROVA[dados.objetivo]
        )
        slugs_materias = [
            SLUG_MATERIA[materia]
            for materia in dados.materias
        ]
        materias = buscar_materias(slugs_materias)
        agora = datetime.now(timezone.utc).isoformat()

        preferencias = {
            "tipo_prova_id": tipo_prova["id"],
            "objetivo_principal": OBJETIVO_PRINCIPAL[dados.meta_principal],
            "minutos_estudo_dia": MINUTOS_ESTUDO[dados.tempo_estudo],
            "onboarding_concluido_em": agora,
            "atualizado_em": agora,
        }

        resposta_preferencias = (
            supabase_admin.table("preferencias_aluno")
            .select("usuario_id")
            .eq("usuario_id", usuario_id)
            .limit(1)
            .execute()
        )

        if resposta_preferencias.data:
            (
                supabase_admin.table("preferencias_aluno")
                .update(preferencias)
                .eq("usuario_id", usuario_id)
                .execute()
            )
        else:
            preferencias["usuario_id"] = usuario_id
            (
                supabase_admin.table("preferencias_aluno")
                .insert(preferencias)
                .execute()
            )

        (
            supabase_admin.table("dificuldades_aluno_materias")
            .delete()
            .eq("usuario_id", usuario_id)
            .execute()
        )
        (
            supabase_admin.table("dificuldades_aluno_materias")
            .insert([
                {
                    "usuario_id": usuario_id,
                    "materia_id": materia["id"],
                }
                for materia in materias
            ])
            .execute()
        )

        dados_plano = {
            "tipo_prova_id": tipo_prova["id"],
            "titulo": f"Plano de estudos - {tipo_prova['nome']}",
            "data_inicio": date.today().isoformat(),
            "status": "ativo",
            "criado_por": "ia",
            "atualizado_em": agora,
        }

        resposta_plano = (
            supabase_admin.table("planos_estudo")
            .select("id")
            .eq("usuario_id", usuario_id)
            .eq("criado_por", "ia")
            .eq("status", "ativo")
            .order("criado_em", desc=True)
            .limit(1)
            .execute()
        )

        if resposta_plano.data:
            (
                supabase_admin.table("planos_estudo")
                .update(dados_plano)
                .eq("id", resposta_plano.data[0]["id"])
                .execute()
            )
        else:
            dados_plano["usuario_id"] = usuario_id
            (
                supabase_admin.table("planos_estudo")
                .insert(dados_plano)
                .execute()
            )

        resposta_configuracoes = (
            supabase_admin.table("configuracoes_usuario")
            .select("usuario_id")
            .eq("usuario_id", usuario_id)
            .limit(1)
            .execute()
        )

        if resposta_configuracoes.data:
            (
                supabase_admin.table("configuracoes_usuario")
                .update({"personalizacao_ia_ativa": True})
                .eq("usuario_id", usuario_id)
                .execute()
            )
        else:
            (
                supabase_admin.table("configuracoes_usuario")
                .insert({
                    "usuario_id": usuario_id,
                    "personalizacao_ia_ativa": True,
                })
                .execute()
            )

        return {
            "sucesso": True,
            "mensagem": "Onboarding concluído e plano criado com sucesso.",
            "onboarding": montar_onboarding(usuario_id),
        }

    except HTTPException:
        raise

    except Exception as erro:
        print(f"Erro ao concluir onboarding: {erro}")
        raise HTTPException(
            status_code=500,
            detail="Erro ao concluir onboarding.",
        )
