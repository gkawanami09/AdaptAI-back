from fastapi import APIRouter, HTTPException, Depends, Query
from database import supabase_admin
from uuid import UUID
from utils.autenticacao import pegar_usuario_atual
from schemas.banco_questoes_schema import (
    BancoQuestoesFiltrosResponse,
    BancoQuestoesListasResponse,
    GerarListaIAResponse,
)

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
        }

    except Exception as erro:
        print(f"Erro ao obter filtros do banco de questões: {erro}")

        raise HTTPException(
            status_code=500,
            detail="Erro ao obter filtros do banco de questões"
        )


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

    ids_questoes_todas = list({item["questao_id"] for item in itens})

    tentativas = (
        supabase_admin.table("tentativas_questoes")
        .select("questao_id, acertou")
        .eq("usuario_id", usuario_id)
        .in_("questao_id", ids_questoes_todas)
        .execute()
        .data or []
    ) if ids_questoes_todas else []

    questoes_respondidas = {t["questao_id"] for t in tentativas}

    listas = []
    for lista in listas_banco:
        materia = materias_por_id.get(lista["materia_id"])
        tipo_prova = tipos_prova_por_id.get(lista["tipo_prova_id"])
        questoes_da_lista = questoes_por_lista.get(lista["id"], [])
        concluidas = sum(1 for q in questoes_da_lista if q in questoes_respondidas)
        dificuldade = lista.get("dificuldade") or "medio"

        listas.append({
            "id": lista["id"],
            "slug": lista.get("slug"),
            "icone": materia["icone"] if materia else "📚",
            "icone_cor": materia["cor"] if materia else ICONE_COR_PADRAO,
            "titulo": lista["titulo"],
            "dificuldade": DIFICULDADE_LABEL.get(dificuldade, dificuldade),
            "dificuldade_cor": DIFICULDADE_COR.get(dificuldade, "gray"),
            "vestibular": tipo_prova["nome"] if tipo_prova else "Geral",
            "questoes_concluidas": concluidas,
            "questoes_totais": len(questoes_da_lista),
            "progresso_cor": materia["cor"] if materia else PROGRESSO_COR_PADRAO,
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

        # TODO: integração com o mecanismo de IA para gerar listas personalizadas
        # ainda não implementada. Aguardando definição do serviço responsável.
        raise HTTPException(
            status_code=422,
            detail="Geração automática de listas ainda não disponível"
        )

    except HTTPException:
        raise

    except Exception as erro:
        print(f"Erro ao gerar lista com IA: {erro}")

        raise HTTPException(
            status_code=500,
            detail="Erro ao gerar lista com IA"
        )
