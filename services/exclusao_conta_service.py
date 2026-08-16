from database import supabase_admin

# Tabelas com FK direta usuario_id -> perfis(id) sem outras tabelas
# dependendo delas, seguras para apagar diretamente por usuario_id.
_TABELAS_SIMPLES = [
    "conceitos_aula_usuario",
    "progresso_aulas_usuario",
    "metas_mensais_usuario",
    "atividade_diaria",
    "dificuldades_aluno_materias",
    "questoes_favoritas",
    "tentativas_questoes",
    "sessoes_simulado",
    "progresso_lista_questoes_aluno",
    "respostas_lista_questoes_aluno",
    "tentativas_lista_questoes",
    "redacoes_enviadas",
    "conquistas_usuario",
    "progresso_missoes_usuario",
    "notificacoes",
    "mensagens_ia",  # via conversas_ia, mas apagado antes por segurança
    "conversas_ia",
    "preferencias_dados_ia",
    "preferencias_aluno",
    "estatisticas_usuario",
    "configuracoes_usuario",
    "email_verificacoes",
]


def excluir_conta(usuario_id: str) -> None:
    # Planos de estudo têm sessões (planos_estudo_sessoes) filhas por
    # plano_estudo_id, não por usuario_id — precisam ser resolvidas antes.
    planos = (
        supabase_admin.table("planos_estudo")
        .select("id")
        .eq("usuario_id", usuario_id)
        .execute()
        .data
    ) or []
    ids_planos = [p["id"] for p in planos]

    if ids_planos:
        supabase_admin.table("planos_estudo_sessoes").delete().in_(
            "plano_estudo_id", ids_planos
        ).execute()

    supabase_admin.table("tarefas_estudo").delete().eq("usuario_id", usuario_id).execute()

    if ids_planos:
        supabase_admin.table("planos_estudo").delete().in_("id", ids_planos).execute()

    # Listas de questões criadas pelo próprio aluno (usuario_id é nulo em
    # listas do banco oficial/admin, então esse filtro não afeta catálogo).
    listas = (
        supabase_admin.table("listas_questoes")
        .select("id")
        .eq("usuario_id", usuario_id)
        .execute()
        .data
    ) or []
    ids_listas = [l["id"] for l in listas]

    if ids_listas:
        supabase_admin.table("itens_lista_questoes").delete().in_(
            "lista_questoes_id", ids_listas
        ).execute()
        supabase_admin.table("tentativas_lista_questoes").delete().in_(
            "lista_questoes_id", ids_listas
        ).execute()
        supabase_admin.table("listas_questoes").delete().in_("id", ids_listas).execute()

    for tabela in _TABELAS_SIMPLES:
        try:
            supabase_admin.table(tabela).delete().eq("usuario_id", usuario_id).execute()
        except Exception as erro:
            print(f"Erro ao limpar tabela {tabela} na exclusão de conta {usuario_id}: {erro}")

    supabase_admin.table("recuperacao_senha_tokens").delete().eq(
        "user_id", usuario_id
    ).execute()

    supabase_admin.table("perfis").delete().eq("id", usuario_id).execute()

    supabase_admin.auth.admin.delete_user(usuario_id)
