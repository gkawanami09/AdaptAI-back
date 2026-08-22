import pytest

from services.ai.base import AIRespostaInvalidaError
from services.ai.json_parsing import extrair_e_validar_json
from services.ai.schemas.questoes_geradas_schema import QuestoesGeradasIA


def test_extrai_json_completo_normalmente():
    conteudo = '{"questoes": [{"enunciado": "2+2?", "alternativas": ["3","4"], "resposta_correta": "4"}]}'

    resultado = extrair_e_validar_json(conteudo, QuestoesGeradasIA)

    assert len(resultado.questoes) == 1
    assert resultado.questoes[0].enunciado == "2+2?"


def test_recupera_itens_completos_quando_json_e_cortado_no_meio():
    """Regressão: modelo estourou o orçamento de tokens no meio da 3ª
    questão (visto de verdade com qwen2.5:1.5b gerando 10 questões de um
    tópico só — a explicação de uma questão de polinômio ficou gigante e
    consumiu todo o orçamento). Antes disso, json.loads falhava por
    inteiro e as 2 questões já completas eram jogadas fora junto."""
    conteudo = (
        '{"questoes": ['
        '{"enunciado": "2+2?", "alternativas": ["3","4"], "resposta_correta": "4"},'
        '{"enunciado": "3+3?", "alternativas": ["5","6"], "resposta_correta": "6"},'
        '{"enunciado": "Calcule m(6) - m(-6) onde m(x) = 9x^9 - 10x^8...", '
        '"explicacao": "m(6) = 9(6)^9 - 10(6)^8 + 11(6)^7 - 12'  # corta no meio
    )

    resultado = extrair_e_validar_json(conteudo, QuestoesGeradasIA)

    assert len(resultado.questoes) == 2
    assert resultado.questoes[0].enunciado == "2+2?"
    assert resultado.questoes[1].enunciado == "3+3?"


def test_levanta_erro_quando_nao_ha_nenhum_item_completo():
    conteudo = '{"questoes": [{"enunciado": "2+2?", "alternativas": ["3"'  # corta na 1ª questão

    with pytest.raises(AIRespostaInvalidaError):
        extrair_e_validar_json(conteudo, QuestoesGeradasIA)


def test_levanta_erro_quando_nao_ha_bloco_json_nenhum():
    with pytest.raises(AIRespostaInvalidaError):
        extrair_e_validar_json("desculpe, não consigo ajudar com isso", QuestoesGeradasIA)
