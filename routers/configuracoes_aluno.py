from fastapi import APIRouter, HTTPException, Depends
from database import supabase, supabase_admin
from utils.autenticacao import pegar_usuario_atual
from utils.validacao import validar_senha_forte
from services import dados_ia_service
from schemas.configuracoes_aluno_schema import (
    ConfiguracoesAlunoResponse,
    PatchNotificacaoAlunoPayload,
    PatchNotificacaoAlunoResponse,
    PatchMetasAlunoPayload,
    ConfiguracoesAlunoMetas,
    PatchAparenciaAlunoPayload,
    PatchAparenciaAlunoResponse,
    PatchPerfilAlunoPayload,
    ConfiguracoesAlunoPerfil,
    AlterarSenhaAlunoPayload,
    AlterarSenhaAlunoResponse,
    DadosIAResponse,
    PatchDadosIAPayload,
    PatchDadosIAResponse,
)

router = APIRouter(
    prefix='/aluno/configuracoes',
    tags=['Aluno - Configurações']
)

NOTIFICACOES_CATALOGO = [
    {
        "id": "lembrete-diario",
        "label": "Lembrete diário de estudos",
        "description": "Receba um lembrete todo dia",
        "coluna": "lembrete_estudo_ativo",
    },
    {
        "id": "alerta-ofensiva",
        "label": "Alerta de ofensiva",
        "description": "Avise quando eu estiver perto de perder a ofensiva",
        "coluna": "alerta_ofensiva_ativo",
    },
    {
        "id": "novas-conquistas",
        "label": "Novas conquistas",
        "description": "Avise quando eu desbloquear uma conquista",
        "coluna": "notificacao_conquistas_ativa",
    },
    {
        "id": "novidades",
        "label": "Novidades do AdaptAI",
        "description": "Novidades e atualizações da plataforma",
        "coluna": "novidades_adaptai_ativo",
    },
]

COLUNA_POR_ID_NOTIFICACAO = {item["id"]: item["coluna"] for item in NOTIFICACOES_CATALOGO}

OBJETIVO_LABEL = {
    "melhorar_nota": "Melhorar minha nota",
    "passar_publica": "Passar em universidade pública",
    "estudar_do_zero": "Estudar do zero",
    "revisar_conteudos": "Revisar conteúdos",
    "treinar_redacao": "Treinar redação",
}

OBJETIVO_LABEL_PARA_ENUM = {label: enum for enum, label in OBJETIVO_LABEL.items()}


def formatar_tempo_estudo(minutos: int | None) -> str:
    if not minutos:
        return "0min"

    horas = minutos // 60
    restante = minutos % 60

    if horas and restante:
        return f"{horas}h{restante:02d}"
    if horas:
        return f"{horas}h"
    return f"{restante}min"


def parsear_tempo_estudo(texto: str) -> int:
    texto = texto.strip().lower()

    if "h" in texto:
        partes = texto.split("h")
        horas = int(partes[0]) if partes[0] else 0
        minutos = int(partes[1]) if len(partes) > 1 and partes[1].replace("min", "") else 0
        return horas * 60 + minutos

    if "min" in texto:
        return int(texto.replace("min", ""))

    if texto.isdigit():
        return int(texto)

    raise HTTPException(status_code=422, detail="Formato de tempo de estudo inválido")


def buscar_ou_criar_configuracoes(usuario_id: str):
    resposta = (
        supabase_admin.table("configuracoes_usuario")
        .select("*")
        .eq("usuario_id", usuario_id)
        .limit(1)
        .execute()
    )

    if resposta.data:
        return resposta.data[0]

    nova = (
        supabase_admin.table("configuracoes_usuario")
        .insert({"usuario_id": usuario_id})
        .execute()
    )
    return nova.data[0]


def montar_perfil(usuario_atual, usuario_id: str):
    perfil = (
        supabase_admin.table("perfis")
        .select("nome, escola_nome")
        .eq("id", usuario_id)
        .limit(1)
        .execute()
        .data
    )

    if not perfil:
        raise HTTPException(status_code=404, detail="Perfil não encontrado")

    estatisticas = (
        supabase_admin.table("estatisticas_usuario")
        .select("nivel, xp_total")
        .eq("usuario_id", usuario_id)
        .limit(1)
        .execute()
        .data
    )

    preferencias = (
        supabase_admin.table("preferencias_aluno")
        .select("ano_alvo")
        .eq("usuario_id", usuario_id)
        .limit(1)
        .execute()
        .data
    )

    nivel = estatisticas[0]["nivel"] if estatisticas else 1
    xp_total = estatisticas[0]["xp_total"] if estatisticas else 0
    ano_enem = str(preferencias[0]["ano_alvo"]) if preferencias and preferencias[0]["ano_alvo"] else ""

    return {
        "nome": perfil[0]["nome"],
        "email": usuario_atual.email or "",
        "nivel": nivel,
        "xp_total": xp_total,
        "escola": perfil[0]["escola_nome"] or "",
        "ano_enem": ano_enem,
    }


