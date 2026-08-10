"""Calcula o valor atual de cada `tipo_condicao` de conquista a partir
dos dados reais do aluno. Cada função recebe (usuario_id, conquista) e
devolve um número comparável a `conquista["valor_condicao"]`.

Nenhuma função aqui decide se a conquista foi desbloqueada — isso é
responsabilidade de conquistas_service. Aqui só se mede.
"""

from database import supabase_admin

# Abaixo desse número de questões respondidas na matéria, o percentual de
# acerto não é uma amostra confiável (1 questão certa = 100%). Configurável
# em um único lugar — nada mais no projeto deve hardcodar esse valor.
MIN_QUESTOES_CONQUISTA_PERCENTUAL = 20

# Slugs de listas de questões que contam como "revisão" quando respondidas
# corretamente (usa o enum tipo_lista já existente em listas_questoes).
TIPOS_LISTA_REVISAO = ("questoes_erradas", "revisao")


def _contar(tabela: str, **filtros) -> int:
    consulta = supabase_admin.table(tabela).select("id", count="exact")
    for campo, valor in filtros.items():
        consulta = consulta.eq(campo, valor)
    return consulta.execute().count or 0


def dias_estudo(usuario_id: str, conquista: dict) -> int:
    return _maior_ofensiva(usuario_id)


def ofensiva_dias(usuario_id: str, conquista: dict) -> int:
    return _maior_ofensiva(usuario_id)


def _maior_ofensiva(usuario_id: str) -> int:
    resposta = (
        supabase_admin.table("estatisticas_usuario")
        .select("maior_ofensiva_dias")
        .eq("usuario_id", usuario_id)
        .limit(1)
        .execute()
        .data
    )
    return resposta[0]["maior_ofensiva_dias"] if resposta else 0


def questoes_respondidas(usuario_id: str, conquista: dict) -> int:
    return _contar("respostas_lista_questoes_aluno", usuario_id=usuario_id)


def redacoes_enviadas(usuario_id: str, conquista: dict) -> int:
    resposta = (
        supabase_admin.table("redacoes_enviadas")
        .select("id", count="exact")
        .eq("usuario_id", usuario_id)
        .neq("status", "rascunho")
        .execute()
    )
    return resposta.count or 0


def simulados_completos(usuario_id: str, conquista: dict) -> int:
    return _contar("sessoes_simulado", usuario_id=usuario_id, status="concluido")


def nota_redacao(usuario_id: str, conquista: dict) -> int:
    notas = (
        supabase_admin.table("redacoes_enviadas")
        .select("nota_total")
        .eq("usuario_id", usuario_id)
        .eq("status", "corrigida")
        .execute()
        .data or []
    )
    valores = [n["nota_total"] for n in notas if n["nota_total"] is not None]
    return max(valores) if valores else 0


def minutos_estudo_dia(usuario_id: str, conquista: dict) -> int:
    dias = (
        supabase_admin.table("atividade_diaria")
        .select("minutos_estudo")
        .eq("usuario_id", usuario_id)
        .execute()
        .data or []
    )
    return max((d["minutos_estudo"] for d in dias), default=0)


def percentual_acerto_materia(usuario_id: str, conquista: dict) -> int:
    materia_id = conquista.get("materia_id")
    if not materia_id:
        return 0

    ids_questoes = [
        q["id"] for q in
        supabase_admin.table("questoes").select("id").eq("materia_id", materia_id).execute().data or []
    ]
    if not ids_questoes:
        return 0

    respostas = (
        supabase_admin.table("respostas_lista_questoes_aluno")
        .select("correta")
        .eq("usuario_id", usuario_id)
        .in_("questao_id", ids_questoes)
        .execute()
        .data or []
    )

    total = len(respostas)
    if total < MIN_QUESTOES_CONQUISTA_PERCENTUAL:
        return 0

    corretas = sum(1 for r in respostas if r["correta"])
    return round((corretas / total) * 100)


def questoes_erradas_revisadas(usuario_id: str, conquista: dict) -> int:
    ids_listas_revisao = [
        lista["id"] for lista in
        supabase_admin.table("listas_questoes")
        .select("id")
        .in_("tipo_lista", TIPOS_LISTA_REVISAO)
        .execute()
        .data or []
    ]
    if not ids_listas_revisao:
        return 0

    resposta = (
        supabase_admin.table("respostas_lista_questoes_aluno")
        .select("id", count="exact")
        .eq("usuario_id", usuario_id)
        .eq("correta", True)
        .in_("lista_questoes_id", ids_listas_revisao)
        .execute()
    )
    return resposta.count or 0


MEDIDORES = {
    "dias_estudo": dias_estudo,
    "ofensiva_dias": ofensiva_dias,
    "questoes_respondidas": questoes_respondidas,
    "redacoes_enviadas": redacoes_enviadas,
    "simulados_completos": simulados_completos,
    "nota_redacao": nota_redacao,
    "minutos_estudo_dia": minutos_estudo_dia,
    "percentual_acerto_materia": percentual_acerto_materia,
    "questoes_erradas_revisadas": questoes_erradas_revisadas,
}
