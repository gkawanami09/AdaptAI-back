from services.gamificacao.conquistas_service import avaliar_conquistas, recalcular_conquistas_aluno
from services.gamificacao.eventos import EventoGamificacao
from services.gamificacao.missoes_service import atualizar_missoes


def registrar_evento_gamificacao(usuario_id: str, evento: EventoGamificacao, dados: dict | None = None) -> None:
    """Ponto único que os routers chamam quando o aluno realiza uma ação
    relevante. Não recebe request/response — só usuario_id, o evento e os
    dados mínimos necessários para avaliar aquele evento específico (ex.:
    {"materia_id": ...} para QUESTAO_ACERTADA, {"minutos": ...} para
    SESSAO_ESTUDO_CONCLUIDA).

    Concessão de XP pela ação em si (ex.: +10 por concluir aula) continua
    responsabilidade do caller via xp_service.conceder_xp_e_atividade —
    aqui só reage ao evento: conquistas e progresso de missão.
    """
    dados = dados or {}
    avaliar_conquistas(usuario_id, evento, dados)
    atualizar_missoes(usuario_id, evento, dados)
