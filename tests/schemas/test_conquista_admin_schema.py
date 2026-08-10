import pytest
from pydantic import ValidationError

from schemas.conquista_admin_schema import ConquistaCriar, ConquistaEditar
from services.gamificacao.metricas import MEDIDORES


def _payload_base(**overrides):
    payload = {
        "titulo": "Nova Conquista",
        "tipo_condicao": "questoes_respondidas",
        "valor_condicao": 10,
    }
    payload.update(overrides)
    return payload


def test_tipo_condicao_valido_e_aceito():
    conquista = ConquistaCriar(**_payload_base())
    assert conquista.tipo_condicao == "questoes_respondidas"


def test_tipo_condicao_invalido_e_rejeitado():
    with pytest.raises(ValidationError):
        ConquistaCriar(**_payload_base(tipo_condicao="condicao-que-nao-existe"))


def test_todas_as_condicoes_reais_sao_aceitas():
    for tipo_condicao in MEDIDORES.keys():
        conquista = ConquistaCriar(**_payload_base(tipo_condicao=tipo_condicao))
        assert conquista.tipo_condicao == tipo_condicao


def test_editar_permite_tipo_condicao_ausente():
    edicao = ConquistaEditar()
    assert edicao.tipo_condicao is None


def test_editar_rejeita_tipo_condicao_invalido():
    with pytest.raises(ValidationError):
        ConquistaEditar(tipo_condicao="condicao-que-nao-existe")
