from fastapi import APIRouter, HTTPException, Depends, Query
from database import supabase_admin
from uuid import UUID
from utils.autenticacao import pegar_usuario_atual
from schemas.biblioteca_aulas_schema import BibliotecaAulasResponse, AulaBibliotecaDetalhe

router = APIRouter(
    prefix='/aluno/aulas',
    tags=['Aluno - Biblioteca de Aulas']
)

DIFICULDADE_LABEL = {
    "basico": "Básico",
    "medio": "Médio",
    "dificil": "Difícil",
}


# Busca em aulas_tipos e devolve o mapa id->nome
def obter_mapa_tipos():
    resposta = supabase_admin.table("aulas_tipos").select("id, nome").execute()
    return {tipo["id"]: tipo["nome"] for tipo in (resposta.data or [])}


@router.get('', response_model=BibliotecaAulasResponse)
def listar_aulas(
    categoria_id: UUID | None = Query(default=None),
    usuario_atual=Depends(pegar_usuario_atual)
):
    try:
        materias = (
            supabase_admin.table("materias")
            .select("id, nome, cor, icone")
            .eq("ativo", True)
            .order("ordem")
            .execute()
            .data or []
        )

        if categoria_id and not any(materia["id"] == str(categoria_id) for materia in materias):
            raise HTTPException(
                status_code=404,
                detail="Categoria não encontrada"
            )

        materias_por_id = {materia["id"]: materia for materia in materias}

        consulta = (
            supabase_admin.table("aulas")
            .select("id, slug, titulo, materia_id, dificuldade, mais_cobrado")
            .eq("ativo", True)
        )

        if categoria_id:
            consulta = consulta.eq("materia_id", str(categoria_id))

        aulas_banco = consulta.order("ordem").order("titulo").execute().data or []
        ids_aulas = [aula["id"] for aula in aulas_banco]

        conteudos = (
            supabase_admin.table("aulas_conteudo")
            .select("aula_id, duracao")
            .in_("aula_id", ids_aulas)
            .execute()
            .data or []
        ) if ids_aulas else []

        duracao_por_aula: dict[str, int] = {}
        for conteudo in conteudos:
            duracao_por_aula[conteudo["aula_id"]] = duracao_por_aula.get(conteudo["aula_id"], 0) + conteudo["duracao"]

        progresso_aluno = (
            supabase_admin.table("progresso_aulas_usuario")
            .select("aula_id, status, percentual_progresso")
            .eq("usuario_id", str(usuario_atual.id))
            .in_("aula_id", ids_aulas)
            .execute()
            .data or []
        ) if ids_aulas else []

        progresso_por_aula = {item["aula_id"]: item for item in progresso_aluno}

        aulas = []
        for aula in aulas_banco:
            materia = materias_por_id.get(aula["materia_id"])
            if not materia:
                continue

            progresso = progresso_por_aula.get(aula["id"])
            status = progresso["status"].replace("_", "-") if progresso else "nao-iniciada"
            percentual = int(progresso["percentual_progresso"]) if progresso else 0

            aulas.append({
                "id": aula["id"],
                "slug": aula["slug"],
                "titulo": aula["titulo"],
                "materia": materia["nome"],
                "materia_cor": materia["cor"],
                "icone": materia["icone"],
                "icone_cor": materia["cor"],
                "duracao_min": duracao_por_aula.get(aula["id"], 0),
                "dificuldade": DIFICULDADE_LABEL.get(aula["dificuldade"], aula["dificuldade"]),
                "progresso": percentual,
                "status": status,
                "destaque": bool(aula["mais_cobrado"]),
            })

        total_aulas = len(aulas)
        total_concluidas = sum(1 for aula in aulas if aula["status"] == "concluida")

        return {
            "total_aulas": total_aulas,
            "total_concluidas": total_concluidas,
            "subtitulo": f"{total_aulas} aulas disponíveis · {total_concluidas} concluídas",
            "categorias": [
                {"id": materia["id"], "nome": materia["nome"]}
                for materia in materias
            ],
            "aulas": aulas,
        }

    except HTTPException:
        raise

    except Exception as erro:
        print(f"Erro ao listar aulas: {erro}")

        raise HTTPException(
            status_code=500,
            detail="Erro ao listar aulas"
        )


