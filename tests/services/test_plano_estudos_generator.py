from datetime import date, timedelta

from services.plano_estudos.contexto import (
    AulaContexto,
    ListaContexto,
    PlanoEstudosContexto,
    ProvaContexto,
)
from services.plano_estudos.deterministic_generator import DeterministicPlanGenerator

HOJE = date(2026, 1, 5)  # segunda-feira


def _aula(
    id_, materia, titulo, duracao, ordem_topico=0, ordem_aula=0, mais_cobrado=False,
    dificuldade="medio", topico_id=None,
):
    return AulaContexto(
        id=id_,
        materia_slug=materia,
        titulo=titulo,
        duracao_minutos=duracao,
        ordem_topico=ordem_topico,
        ordem_aula=ordem_aula,
        mais_cobrado=mais_cobrado,
        dificuldade=dificuldade,
        topico_id=topico_id,
    )


def _contexto(
    provas,
    materias_selecionadas,
    materias_por_prova,
    aulas_por_materia,
    tempo_por_dia_minutos=60,
    dias_estudo=None,
    taxa_erro_por_materia=None,
    taxa_erro_por_topico=None,
    listas_por_materia=None,
):
    return PlanoEstudosContexto(
        data_inicio=HOJE,
        provas=provas,
        materias_selecionadas=materias_selecionadas,
        materias_por_prova=materias_por_prova,
        aulas_por_materia=aulas_por_materia,
        tempo_por_dia_minutos=tempo_por_dia_minutos,
        dias_estudo=dias_estudo or ["monday", "tuesday", "wednesday", "thursday", "friday"],
        taxa_erro_por_materia=taxa_erro_por_materia or {},
        taxa_erro_por_topico=taxa_erro_por_topico or {},
        listas_por_materia=listas_por_materia or {},
    )


def test_uma_prova_gera_sessoes_com_aulas_reais():
    aulas = [
        _aula("a1", "matematica", "Funções de 1º grau", 30, ordem_aula=1),
        _aula("a2", "matematica", "Funções quadráticas", 30, ordem_aula=2),
    ]
    contexto = _contexto(
        provas=[ProvaContexto("enem", "ENEM", HOJE + timedelta(days=90))],
        materias_selecionadas=["matematica"],
        materias_por_prova={"enem": {"matematica"}},
        aulas_por_materia={"matematica": aulas},
    )

    plano = DeterministicPlanGenerator().gerar(contexto)

    assert plano.periodo_fim == HOJE + timedelta(days=90)
    assert plano.dias, "deveria gerar ao menos um dia com sessões"

    primeira_sessao = plano.dias[0].sessoes[0]
    assert primeira_sessao.aula_id == "a1"
    assert primeira_sessao.titulo == "Funções de 1º grau"
    assert primeira_sessao.materia == "matematica"


def test_duas_provas_periodo_fim_e_a_data_mais_distante():
    contexto = _contexto(
        provas=[
            ProvaContexto("enem", "ENEM", HOJE + timedelta(days=90)),
            ProvaContexto("fuvest", "Fuvest", HOJE + timedelta(days=45)),
        ],
        materias_selecionadas=["matematica"],
        materias_por_prova={"enem": {"matematica"}, "fuvest": {"matematica"}},
        aulas_por_materia={"matematica": [_aula("a1", "matematica", "Aula 1", 30)]},
    )

    plano = DeterministicPlanGenerator().gerar(contexto)

    assert plano.periodo_fim == HOJE + timedelta(days=90)


