from enum import Enum


class EventoGamificacao(str, Enum):
    QUESTAO_RESPONDIDA = "questao_respondida"
    QUESTAO_ACERTADA = "questao_acertada"
    QUESTAO_ERRADA = "questao_errada"
    REVISAO_QUESTAO_CONCLUIDA = "revisao_questao_concluida"
    AULA_CONCLUIDA = "aula_concluida"
    SESSAO_ESTUDO_CONCLUIDA = "sessao_estudo_concluida"
    REDACAO_ENVIADA = "redacao_enviada"
    CORRECAO_REDACAO_CONCLUIDA = "correcao_redacao_concluida"
    SIMULADO_CONCLUIDO = "simulado_concluido"
