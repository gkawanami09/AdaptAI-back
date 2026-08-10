from unittest.mock import MagicMock


def query_result(data=None, count=None):
    resultado = MagicMock()
    resultado.data = data
    resultado.count = count
    return resultado


class FakeSupabase:
    """Mock mínimo de supabase_admin: toda tabela devolve o mesmo mock
    encadeável (select/eq/in_/neq/limit/order... retornam self), e
    `.execute()` é configurado por teste via `tabela(nome).execute.side_effect`
    ou `.return_value`.
    """

    def __init__(self):
        self._tabelas: dict[str, MagicMock] = {}

    def table(self, nome: str) -> MagicMock:
        if nome not in self._tabelas:
            mock = MagicMock(name=f"tabela_{nome}")
            for metodo in ("select", "eq", "neq", "in_", "order", "limit", "insert", "update", "delete"):
                getattr(mock, metodo).return_value = mock
            self._tabelas[nome] = mock
        return self._tabelas[nome]