def test_prova_mais_proxima_recebe_maior_prioridade():
    gerador = DeterministicPlanGenerator()
    provas_validas = [
        (ProvaContexto("enem", "ENEM", HOJE + timedelta(days=90)), HOJE + timedelta(days=90)),
        (ProvaContexto("fuvest", "Fuvest", HOJE + timedelta(days=10)), HOJE + timedelta(days=10)),
    ]
    contexto = _contexto(
        provas=[p for p, _ in provas_validas],
        materias_selecionadas=["matematica", "quimica"],
        materias_por_prova={"enem": {"matematica"}, "fuvest": {"quimica"}},
        aulas_por_materia={
            "matematica": [_aula("a1", "matematica", "Aula mat", 30)],
            "quimica": [_aula("a2", "quimica", "Aula quim", 30)],
        },
    )

    ordenadas = gerador._priorizar_materias(contexto, provas_validas, HOJE)

    assert ordenadas[0] == "quimica"  # ligada à prova mais próxima (Fuvest, 10 dias)
    assert ordenadas[1] == "matematica"


def test_materia_selecionada_sem_prova_relacionada_ainda_e_incluida_com_prioridade_menor():
    gerador = DeterministicPlanGenerator()
    provas_validas = [
        (ProvaContexto("enem", "ENEM", HOJE + timedelta(days=90)), HOJE + timedelta(days=90)),
    ]
    contexto = _contexto(
        provas=[p for p, _ in provas_validas],
        materias_selecionadas=["matematica", "redacao"],
        materias_por_prova={"enem": {"matematica"}},
        aulas_por_materia={
            "matematica": [_aula("a1", "matematica", "Aula mat", 30)],
            "redacao": [_aula("a2", "redacao", "Aula red", 30)],
        },
    )

    ordenadas = gerador._priorizar_materias(contexto, provas_validas, HOJE)

    assert ordenadas == ["matematica", "redacao"]


def test_limite_diario_e_respeitado():
    aulas = [_aula(f"a{i}", "matematica", f"Aula {i}", 40) for i in range(5)]
    contexto = _contexto(
        provas=[ProvaContexto("enem", "ENEM", HOJE + timedelta(days=30))],
        materias_selecionadas=["matematica"],
        materias_por_prova={"enem": {"matematica"}},
        aulas_por_materia={"matematica": aulas},
        tempo_por_dia_minutos=60,
    )

    plano = DeterministicPlanGenerator().gerar(contexto)

    for dia in plano.dias:
        total = sum(s.duracao_minutos for s in dia.sessoes)
        assert total <= 60


def test_somente_dias_selecionados_recebem_sessao():
    aulas = [_aula(f"a{i}", "matematica", f"Aula {i}", 30) for i in range(20)]
    contexto = _contexto(
        provas=[ProvaContexto("enem", "ENEM", HOJE + timedelta(days=30))],
        materias_selecionadas=["matematica"],
        materias_por_prova={"enem": {"matematica"}},
        aulas_por_materia={"matematica": aulas},
        dias_estudo=["monday", "wednesday"],
    )

    plano = DeterministicPlanGenerator().gerar(contexto)

    dias_com_sessao = {dia.data.strftime("%A").lower() for dia in plano.dias}
    assert dias_com_sessao <= {"monday", "wednesday"}


def test_aulas_reais_sao_utilizadas_em_ordem_de_topico_e_ordem():
    aulas = [
        _aula("a2", "matematica", "Segunda", 20, ordem_topico=1, ordem_aula=2),
        _aula("a1", "matematica", "Primeira", 20, ordem_topico=1, ordem_aula=1),
    ]
    contexto = _contexto(
        provas=[ProvaContexto("enem", "ENEM", HOJE + timedelta(days=30))],
        materias_selecionadas=["matematica"],
        materias_por_prova={"enem": {"matematica"}},
        aulas_por_materia={"matematica": sorted(aulas, key=lambda a: (a.ordem_topico, a.ordem_aula))},
    )

    plano = DeterministicPlanGenerator().gerar(contexto)

    primeira_sessao = plano.dias[0].sessoes[0]
    assert primeira_sessao.aula_id == "a1"