@router.get('/{slug_ou_id}', response_model=AulaBibliotecaDetalhe)
def buscar_aula(
    slug_ou_id: str,
    usuario_atual=Depends(pegar_usuario_atual)
):
    try:
        consulta = supabase_admin.table("aulas").select(
            "id, slug, titulo, materia_id, dificuldade"
        )

        try:
            aula_id = UUID(slug_ou_id)
            consulta = consulta.eq("id", str(aula_id))
        except ValueError:
            consulta = consulta.eq("slug", slug_ou_id)

        resposta = consulta.limit(1).execute()

        if not resposta.data:
            raise HTTPException(
                status_code=404,
                detail="Aula não encontrada"
            )

        aula = resposta.data[0]

        materia = (
            supabase_admin.table("materias")
            .select("nome, cor")
            .eq("id", aula["materia_id"])
            .limit(1)
            .execute()
        )

        if not materia.data:
            raise HTTPException(
                status_code=404,
                detail="Aula não encontrada"
            )

        conteudos_banco = (
            supabase_admin.table("aulas_conteudo")
            .select("id, ordem, duracao, id_tipo")
            .eq("aula_id", aula["id"])
            .eq("ativo", True)
            .order("ordem")
            .execute()
            .data or []
        )

        ids_para_nome = obter_mapa_tipos()
        ids_conteudo = [conteudo["id"] for conteudo in conteudos_banco]

        textos = []
        videos = []

        if ids_conteudo:
            textos = (
                supabase_admin.table("aulas_texto")
                .select("aulas_conteudo_id, titulo, descricao")
                .in_("aulas_conteudo_id", ids_conteudo)
                .execute()
                .data or []
            )
            videos = (
                supabase_admin.table("aulas_video")
                .select("aulas_conteudo_id, titulo, descricao, video_link")
                .in_("aulas_conteudo_id", ids_conteudo)
                .execute()
                .data or []
            )

        conteudos = []
        for conteudo in conteudos_banco:
            tipo = ids_para_nome.get(conteudo["id_tipo"])

            if tipo == "texto":
                detalhe = next((t for t in textos if t["aulas_conteudo_id"] == conteudo["id"]), None)
            else:
                detalhe = next((v for v in videos if v["aulas_conteudo_id"] == conteudo["id"]), None)

            if not detalhe:
                continue

            conteudos.append({
                "tipo": tipo,
                "ordem": conteudo["ordem"],
                "duracao_min": conteudo["duracao"],
                "titulo": detalhe["titulo"],
                "descricao": detalhe["descricao"],
                "video_link": detalhe.get("video_link"),
            })

        progresso_resposta = (
            supabase_admin.table("progresso_aulas_usuario")
            .select("status, percentual_progresso")
            .eq("usuario_id", str(usuario_atual.id))
            .eq("aula_id", aula["id"])
            .limit(1)
            .execute()
        )

        progresso = progresso_resposta.data[0] if progresso_resposta.data else None
        status = progresso["status"].replace("_", "-") if progresso else "nao-iniciada"
        percentual = int(progresso["percentual_progresso"]) if progresso else 0

        return {
            "id": aula["id"],
            "slug": aula["slug"],
            "titulo": aula["titulo"],
            "materia": materia.data[0]["nome"],
            "materia_cor": materia.data[0]["cor"],
            "dificuldade": DIFICULDADE_LABEL.get(aula["dificuldade"], aula["dificuldade"]),
            "progresso": percentual,
            "status": status,
            "conteudos": conteudos,
        }

    except HTTPException:
        raise

    except Exception as erro:
        print(f"Erro ao buscar aula: {erro}")

        raise HTTPException(
            status_code=500,
            detail="Erro ao buscar aula"
        )
