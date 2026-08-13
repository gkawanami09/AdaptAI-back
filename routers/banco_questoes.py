from fastapi import APIRouter, HTTPException, Depends, Query
from database import supabase_admin
from uuid import UUID
from utils.autenticacao import pegar_usuario_atual
from utils.textos import gerar_slug
from schemas.banco_questoes_schema import (
    BancoQuestoesFiltrosResponse,
    BancoQuestoesListasResponse,
    GerarListaIAResponse,
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
