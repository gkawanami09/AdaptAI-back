from services.monitoramento import MonitorDesempenho


def test_resumo_agrupa_rotas_por_metodo_e_caminho():
    monitor = MonitorDesempenho()
    monitor.registrar_request("GET", "/aluno/questoes", 100.0, 200)
    monitor.registrar_request("GET", "/aluno/questoes", 200.0, 200)
    monitor.registrar_request("POST", "/aluno/questoes", 50.0, 500)

    resumo = monitor.resumo()
    rotas_por_chave = {(r["metodo"], r["rota"]): r for r in resumo["rotas"]}

    assert ("GET", "/aluno/questoes") in rotas_por_chave
    assert ("POST", "/aluno/questoes") in rotas_por_chave

    get_stats = rotas_por_chave[("GET", "/aluno/questoes")]
    assert get_stats["total_requisicoes"] == 2
    assert get_stats["latencia_media_ms"] == 150.0
    assert get_stats["taxa_erro_pct"] == 0

    post_stats = rotas_por_chave[("POST", "/aluno/questoes")]
    assert post_stats["total_requisicoes"] == 1
    assert post_stats["taxa_erro_pct"] == 100.0


def test_resumo_operacoes_ia_usa_total_chamadas():
    monitor = MonitorDesempenho()
    monitor.registrar_chamada_ia("gerar-lista", 2000.0, True)
    monitor.registrar_chamada_ia("gerar-lista", 3000.0, False)

    resumo = monitor.resumo()
    operacao = next(o for o in resumo["operacoes_ia"] if o["operacao"] == "gerar-lista")

    assert operacao["total_chamadas"] == 2
    assert operacao["latencia_media_ms"] == 2500.0
    assert operacao["taxa_erro_pct"] == 50.0


def test_resumo_sem_dados_devolve_listas_vazias():
    monitor = MonitorDesempenho()

    resumo = monitor.resumo()

    assert resumo["rotas"] == []
    assert resumo["operacoes_ia"] == []