def montar_notificacoes(configuracoes: dict):
    return [
        {
            "id": item["id"],
            "label": item["label"],
            "description": item["description"],
            "enabled": bool(configuracoes.get(item["coluna"], False)),
        }
        for item in NOTIFICACOES_CATALOGO
    ]


def montar_metas(usuario_id: str):
    preferencias = (
        supabase_admin.table("preferencias_aluno")
        .select("objetivo_principal, minutos_estudo_dia, nota_alvo")
        .eq("usuario_id", usuario_id)
        .limit(1)
        .execute()
        .data
    )

    if not preferencias:
        return {"objetivo": "", "tempo_estudo": "0min", "nota_alvo": ""}

    registro = preferencias[0]
    objetivo = OBJETIVO_LABEL.get(registro["objetivo_principal"], "") if registro["objetivo_principal"] else ""
    nota_alvo = str(registro["nota_alvo"]) if registro["nota_alvo"] is not None else ""

    return {
        "objetivo": objetivo,
        "tempo_estudo": formatar_tempo_estudo(registro["minutos_estudo_dia"]),
        "nota_alvo": nota_alvo,
    }


def montar_aparencia(configuracoes: dict):
    return {"tema": configuracoes.get("tema") or "sistema"}


@router.get('', response_model=ConfiguracoesAlunoResponse)
def obter_configuracoes(usuario_atual=Depends(pegar_usuario_atual)):
    try:
        id_usuario = str(usuario_atual.id)
        configuracoes = buscar_ou_criar_configuracoes(id_usuario)

        return {
            "perfil": montar_perfil(usuario_atual, id_usuario),
            "notificacoes": montar_notificacoes(configuracoes),
            "aparencia": montar_aparencia(configuracoes),
        }

    except HTTPException:
        raise

    except Exception as erro:
        print(f"Erro ao obter configurações do aluno: {erro}")

        raise HTTPException(
            status_code=500,
            detail="Erro ao obter configurações do aluno"
        )


@router.patch('/notificacoes', response_model=PatchNotificacaoAlunoResponse)
def atualizar_notificacao(
    dados: PatchNotificacaoAlunoPayload,
    usuario_atual=Depends(pegar_usuario_atual)
):
    try:
        id_usuario = str(usuario_atual.id)
        coluna = COLUNA_POR_ID_NOTIFICACAO.get(dados.id)

        if not coluna:
            raise HTTPException(status_code=404, detail="Notificação não encontrada")

        buscar_ou_criar_configuracoes(id_usuario)

        supabase_admin.table("configuracoes_usuario").update({
            coluna: dados.enabled,
        }).eq("usuario_id", id_usuario).execute()

        return {
            "id": dados.id,
            "enabled": dados.enabled,
        }

    except HTTPException:
        raise

    except Exception as erro:
        print(f"Erro ao atualizar notificação do aluno: {erro}")

        raise HTTPException(
            status_code=500,
            detail="Erro ao atualizar notificação do aluno"
        )


@router.patch('/metas', response_model=ConfiguracoesAlunoMetas)
def atualizar_metas(
    dados: PatchMetasAlunoPayload,
    usuario_atual=Depends(pegar_usuario_atual)
):
    try:
        id_usuario = str(usuario_atual.id)
        alteracoes = dados.model_dump(exclude_unset=True, exclude_none=True)

        if not alteracoes:
            raise HTTPException(status_code=422, detail="Nenhum campo foi enviado")

        atualizacao = {}

        if "objetivo" in alteracoes:
            objetivo_enum = OBJETIVO_LABEL_PARA_ENUM.get(alteracoes["objetivo"])
            if not objetivo_enum:
                raise HTTPException(status_code=422, detail="Objetivo inválido")
            atualizacao["objetivo_principal"] = objetivo_enum

        if "tempo_estudo" in alteracoes:
            atualizacao["minutos_estudo_dia"] = parsear_tempo_estudo(alteracoes["tempo_estudo"])

        if "nota_alvo" in alteracoes:
            try:
                nota_alvo = int(alteracoes["nota_alvo"])
            except ValueError:
                raise HTTPException(status_code=422, detail="Nota alvo inválida")

            if nota_alvo < 0 or nota_alvo > 1000:
                raise HTTPException(status_code=422, detail="Nota alvo deve estar entre 0 e 1000")

            atualizacao["nota_alvo"] = nota_alvo

        existente = (
            supabase_admin.table("preferencias_aluno")
            .select("usuario_id")
            .eq("usuario_id", id_usuario)
            .limit(1)
            .execute()
            .data
        )

        if existente:
            supabase_admin.table("preferencias_aluno").update(
                atualizacao
            ).eq("usuario_id", id_usuario).execute()
        else:
            supabase_admin.table("preferencias_aluno").insert({
                "usuario_id": id_usuario,
                **atualizacao,
            }).execute()

        return montar_metas(id_usuario)

    except HTTPException:
        raise

    except Exception as erro:
        print(f"Erro ao atualizar metas do aluno: {erro}")

        raise HTTPException(
            status_code=500,
            detail="Erro ao atualizar metas do aluno"
        )


