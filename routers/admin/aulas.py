from fastapi import APIRouter, HTTPException, Depends, Query
from database import supabase_admin
from uuid import UUID, uuid4
from datetime import datetime, timezone
from utils.autenticacao import exigir_administrador
from schemas.aulas_schema import AulaCriar, AulaEditar
from utils.textos import gerar_slug

router = APIRouter(
    prefix='/admin/aulas',
    tags=['Admin - Aulas'],
    dependencies=[Depends(exigir_administrador)]
)


# Busca em aulas_tipos e devolve os mapas nome->id e id->nome
def obter_mapa_tipos():
    resposta = supabase_admin.table("aulas_tipos").select("id, nome").execute()
    tipos = resposta.data or []
    return {tipo["nome"]: tipo["id"] for tipo in tipos}, {tipo["id"]: tipo["nome"] for tipo in tipos}


# Monta a aula com seus conteúdos, já resolvendo o texto ou vídeo de cada um
def montar_aula(aula_id: UUID):
    resposta = (
        supabase_admin.table("aulas")
        .select("*")
        .eq("id", str(aula_id))
        .limit(1)
        .execute()
    )

    if not resposta.data:
        return None

    aula = resposta.data[0]
    _, ids_para_nome = obter_mapa_tipos()

    conteudos = (
        supabase_admin.table("aulas_conteudo")
        .select("*")
        .eq("aula_id", str(aula_id))
        .order("ordem")
        .execute()
        .data or []
    )

    ids_conteudo = [conteudo["id"] for conteudo in conteudos]
    textos = []
    videos = []

    if ids_conteudo:
        textos = (
            supabase_admin.table("aulas_texto")
            .select("*")
            .in_("aulas_conteudo_id", ids_conteudo)
            .execute()
            .data or []
        )
        videos = (
            supabase_admin.table("aulas_video")
            .select("*")
            .in_("aulas_conteudo_id", ids_conteudo)
            .execute()
            .data or []
        )

    for conteudo in conteudos:
        conteudo["tipo"] = ids_para_nome.get(conteudo["id_tipo"])
        conteudo["texto"] = next((t for t in textos if t["aulas_conteudo_id"] == conteudo["id"]), None)
        conteudo["video"] = next((v for v in videos if v["aulas_conteudo_id"] == conteudo["id"]), None)

    aula["conteudos"] = conteudos

    return aula


# Cria os conteúdos (aulas_conteudo + aulas_texto/aulas_video) de uma aula
def salvar_conteudos(aula_id: UUID, conteudos: list):
    nomes_para_id, _ = obter_mapa_tipos()
    agora = datetime.now(timezone.utc).isoformat()

    for conteudo in conteudos:
        id_tipo = nomes_para_id.get(conteudo.tipo)

        if not id_tipo:
            raise HTTPException(
                status_code=400,
                detail=f"Tipo de conteúdo '{conteudo.tipo}' não está cadastrado"
            )

        conteudo_id = str(uuid4())

        supabase_admin.table("aulas_conteudo").insert({
            "id": conteudo_id,
            "aula_id": str(aula_id),
            "ordem": conteudo.ordem,
            "id_tipo": id_tipo,
            "atualizado_em": agora,
            "ativo": conteudo.ativo,
            "duracao": conteudo.duracao,
        }).execute()

        if conteudo.tipo == "texto":
            supabase_admin.table("aulas_texto").insert({
                "atualizado_em": agora,
                "titulo": conteudo.texto.titulo,
                "descricao": conteudo.texto.descricao,
                "aulas_conteudo_id": conteudo_id,
            }).execute()
        else:
            supabase_admin.table("aulas_video").insert({
                "atualizado_em": agora,
                "titulo": conteudo.video.titulo,
                "video_link": conteudo.video.video_link,
                "descricao": conteudo.video.descricao,
                "aulas_conteudo_id": conteudo_id,
            }).execute()


# Remove todos os conteúdos (e seus textos/vídeos) de uma aula
def excluir_conteudos(aula_id: UUID):
    ids_conteudo = [c["id"] for c in (
        supabase_admin.table("aulas_conteudo")
        .select("id")
        .eq("aula_id", str(aula_id))
        .execute()
        .data or []
    )]

    if ids_conteudo:
        supabase_admin.table("aulas_texto").delete().in_("aulas_conteudo_id", ids_conteudo).execute()
        supabase_admin.table("aulas_video").delete().in_("aulas_conteudo_id", ids_conteudo).execute()
        supabase_admin.table("aulas_conteudo").delete().in_("id", ids_conteudo).execute()


# Lista as aulas de uma matéria
@router.get("/por-materia/{materia_id}")
def listar_aulas_por_materia(materia_id: UUID):
    try:
        resposta = (
            supabase_admin.table("aulas")
            .select("*")
            .eq("materia_id", str(materia_id))
            .order("ordem")
            .order("titulo")
            .execute()
        )

        aulas = resposta.data or []

        return {
            "sucesso": True,
            "total_aulas": len(aulas),
            "aulas": aulas
        }

    except Exception as erro:
        print(f"Erro ao listar aulas da matéria: {erro}")
        raise HTTPException(
            status_code=500,
            detail="Erro ao listar aulas da matéria"
        )


