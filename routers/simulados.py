from fastapi import APIRouter, HTTPException, Depends
from database import supabase_admin
from utils.autenticacao import pegar_usuario_atual
from schemas.simulados_schema import SimuladosResponse

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
        .eq("status", "concluido")
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
        .select("slug, titulo, descricao, tipo_modelo, total_questoes, duracao_minutos")
        .eq("ativo", True)
        .execute()
        .data or []
    )

    if not modelos:
        return []

    catalogo = []
    for modelo in modelos:
        icone, icone_cor = ICONE_POR_TIPO_MODELO.get(modelo["tipo_modelo"], ("📋", "gray"))
        tag, tag_cor = TAG_POR_TIPO_MODELO.get(modelo["tipo_modelo"], (modelo["tipo_modelo"], "gray"))

        descricao = modelo.get("descricao")
        if not descricao:
            total_questoes = modelo.get("total_questoes") or 0
            descricao = f"{total_questoes} questões"

        catalogo.append({
            "slug": modelo["slug"],
            "titulo": modelo["titulo"],
            "descricao": descricao,
            "icone": icone,
            "icone_cor": icone_cor,
            "tag": tag,
            "tag_cor": tag_cor,
            "duracao": formatar_duracao(modelo.get("duracao_minutos")),
        })

    return catalogo


def montar_historico(usuario_id: str):
    sessoes = (
        supabase_admin.table("sessoes_simulado")
        .select("id, concluido_em, duracao_segundos, nota_estimada, percentual_acerto, modelo_simulado_id")
        .eq("usuario_id", usuario_id)
        .eq("status", "concluido")
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
