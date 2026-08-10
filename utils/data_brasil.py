from datetime import date, datetime
from zoneinfo import ZoneInfo

FUSO_BRASIL = ZoneInfo("America/Sao_Paulo")


def hoje_brasil() -> date:
    """`date.today()` usa o timezone do sistema operacional do servidor,
    que em produção costuma ser UTC — à noite (a partir de ~21h em
    horário de Brasília) isso já retorna o dia seguinte ao que o aluno
    vê no relógio dele, fazendo tarefas "sumirem" do dia certo na tela.
    Esta função fixa o cálculo no horário do Brasil, independente de
    como o servidor está configurado.
    """
    return datetime.now(FUSO_BRASIL).date()