@router.patch('/aparencia', response_model=PatchAparenciaAlunoResponse)
def atualizar_aparencia(
    dados: PatchAparenciaAlunoPayload,
    usuario_atual=Depends(pegar_usuario_atual)
):
    try:
        id_usuario = str(usuario_atual.id)

        buscar_ou_criar_configuracoes(id_usuario)

        supabase_admin.table("configuracoes_usuario").update({
            "tema": dados.tema,
        }).eq("usuario_id", id_usuario).execute()

        return {"tema": dados.tema}

    except HTTPException:
        raise

    except Exception as erro:
        print(f"Erro ao atualizar aparência do aluno: {erro}")

        raise HTTPException(
            status_code=500,
            detail="Erro ao atualizar aparência do aluno"
        )


@router.patch('/perfil', response_model=ConfiguracoesAlunoPerfil)
def atualizar_perfil(
    dados: PatchPerfilAlunoPayload,
    usuario_atual=Depends(pegar_usuario_atual)
):
    try:
        id_usuario = str(usuario_atual.id)
        nome = dados.nome.strip()

        if not nome:
            raise HTTPException(status_code=400, detail="Nome não pode ser vazio")

        ano_enem = (dados.ano_enem or "").strip()
        if ano_enem and not ano_enem.isdigit():
            raise HTTPException(status_code=400, detail="Ano do ENEM inválido")

        supabase_admin.table("perfis").update({
            "nome": nome,
            "escola_nome": (dados.escola or "").strip() or None,
        }).eq("id", id_usuario).execute()

        if ano_enem:
            existente = (
                supabase_admin.table("preferencias_aluno")
                .select("usuario_id")
                .eq("usuario_id", id_usuario)
                .limit(1)
                .execute()
                .data
            )

            if existente:
                supabase_admin.table("preferencias_aluno").update({
                    "ano_alvo": int(ano_enem),
                }).eq("usuario_id", id_usuario).execute()
            else:
                supabase_admin.table("preferencias_aluno").insert({
                    "usuario_id": id_usuario,
                    "ano_alvo": int(ano_enem),
                }).execute()

        return montar_perfil(usuario_atual, id_usuario)

    except HTTPException:
        raise

    except Exception as erro:
        print(f"Erro ao atualizar perfil do aluno: {erro}")

        raise HTTPException(
            status_code=500,
            detail="Erro ao atualizar perfil do aluno"
        )


@router.post('/senha', response_model=AlterarSenhaAlunoResponse)
def alterar_senha(
    dados: AlterarSenhaAlunoPayload,
    usuario_atual=Depends(pegar_usuario_atual)
):
    try:
        senha_valida, mensagem_senha = validar_senha_forte(dados.nova_senha)
        if not senha_valida:
            raise HTTPException(status_code=400, detail=mensagem_senha)

        email = usuario_atual.email
        if not email:
            raise HTTPException(status_code=400, detail="Usuário sem email associado")

        try:
            supabase.auth.sign_in_with_password({
                "email": email,
                "password": dados.senha_atual,
            })
        except Exception:
            raise HTTPException(status_code=403, detail="Senha atual incorreta")

        supabase_admin.auth.admin.update_user_by_id(
            str(usuario_atual.id),
            {"password": dados.nova_senha},
        )

        # Troca de senha invalida sessões antigas emitidas antes dela.
        try:
            supabase_admin.auth.admin.sign_out(str(usuario_atual.id), scope="others")
        except Exception as erro_sessao:
            print(f"Erro ao invalidar sessões antigas após troca de senha: {erro_sessao}")

        return {"sucesso": True}

    except HTTPException:
        raise

    except Exception as erro:
        print(f"Erro ao alterar senha do aluno: {erro}")

        raise HTTPException(
            status_code=500,
            detail="Erro ao alterar senha do aluno"
        )


@router.get('/dados-ia', response_model=DadosIAResponse)
def obter_dados_ia(usuario_atual=Depends(pegar_usuario_atual)):
    try:
        id_usuario = str(usuario_atual.id)
        return dados_ia_service.montar_dados_ia(id_usuario)

    except HTTPException:
        raise

    except Exception as erro:
        print(f"Erro ao obter dados de IA do aluno: {erro}")

        raise HTTPException(
            status_code=500,
            detail="Erro ao obter dados de IA do aluno"
        )


@router.patch('/dados-ia', response_model=PatchDadosIAResponse)
def atualizar_dados_ia(
    dados: PatchDadosIAPayload,
    usuario_atual=Depends(pegar_usuario_atual)
):
    try:
        if dados.id not in dados_ia_service.IDS_VALIDOS:
            raise HTTPException(status_code=404, detail="Categoria de dados não encontrada")

        id_usuario = str(usuario_atual.id)
        dados_ia_service.atualizar_preferencia(id_usuario, dados.id, dados.utilizado)

        return {"id": dados.id, "utilizado": dados.utilizado}

    except HTTPException:
        raise

    except Exception as erro:
        print(f"Erro ao atualizar preferência de dados de IA do aluno: {erro}")

        raise HTTPException(
            status_code=500,
            detail="Erro ao atualizar preferência de dados de IA do aluno"
        )