def test_plano_nao_ultrapassa_data_da_prova():
    contexto = _contexto(
        provas=[ProvaContexto("enem", "ENEM", HOJE + timedelta(days=14))],
        materias_selecionadas=["matematica"],
        materias_por_prova={"enem": {"matematica"}},
        aulas_por_materia={"matematica": [_aula(f"a{i}", "matematica", f"Aula {i}", 20) for i in range(50)]},
    )

    plano = DeterministicPlanGenerator().gerar(contexto)

    for dia in plano.dias:
        assert dia.data <= HOJE + timedelta(days=14)


def test_prova_sem_data_nao_quebra_geracao_e_gera_aviso():
    contexto = _contexto(
        provas=[ProvaContexto("enem", "ENEM", None)],
        materias_selecionadas=["matematica"],
        materias_por_prova={"enem": {"matematica"}},
        aulas_por_materia={"matematica": [_aula("a1", "matematica", "Aula 1", 30)]},
    )

    plano = DeterministicPlanGenerator().gerar(contexto)

    assert any("sem data" in aviso for aviso in plano.avisos)
    assert plano.periodo_fim == HOJE + timedelta(weeks=12)


def test_materia_sem_aulas_gera_aviso_e_nao_quebra():
    contexto = _contexto(
        provas=[ProvaContexto("enem", "ENEM", HOJE + timedelta(days=30))],
        materias_selecionadas=["matematica", "fisica"],
        materias_por_prova={"enem": {"matematica", "fisica"}},
        aulas_por_materia={"matematica": [_aula("a1", "matematica", "Aula 1", 30)], "fisica": []},
    )

    plano = DeterministicPlanGenerator().gerar(contexto)

    assert any("fisica" in aviso and "não possui aulas" in aviso for aviso in plano.avisos)
    assert plano.dias  # matemática ainda deve gerar sessões


def test_prova_ja_passada_e_ignorada():
    contexto = _contexto(
        provas=[ProvaContexto("enem", "ENEM", HOJE - timedelta(days=5))],
        materias_selecionadas=["matematica"],
        materias_por_prova={"enem": {"matematica"}},
        aulas_por_materia={"matematica": [_aula("a1", "matematica", "Aula 1", 30)]},
    )

    plano = DeterministicPlanGenerator().gerar(contexto)

    assert any("já ocorreu" in aviso for aviso in plano.avisos)
    assert plano.periodo_fim == HOJE + timedelta(weeks=12)


def test_fase_revisao_perto_da_prova_reutiliza_aula_ja_estudada():
    contexto = _contexto(
        provas=[ProvaContexto("enem", "ENEM", HOJE + timedelta(days=10))],
        materias_selecionadas=["matematica"],
        materias_por_prova={"enem": {"matematica"}},
        aulas_por_materia={"matematica": [_aula("a1", "matematica", "Aula única", 20)]},
        tempo_por_dia_minutos=60,
    )

    plano = DeterministicPlanGenerator().gerar(contexto)

    tipos = {s.tipo for dia in plano.dias for s in dia.sessoes}
    assert "revisao" in tipos


def test_aula_maior_que_tempo_diario_e_ignorada_sem_ultrapassar_limite():
    aulas = [
        _aula("a1", "matematica", "Aula enorme", 200),
        _aula("a2", "matematica", "Aula normal", 30),
    ]
    contexto = _contexto(
        provas=[ProvaContexto("enem", "ENEM", HOJE + timedelta(days=30))],
        materias_selecionadas=["matematica"],
        materias_por_prova={"enem": {"matematica"}},
        aulas_por_materia={"matematica": aulas},
        tempo_por_dia_minutos=60,
    )

    plano = DeterministicPlanGenerator().gerar(contexto)

    todos_ids = {s.aula_id for dia in plano.dias for s in dia.sessoes}
    assert "a1" not in todos_ids
    assert "a2" in todos_ids
    for dia in plano.dias:
        assert sum(s.duracao_minutos for s in dia.sessoes) <= 60


