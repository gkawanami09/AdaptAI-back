from services.simulados_service import (
    selecionar_questoes,
    selecionar_questoes_evitando,
    calcular_resultado,
    calcular_resultado_por_area,
)


def test_selecionar_questoes_sem_repeticao():
    pool = [f"q{i}" for i in range(50)]
    selecionadas = selecionar_questoes(pool, 20)

    assert len(selecionadas) == 20
    assert len(set(selecionadas)) == 20
    assert set(selecionadas) <= set(pool)


def test_selecionar_questoes_pool_menor_que_quantidade_devolve_pool_inteiro():
    pool = ["q1", "q2", "q3"]
    selecionadas = selecionar_questoes(pool, 10)

    assert sorted(selecionadas) == sorted(pool)


def test_selecionar_questoes_evitando_prefere_pool_sem_repeticao():
    pool = [f"q{i}" for i in range(10)]
    evitar = {"q0", "q1", "q2"}

    selecionadas = selecionar_questoes_evitando(pool, 5, evitar)

    assert len(selecionadas) == 5
    assert not (set(selecionadas) & evitar)


def test_selecionar_questoes_evitando_repete_se_nao_tiver_banco_suficiente():
    pool = ["q1", "q2", "q3"]
    evitar = {"q1", "q2"}  # só "q3" sobra sem repetir

    selecionadas = selecionar_questoes_evitando(pool, 3, evitar)

    assert len(selecionadas) == 3
    assert sorted(selecionadas) == sorted(pool)  # precisou repetir q1/q2


def test_selecionar_questoes_evitando_sem_evitar_funciona_como_selecionar_questoes():
    pool = [f"q{i}" for i in range(20)]

    selecionadas = selecionar_questoes_evitando(pool, 5, None)

    assert len(selecionadas) == 5
    assert len(set(selecionadas)) == 5


def test_calcular_resultado_zero_por_cento():
    resultado = calcular_resultado([False, False, False, False])

    assert resultado == {
        "total_questoes": 4,
        "respostas_corretas": 0,
        "percentual_acerto": 0,
        "nota_estimada": 0,
    }


def test_calcular_resultado_cem_por_cento():
    resultado = calcular_resultado([True, True, True, True])

    assert resultado == {
        "total_questoes": 4,
        "respostas_corretas": 4,
        "percentual_acerto": 100,
        "nota_estimada": 1000,
    }


def test_calcular_resultado_arredonda_percentual():
    resultado = calcular_resultado([True, True, True, False, False, False, False])  # 3/7 = 42.86%

    assert resultado["respostas_corretas"] == 3
    assert resultado["percentual_acerto"] == 43
    assert resultado["nota_estimada"] == 430


def test_calcular_resultado_sem_respostas_nao_quebra():
    resultado = calcular_resultado([])

    assert resultado["total_questoes"] == 0
    assert resultado["percentual_acerto"] == 0
    assert resultado["nota_estimada"] == 0


def test_calcular_resultado_por_area_multiplas_areas():
    respostas_por_area = {
        "matematica": [True, True, False, False],  # 50%
        "linguagens": [True, True, True, True],  # 100%
    }

    resultados = calcular_resultado_por_area(respostas_por_area)
    resultados_por_area = {r["area"]: r for r in resultados}

    assert resultados_por_area["matematica"]["percentual_acerto"] == 50
    assert resultados_por_area["matematica"]["nota"] == 500
    assert resultados_por_area["linguagens"]["percentual_acerto"] == 100
    assert resultados_por_area["linguagens"]["nota"] == 1000