# Busca uma aula com todos os seus conteúdos
@router.get("/{aula_id}")
def buscar_aula(aula_id: UUID):
    try:
        aula = montar_aula(aula_id)

        if not aula:
            raise HTTPException(
                status_code=404,
                detail="Aula não encontrada"
            )

        return {
            "sucesso": True,
            "aula": aula
        }

    except HTTPException:
        raise

    except Exception as erro:
        print(f"Erro ao buscar aula: {erro}")
        raise HTTPException(
            status_code=500,
            detail="Erro ao buscar aula"
        )


# Cria a aula e, se enviados, os conteúdos já junto
@router.post('')
def criar_aula(dados: AulaCriar):
    try:
        resposta_materia = (
            supabase_admin.table("materias")
            .select("id")
            .eq("id", str(dados.materia_id))
            .limit(1)
            .execute()
        )

        if not resposta_materia.data:
            raise HTTPException(
                status_code=404,
                detail="Matéria não encontrada"
            )

        titulo = dados.titulo.strip()
        slug = gerar_slug(titulo)

        resposta = (
            supabase_admin.table("aulas")
            .select("id")
            .eq("materia_id", str(dados.materia_id))
            .eq("slug", slug)
            .limit(1)
            .execute()
        )

        if resposta.data:
            raise HTTPException(
                status_code=409,
                detail="Já existe uma aula com esse título nessa matéria"
            )

        nova_aula = dados.model_dump(exclude={"conteudos"})
        nova_aula["materia_id"] = str(dados.materia_id)
        nova_aula["topico_id"] = str(dados.topico_id) if dados.topico_id else None
        nova_aula["titulo"] = titulo
        nova_aula["slug"] = slug

        resposta = (
            supabase_admin.table("aulas")
            .insert(nova_aula)
            .execute()
        )

        if not resposta.data:
            raise HTTPException(
                status_code=500,
                detail="Não foi possível criar a aula"
            )

        aula_id = resposta.data[0]["id"]

        if dados.conteudos:
            salvar_conteudos(aula_id, dados.conteudos)

        return {
            "sucesso": True,
            "mensagem": "Aula criada com sucesso",
            "aula": montar_aula(aula_id)
        }

    except HTTPException:
        raise

    except Exception as erro:
        print(f"Erro ao criar aula: {erro}")
        raise HTTPException(
            status_code=500,
            detail="Erro ao criar aula"
        )


# Atualiza a aula; se vier "conteudos", substitui todos os conteúdos existentes pelos enviados
@router.patch('/{aula_id}')
def editar_aula(aula_id: UUID, dados: AulaEditar):
    try:
        alteracoes = dados.model_dump(exclude_unset=True, exclude={"conteudos"})

        if not alteracoes and dados.conteudos is None:
            raise HTTPException(
                status_code=400,
                detail="Nenhuma alteração foi enviada"
            )

        if "materia_id" in alteracoes:
            alteracoes["materia_id"] = str(alteracoes["materia_id"])

        if "topico_id" in alteracoes and alteracoes["topico_id"] is not None:
            alteracoes["topico_id"] = str(alteracoes["topico_id"])

        if "titulo" in alteracoes:
            alteracoes["titulo"] = alteracoes["titulo"].strip()
            alteracoes["slug"] = gerar_slug(alteracoes["titulo"])

        if alteracoes:
            resposta = (
                supabase_admin.table("aulas")
                .update(alteracoes)
                .eq("id", str(aula_id))
                .execute()
            )

            if not resposta.data:
                raise HTTPException(
                    status_code=404,
                    detail="Aula não encontrada"
                )

        if dados.conteudos is not None:
            excluir_conteudos(aula_id)
            salvar_conteudos(aula_id, dados.conteudos)

        return {
            "sucesso": True,
            "mensagem": "Aula atualizada com sucesso",
            "aula": montar_aula(aula_id)
        }

    except HTTPException:
        raise

    except Exception as erro:
        print(f"Erro ao atualizar aula: {erro}")
        raise HTTPException(
            status_code=500,
            detail="Erro ao atualizar aula"
        )


# Exclui a aula e todos os seus conteúdos
@router.delete('/{aula_id}')
def excluir_aula(aula_id: UUID):
    try:
        resposta = (
            supabase_admin.table("aulas")
            .select("id")
            .eq("id", str(aula_id))
            .limit(1)
            .execute()
        )

        if not resposta.data:
            raise HTTPException(
                status_code=404,
                detail="Aula não encontrada"
            )

        excluir_conteudos(aula_id)

        supabase_admin.table("aulas").delete().eq("id", str(aula_id)).execute()

        return {
            "sucesso": True,
            "mensagem": "Aula excluída com sucesso"
        }

    except HTTPException:
        raise

    except Exception as erro:
        print(f"Erro ao excluir aula: {erro}")
        raise HTTPException(
            status_code=500,
            detail="Erro ao excluir aula"
        )