def test_nao_repete_a_mesma_materia_mais_de_uma_vez_no_mesmo_dia():
    # cenário exato do bug reportado: 1 matéria com 1 única aula, orçamento
    # diário grande o bastante pra "caber" a mesma aula várias vezes como
    # revisão (120 // 30 = 4 repetições) se não houvesse o limite por dia.
    contexto = _contexto(
        provas=[ProvaContexto("enem", "ENEM", HOJE + timedelta(days=10))],
        materias_selecionadas=["matematica"],
        materias_por_prova={"enem": {"matematica"}},
        aulas_por_materia={"matematica": [_aula("a1", "matematica", "Aula única", 30)]},
        tempo_por_dia_minutos=120,
    )

    plano = DeterministicPlanGenerator().gerar(contexto)

    for dia in plano.dias:
        materias_no_dia = [s.materia for s in dia.sessoes]
        assert len(materias_no_dia) == len(set(materias_no_dia)), (
            f"matéria repetida no mesmo dia: {materias_no_dia}"
        )
        assert len(dia.sessoes) <= 1


def test_nao_repete_materia_no_mesmo_dia_com_varias_materias_e_pouco_conteudo():
    contexto = _contexto(
        provas=[ProvaContexto("enem", "ENEM", HOJE + timedelta(days=10))],
        materias_selecionadas=["matematica", "fisica", "quimica"],
        materias_por_prova={"enem": {"matematica", "fisica", "quimica"}},
        aulas_por_materia={
            "matematica": [_aula("a1", "matematica", "Aula mat", 30)],
            "fisica": [],
            "quimica": [],
        },
        tempo_por_dia_minutos=120,
    )

    plano = DeterministicPlanGenerator().gerar(contexto)

    for dia in plano.dias:
        materias_no_dia = [s.materia for s in dia.sessoes]
        assert len(materias_no_dia) == len(set(materias_no_dia))


def test_aula_mais_cobrada_e_servida_antes_das_demais():
    aulas = [
        _aula("comum", "matematica", "Aula comum", 20, ordem_topico=1, ordem_aula=1, mais_cobrado=False),
        _aula("cobrada", "matematica", "Aula mais cobrada", 20, ordem_topico=1, ordem_aula=2, mais_cobrado=True),
    ]
    contexto = _contexto(
        provas=[ProvaContexto("enem", "ENEM", HOJE + timedelta(days=90))],
        materias_selecionadas=["matematica"],
        materias_por_prova={"enem": {"matematica"}},
        aulas_por_materia={"matematica": aulas},
        tempo_por_dia_minutos=20,
    )

    plano = DeterministicPlanGenerator().gerar(contexto)

    primeira_sessao = plano.dias[0].sessoes[0]
    assert primeira_sessao.aula_id == "cobrada"


def test_aula_mais_facil_vem_antes_da_dificil_no_mesmo_nivel_de_importancia():
    aulas = [
        _aula("dificil", "matematica", "Aula difícil", 20, ordem_topico=1, ordem_aula=1, dificuldade="dificil"),
        _aula("facil", "matematica", "Aula fácil", 20, ordem_topico=1, ordem_aula=2, dificuldade="basico"),
    ]
    contexto = _contexto(
        provas=[ProvaContexto("enem", "ENEM", HOJE + timedelta(days=90))],
        materias_selecionadas=["matematica"],
        materias_por_prova={"enem": {"matematica"}},
        aulas_por_materia={"matematica": aulas},
        tempo_por_dia_minutos=20,
    )

    plano = DeterministicPlanGenerator().gerar(contexto)

    primeira_sessao = plano.dias[0].sessoes[0]
    assert primeira_sessao.aula_id == "facil"


