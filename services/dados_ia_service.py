from database import supabase_admin

# Catálogo fixo de categorias de dados que a IA pode considerar ao gerar
# recomendações/insights para o aluno. Cada entrada aqui precisa ter uma
# regra correspondente em `_gerar_insights` (ou nenhuma, se ainda não há
# geração automática para aquela categoria).
CATALOGO_DADOS_IA = [
    {
        "id": "desempenho-matematica",
        "nome": "Desempenho em Matemática",
        "descricao": "Resultados em questões e simulados de Matemática",
        "categoria": "desempenho",
    },
    {
        "id": "questoes-erradas",
        "nome": "Questões erradas",
        "descricao": "Histórico de questões respondidas incorretamente",
        "categoria": "questoes",
    },
    {
        "id": "tempo-estudo",
        "nome": "Tempo de estudo",
        "descricao": "Duração e frequência das suas sessões de estudo",
        "categoria": "habitos",
    },
    {
        "id": "redacoes",
        "nome": "Histórico de redações",
        "descricao": "Correções e evolução das suas redações",
        "categoria": "redacao",
    },
]

IDS_VALIDOS = {item["id"] for item in CATALOGO_DADOS_IA}


def buscar_preferencias(usuario_id: str) -> dict:
    registros = (
        supabase_admin.table("preferencias_dados_ia")
        .select("categoria_id, utilizado")
        .eq("usuario_id", usuario_id)
        .execute()
        .data
    ) or []

    preferencias = {item["categoria_id"]: item["utilizado"] for item in registros}
    # Categoria sem preferência salva ainda = habilitada por padrão.
    return {item["id"]: preferencias.get(item["id"], True) for item in CATALOGO_DADOS_IA}


def categoria_habilitada(usuario_id: str, categoria_id: str) -> bool:
    return buscar_preferencias(usuario_id).get(categoria_id, True)


def atualizar_preferencia(usuario_id: str, categoria_id: str, utilizado: bool) -> None:
    supabase_admin.table("preferencias_dados_ia").upsert({
        "usuario_id": usuario_id,
        "categoria_id": categoria_id,
        "utilizado": utilizado,
    }).execute()


def _insight_desempenho(usuario_id: str) -> dict | None:
    dificuldades = (
        supabase_admin.table("dificuldades_aluno_materias")
        .select("materia_id, materias(nome)")
        .eq("usuario_id", usuario_id)
        .limit(1)
        .execute()
        .data
    )

    if not dificuldades or not dificuldades[0].get("materias"):
        return None

    materia_nome = dificuldades[0]["materias"]["nome"]

    return {
        "id": "insight-desempenho",
        "titulo": f"Maior dificuldade em {materia_nome}",
        "descricao": f"Você apresenta maior dificuldade em {materia_nome} em relação às demais matérias.",
        "materia": materia_nome,
        "tipo": "dificuldade",
    }


def _insight_questoes_erradas(usuario_id: str) -> dict | None:
    tentativas = (
        supabase_admin.table("tentativas_questoes")
        .select("acertou, questoes(materia_id, materias(nome))")
        .eq("usuario_id", usuario_id)
        .execute()
        .data
    ) or []

    if len(tentativas) < 5:
        return None

    por_materia: dict[str, dict] = {}
    for tentativa in tentativas:
        questao = tentativa.get("questoes") or {}
        materia = questao.get("materias") or {}
        nome = materia.get("nome")
        if not nome:
            continue

        registro = por_materia.setdefault(nome, {"total": 0, "erros": 0})
        registro["total"] += 1
        if not tentativa.get("acertou"):
            registro["erros"] += 1

    pior_materia = None
    pior_taxa_erro = 0.0
    for nome, registro in por_materia.items():
        if registro["total"] < 5:
            continue
        taxa_erro = registro["erros"] / registro["total"]
        if taxa_erro > pior_taxa_erro:
            pior_taxa_erro = taxa_erro
            pior_materia = nome

    if not pior_materia or pior_taxa_erro < 0.5:
        return None

    return {
        "id": "insight-questoes-erradas",
        "titulo": f"Muitos erros em {pior_materia}",
        "descricao": f"Mais da metade das questões que você respondeu em {pior_materia} estão erradas. Vale reforçar esse conteúdo.",
        "materia": pior_materia,
        "tipo": "dificuldade",
    }


def _insight_tempo_estudo(usuario_id: str) -> dict | None:
    atividades = (
        supabase_admin.table("atividade_diaria")
        .select("minutos_estudo, tarefas_concluidas")
        .eq("usuario_id", usuario_id)
        .order("data_atividade", desc=True)
        .limit(14)
        .execute()
        .data
    ) or []

    total_tarefas = sum(a["tarefas_concluidas"] for a in atividades)
    total_minutos = sum(a["minutos_estudo"] for a in atividades)

    if total_tarefas < 5 or total_minutos == 0:
        return None

    media_minutos_por_tarefa = total_minutos / total_tarefas
    if media_minutos_por_tarefa >= 30:
        return None

    return {
        "id": "insight-tempo-estudo",
        "titulo": "Sessões curtas funcionam melhor",
        "descricao": "Seu desempenho aparece melhor quando você faz sessões de estudo menores e mais frequentes.",
        "materia": None,
        "tipo": "habito",
    }


def _insight_redacoes(usuario_id: str) -> dict | None:
    redacoes = (
        supabase_admin.table("redacoes_enviadas")
        .select("nota_total, corrigido_em")
        .eq("usuario_id", usuario_id)
        .eq("status", "corrigida")
        .order("corrigido_em", desc=False)
        .execute()
        .data
    ) or []

    redacoes = [r for r in redacoes if r["nota_total"] is not None]
    if len(redacoes) < 2:
        return None

    primeira_nota = redacoes[0]["nota_total"]
    ultima_nota = redacoes[-1]["nota_total"]

    if ultima_nota <= primeira_nota:
        return None

    return {
        "id": "insight-redacoes",
        "titulo": "Evolução nas redações",
        "descricao": f"Sua nota de redação subiu de {primeira_nota} para {ultima_nota} desde a primeira correção.",
        "materia": "Redação",
        "tipo": "evolucao",
    }


_GERADORES_POR_CATEGORIA = {
    "desempenho-matematica": _insight_desempenho,
    "questoes-erradas": _insight_questoes_erradas,
    "tempo-estudo": _insight_tempo_estudo,
    "redacoes": _insight_redacoes,
}


def montar_dados_ia(usuario_id: str) -> dict:
    preferencias = buscar_preferencias(usuario_id)

    dados = [
        {**item, "utilizado": preferencias[item["id"]]}
        for item in CATALOGO_DADOS_IA
    ]

    insights = []
    for categoria_id, gerador in _GERADORES_POR_CATEGORIA.items():
        if not preferencias.get(categoria_id, True):
            continue

        try:
            insight = gerador(usuario_id)
        except Exception as erro:
            print(f"Erro ao gerar insight de IA ({categoria_id}) para usuário {usuario_id}: {erro}")
            insight = None

        if insight:
            insights.append(insight)

    return {"dados": dados, "insights": insights}
