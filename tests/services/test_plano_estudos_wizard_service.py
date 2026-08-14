from datetime import date, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from services.plano_estudos_wizard_service import PlanoEstudosWizardService
from tests.services._supabase_mock import FakeSupabase, query_result


def _query_result(data):
    resultado = MagicMock()
    resultado.data = data
    return resultado


def test_obter_plano_nao_retorna_plano_de_outro_aluno():
    service = PlanoEstudosWizardService()

    with patch("services.plano_estudos_wizard_service.supabase_admin") as supabase_mock:
        tabela = supabase_mock.table.return_value
        tabela.select.return_value = tabela
        tabela.eq.return_value = tabela
        tabela.limit.return_value = tabela
        tabela.execute.return_value = _query_result([])

        plano = service.obter_plano("plano-1", "usuario-outro")

        assert plano is None
        tabela.eq.assert_any_call("usuario_id", "usuario-outro")


def test_validar_slugs_rejeita_prova_inexistente():
    service = PlanoEstudosWizardService()

    with patch("services.plano_estudos_wizard_service.supabase_admin") as supabase_mock:
        tabela = supabase_mock.table.return_value
        tabela.select.return_value = tabela
        tabela.in_.return_value = tabela
        tabela.execute.return_value = _query_result([{"slug": "matematica"}])

        from fastapi import HTTPException
        import pytest

        with pytest.raises(HTTPException) as exc_info:
            service._validar_slugs(["prova-inexistente"], ["matematica"])

        assert exc_info.value.status_code == 422


def test_generator_padrao_e_deterministico_ia_e_so_sob_demanda():
    deterministico = MagicMock(name="deterministico")
    ia = MagicMock(name="ia")
    service = PlanoEstudosWizardService(deterministic_generator=deterministico, ai_generator=ia)

    assert service._escolher_generator(SimpleNamespace(usar_ia=False)) is deterministico
    assert service._escolher_generator(SimpleNamespace(usar_ia=True)) is ia


def test_replanejar_apos_conclusao_nao_reoferece_aula_concluida():
    hoje = date.today()
    plano_id = "plano-1"
    usuario_id = "usuario-1"

    fake = FakeSupabase()

    fake.table("planos_estudo").execute.side_effect = [
        query_result(data=[{
            "id": plano_id,
            "status": "ativo",
            "provas_selecionadas": ["enem"],
            "materias_selecionadas": ["matematica"],
            "tempo_por_dia_minutos": 20,
            "dias_estudo": ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"],
        }]),
        query_result(data=[]),  # update final, resposta não é checada
    ]

    fake.table("tipos_prova").execute.return_value = query_result(
        data=[{"id": "prova-1", "slug": "enem", "nome": "ENEM", "data_prova": (hoje + timedelta(days=90)).isoformat()}]
    )
    fake.table("materias").execute.return_value = query_result(
        data=[{"id": "materia-1", "slug": "matematica", "nome": "Matemática"}]
    )
    fake.table("questoes").execute.return_value = query_result(data=[])
    fake.table("listas_questoes").execute.return_value = query_result(data=[])
    fake.table("topicos").execute.return_value = query_result(data=[])
    fake.table("aulas").execute.return_value = query_result(data=[
        {"id": "a1", "materia_id": "materia-1", "topico_id": None, "titulo": "Aula 1", "ordem": 1,
         "mais_cobrado": False, "dificuldade": "medio"},
        {"id": "a2", "materia_id": "materia-1", "topico_id": None, "titulo": "Aula 2", "ordem": 2,
         "mais_cobrado": False, "dificuldade": "medio"},
    ])
    fake.table("aulas_conteudo").execute.return_value = query_result(data=[
        {"aula_id": "a1", "duracao": 20},
        {"aula_id": "a2", "duracao": 20},
    ])

    fake.table("tarefas_estudo").execute.side_effect = [
        query_result(data=[{
            "id": "tarefa-1",
            "materia_id": "materia-1",
            "aula_id": "a1",
            "status": "concluida",
            "data_agendada": hoje.isoformat(),
            "concluido_em": f"{hoje.isoformat()}T10:00:00Z",
        }]),
        query_result(data=[]),  # delete de tarefas futuras pendentes
        query_result(data=[{"id": "nova-tarefa"}]),  # insert das novas tarefas
    ]

    fake.table("planos_estudo_sessoes").execute.side_effect = [
        query_result(data=[]),  # delete de sessões futuras
        query_result(data=[{"id": "nova-sessao"}]),  # insert das novas sessões
    ]

    service = PlanoEstudosWizardService()

    with patch("services.plano_estudos_wizard_service.supabase_admin", fake), \
         patch("services.plano_estudos_wizard_service.hoje_brasil", return_value=hoje):
        service.replanejar_apos_conclusao(plano_id, usuario_id)

    payload_tarefas_inseridas = fake.table("tarefas_estudo").insert.call_args[0][0]
    aulas_ensinadas_como_novas = {
        t["aula_id"] for t in payload_tarefas_inseridas if t["tipo_tarefa"] == "aula"
    }

    # a1 já foi concluída — não pode voltar a ser ensinada como conteúdo
    # novo, só reaparecer como revisão (o que de fato acontece mais perto
    # da prova, rotacionando com a2 — ver asserção de rotação abaixo).
    assert "a1" not in aulas_ensinadas_como_novas
    # a2 é a única aula nova disponível, e precisa ser ensinada
    assert aulas_ensinadas_como_novas == {"a2"}

    revisoes = [t["aula_id"] for t in payload_tarefas_inseridas if t["tipo_tarefa"] == "revisao"]
    assert "a1" in revisoes  # a aula concluída volta como revisão
    for anterior, atual in zip(revisoes, revisoes[1:]):
        assert anterior != atual  # não repete a mesma aula em dias consecutivos