def test_revisao_circula_entre_aulas_ja_vistas_em_vez_de_repetir_a_ultima():
    # Prova a 40 dias: começa em fase "misto" (ensina a1 e a2 como conteúdo
    # novo nos 2 primeiros dias) e depois de esgotar a fila cai em revisão
    # com as duas aulas já no histórico — cenário em que a rotação importa.
    aulas = [
        _aula("a1", "matematica", "Aula 1", 20, ordem_aula=1),
        _aula("a2", "matematica", "Aula 2", 20, ordem_aula=2),
    ]
    contexto = _contexto(
        provas=[ProvaContexto("enem", "ENEM", HOJE + timedelta(days=40))],
        materias_selecionadas=["matematica"],
        materias_por_prova={"enem": {"matematica"}},
        aulas_por_materia={"matematica": aulas},
        tempo_por_dia_minutos=20,
    )

    plano = DeterministicPlanGenerator().gerar(contexto)

    sessoes_revisao = [
        s.aula_id for dia in plano.dias for s in dia.sessoes if s.tipo == "revisao"
    ]
    assert sessoes_revisao, "deveria ter entrado em fase de revisão com a prova a 10 dias"
    # não pode ficar preso sempre na mesma aula — as duas precisam aparecer
    assert set(sessoes_revisao) == {"a1", "a2"}
    # dias consecutivos de revisão não repetem a mesma aula
    for anterior, atual in zip(sessoes_revisao, sessoes_revisao[1:]):
        assert anterior != atual


def test_replanejamento_nao_reoferece_aula_ja_concluida_e_retoma_historico():
    aulas = [
        _aula("a1", "matematica", "Aula 1", 20, ordem_aula=1),
        _aula("a2", "matematica", "Aula 2", 20, ordem_aula=2),
    ]
    contexto = _contexto(
        provas=[ProvaContexto("enem", "ENEM", HOJE + timedelta(days=90))],
        materias_selecionadas=["matematica"],
        materias_por_prova={"enem": {"matematica"}},
        aulas_por_materia={"matematica": aulas},
        tempo_por_dia_minutos=20,
    )

    aula_ja_concluida = aulas[0]
    plano = DeterministicPlanGenerator().gerar(
        contexto,
        historico_inicial={"matematica": [aula_ja_concluida]},
        aulas_ja_usadas={"a1"},
        data_inicio_override=HOJE + timedelta(days=1),
    )

    todos_ids = {s.aula_id for dia in plano.dias for s in dia.sessoes if s.tipo == "teoria"}
    assert "a1" not in todos_ids
    assert "a2" in todos_ids
    assert plano.periodo_inicio == HOJE + timedelta(days=1)


def test_materia_com_mais_erro_sobe_na_prioridade_mesmo_com_prova_mais_distante():
    gerador = DeterministicPlanGenerator()
    provas_validas = [
        (ProvaContexto("enem", "ENEM", HOJE + timedelta(days=30)), HOJE + timedelta(days=30)),
        (ProvaContexto("fuvest", "Fuvest", HOJE + timedelta(days=25)), HOJE + timedelta(days=25)),
    ]
    contexto = _contexto(
        provas=[p for p, _ in provas_validas],
        materias_selecionadas=["matematica", "quimica"],
        materias_por_prova={"enem": {"matematica"}, "fuvest": {"quimica"}},
        aulas_por_materia={
            "matematica": [_aula("a1", "matematica", "Aula mat", 30)],
            "quimica": [_aula("a2", "quimica", "Aula quim", 30)],
        },
        # Sem taxa de erro, quimica venceria por ter a prova mais próxima
        # (25 dias vs 30). Com erro alto em matemática, o boost deve
        # inverter essa ordem.
        taxa_erro_por_materia={"matematica": 1.0},
    )

    ordenadas = gerador._priorizar_materias(contexto, provas_validas, HOJE)

    assert ordenadas[0] == "matematica"


def test_materia_fraca_ganha_sessao_extra_de_revisao_quando_sobra_tempo():
    aulas = [_aula("a1", "matematica", "Aula única", 20)]
    contexto = _contexto(
        provas=[ProvaContexto("enem", "ENEM", HOJE + timedelta(days=90))],
        materias_selecionadas=["matematica"],
        materias_por_prova={"enem": {"matematica"}},
        aulas_por_materia={"matematica": aulas},
        tempo_por_dia_minutos=60,
        taxa_erro_por_materia={"matematica": 0.8},
    )

    plano = DeterministicPlanGenerator().gerar(contexto)

    primeiro_dia = plano.dias[0]
    tipos_no_dia = [s.tipo for s in primeiro_dia.sessoes]
    assert tipos_no_dia.count("revisao") >= 1
    assert len(primeiro_dia.sessoes) >= 2


def test_materia_fraca_com_lista_disponivel_prefere_sessao_de_questoes_no_reforco():
    aulas = [_aula("a1", "matematica", "Aula única", 20)]
    contexto = _contexto(
        provas=[ProvaContexto("enem", "ENEM", HOJE + timedelta(days=90))],
        materias_selecionadas=["matematica"],
        materias_por_prova={"enem": {"matematica"}},
        aulas_por_materia={"matematica": aulas},
        tempo_por_dia_minutos=60,
        taxa_erro_por_materia={"matematica": 0.8},
        listas_por_materia={"matematica": ListaContexto(id="lista-1", materia_slug="matematica")},
    )

    plano = DeterministicPlanGenerator().gerar(contexto)

    sessoes_questoes = [
        s for dia in plano.dias for s in dia.sessoes if s.tipo == "questoes"
    ]
    assert sessoes_questoes, "deveria ter gerado ao menos uma sessão de prática de questões"
    assert sessoes_questoes[0].lista_questoes_id == "lista-1"


def test_materia_sem_erro_nao_ganha_reforco_extra():
    aulas = [_aula("a1", "matematica", "Aula única", 20)]
    contexto = _contexto(
        provas=[ProvaContexto("enem", "ENEM", HOJE + timedelta(days=90))],
        materias_selecionadas=["matematica"],
        materias_por_prova={"enem": {"matematica"}},
        aulas_por_materia={"matematica": aulas},
        tempo_por_dia_minutos=60,
        taxa_erro_por_materia={"matematica": 0.1},
    )

    plano = DeterministicPlanGenerator().gerar(contexto)

    assert len(plano.dias[0].sessoes) == 1


def test_topico_fraco_e_priorizado_dentro_da_materia():
    aulas = [
        _aula("a1", "matematica", "Tópico forte", 20, ordem_topico=1, ordem_aula=1, topico_id="topico-forte"),
        _aula("a2", "matematica", "Tópico fraco", 20, ordem_topico=2, ordem_aula=1, topico_id="topico-fraco"),
    ]
    contexto = _contexto(
        provas=[ProvaContexto("enem", "ENEM", HOJE + timedelta(days=90))],
        materias_selecionadas=["matematica"],
        materias_por_prova={"enem": {"matematica"}},
        aulas_por_materia={"matematica": aulas},
        tempo_por_dia_minutos=20,
        taxa_erro_por_topico={"topico-fraco": 0.9},
    )

    plano = DeterministicPlanGenerator().gerar(contexto)

    primeira_sessao = plano.dias[0].sessoes[0]
    assert primeira_sessao.aula_id == "a2"


def test_sem_dados_de_erro_comportamento_e_identico_ao_anterior():
    aulas = [
        _aula("comum", "matematica", "Aula comum", 20, ordem_topico=1, ordem_aula=1, mais_cobrado=False),
        _aula("cobrada", "matematica", "Aula mais cobrada", 20, ordem_topico=1, ordem_aula=2, mais_cobrado=True),
    ]
    contexto = _contexto(
        provas=[ProvaContexto("enem", "ENEM", HOJE + timedelta(days=90))],
        materias_selecionadas=["matematica"],
        materias_por_prova={"enem": {"matematica"}},
        aulas_por_materia={"matematica": aulas},
        tempo_por_dia_minutos=20,
    )

    plano = DeterministicPlanGenerator().gerar(contexto)

    primeira_sessao = plano.dias[0].sessoes[0]
    assert primeira_sessao.aula_id == "cobrada"
