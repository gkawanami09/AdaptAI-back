from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from uuid import uuid4

from routers import simulados
from tests.services._supabase_mock import FakeSupabase, query_result

USUARIO_ID = str(uuid4())
OUTRO_USUARIO_ID = str(uuid4())
TENTATIVA_ID = str(uuid4())
MODELO_ID = str(uuid4())
MATERIA_MAT_ID = str(uuid4())
MATERIA_HIST_ID = str(uuid4())
QUESTAO_1 = str(uuid4())
QUESTAO_2 = str(uuid4())


class _UsuarioFake:
    id = USUARIO_ID


def test_buscar_tentativa_de_outro_aluno_retorna_404():
    fake = FakeSupabase()
    fake.table("sessoes_simulado").execute.return_value = query_result(data=[{
        "id": TENTATIVA_ID, "usuario_id": OUTRO_USUARIO_ID, "modelo_simulado_id": MODELO_ID,
        "status": "em_andamento", "iniciado_em": "2026-01-01T10:00:00+00:00",
        "tempo_limite_segundos": 3600, "concluido_em": None, "duracao_segundos": None,
        "total_questoes": 10, "questoes_respondidas": 0, "respostas_corretas": 0,
        "percentual_acerto": 0, "nota_estimada": 0,
    }])

    with patch("routers.simulados.supabase_admin", fake):
        try:
            simulados._buscar_tentativa(TENTATIVA_ID, USUARIO_ID)
            assert False, "deveria levantar HTTPException"
        except Exception as erro:
            assert getattr(erro, "status_code", None) == 404


def test_buscar_tentativa_inexistente_retorna_404():
    fake = FakeSupabase()
    fake.table("sessoes_simulado").execute.return_value = query_result(data=[])

    with patch("routers.simulados.supabase_admin", fake):
        try:
            simulados._buscar_tentativa(TENTATIVA_ID, USUARIO_ID)
            assert False, "deveria levantar HTTPException"
        except Exception as erro:
            assert getattr(erro, "status_code", None) == 404


def test_buscar_tentativa_traduz_status_legado():
    fake = FakeSupabase()
    fake.table("sessoes_simulado").execute.return_value = query_result(data=[{
        "id": TENTATIVA_ID, "usuario_id": USUARIO_ID, "modelo_simulado_id": MODELO_ID,
        "status": "concluido", "iniciado_em": "2026-01-01T10:00:00+00:00",
        "tempo_limite_segundos": 3600, "concluido_em": "2026-01-01T11:00:00+00:00",
        "duracao_segundos": 3600, "total_questoes": 10, "questoes_respondidas": 10,
        "respostas_corretas": 8, "percentual_acerto": 80, "nota_estimada": 800,
    }])

    with patch("routers.simulados.supabase_admin", fake):
        tentativa = simulados._buscar_tentativa(TENTATIVA_ID, USUARIO_ID)

    assert tentativa["status"] == "concluida"


def test_expirar_se_necessario_finaliza_tentativa_vencida():
    fake = FakeSupabase()
    iniciado_em = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
    tentativa = {
        "id": TENTATIVA_ID, "usuario_id": USUARIO_ID, "modelo_simulado_id": MODELO_ID,
        "status": "em_andamento", "iniciado_em": iniciado_em, "tempo_limite_segundos": 3600,
    }

    fake.table("questoes_sessao_simulado").execute.return_value = query_result(data=[
        {"questao_id": QUESTAO_1, "area": "matematica"},
        {"questao_id": QUESTAO_2, "area": "matematica"},
    ])
    fake.table("tentativas_questoes").execute.return_value = query_result(data=[
        {"questao_id": QUESTAO_1, "acertou": True},
    ])
    fake.table("sessoes_simulado").execute.side_effect = [
        query_result(data=[{"id": TENTATIVA_ID}]),  # update em _finalizar_tentativa
        query_result(data=[{  # _buscar_tentativa de novo, após finalizar
            "id": TENTATIVA_ID, "usuario_id": USUARIO_ID, "modelo_simulado_id": MODELO_ID,
            "status": "expirada", "iniciado_em": iniciado_em, "tempo_limite_segundos": 3600,
            "concluido_em": datetime.now(timezone.utc).isoformat(), "duracao_segundos": 3600,
            "total_questoes": 2, "questoes_respondidas": 1, "respostas_corretas": 1,
            "percentual_acerto": 100, "nota_estimada": 1000,
        }]),
    ]
    fake.table("resultados_area_simulado").execute.return_value = query_result(data=[{"id": str(uuid4())}])

    with patch("routers.simulados.supabase_admin", fake), \
         patch("routers.simulados.conceder_xp_e_atividade"), \
         patch("routers.simulados.registrar_evento_gamificacao"):
        resultado = simulados._expirar_se_necessario(tentativa, USUARIO_ID)

    assert resultado["status"] == "expirada"
    fake.table("sessoes_simulado").update.assert_called_once()
    payload = fake.table("sessoes_simulado").update.call_args[0][0]
    assert payload["status"] == "expirada"
    assert payload["duracao_segundos"] == 3600  # limitado ao tempo_limite_segundos


def test_expirar_se_necessario_nao_mexe_em_tentativa_dentro_do_prazo():
    fake = FakeSupabase()
    tentativa = {
        "id": TENTATIVA_ID, "status": "em_andamento",
        "iniciado_em": datetime.now(timezone.utc).isoformat(), "tempo_limite_segundos": 3600,
    }

    with patch("routers.simulados.supabase_admin", fake):
        resultado = simulados._expirar_se_necessario(tentativa, USUARIO_ID)

    assert resultado is tentativa
    fake.table("sessoes_simulado").update.assert_not_called()


def test_responder_tentativa_ja_finalizada_retorna_409():
    fake = FakeSupabase()
    fake.table("sessoes_simulado").execute.return_value = query_result(data=[{
        "id": TENTATIVA_ID, "usuario_id": USUARIO_ID, "modelo_simulado_id": MODELO_ID,
        "status": "concluida", "iniciado_em": datetime.now(timezone.utc).isoformat(),
        "tempo_limite_segundos": 3600, "concluido_em": datetime.now(timezone.utc).isoformat(),
        "duracao_segundos": 100, "total_questoes": 2, "questoes_respondidas": 2,
        "respostas_corretas": 1, "percentual_acerto": 50, "nota_estimada": 500,
    }])

    payload = simulados.ResponderTentativaPayload(questao_id=QUESTAO_1, alternativa_id="a")

    with patch("routers.simulados.supabase_admin", fake):
        try:
            simulados.responder_tentativa(tentativa_id=TENTATIVA_ID, dados=payload, usuario_atual=_UsuarioFake())
            assert False, "deveria levantar HTTPException"
        except Exception as erro:
            assert getattr(erro, "status_code", None) == 409


def test_selecionar_questoes_tentativa_respeita_distribuicao_por_area():
    fake = FakeSupabase()
    modelo = {"id": MODELO_ID, "tipo_prova_id": None, "total_questoes": None}

    fake.table("sessoes_simulado").execute.return_value = query_result(data=[])  # sem tentativa anterior
    fake.table("modelos_simulado_areas").execute.return_value = query_result(data=[
        {"area": "matematica", "quantidade_questoes": 2},
        {"area": "humanas", "quantidade_questoes": 1},
    ])
    fake.table("materias").execute.return_value = query_result(data=[
        {"id": MATERIA_MAT_ID, "slug": "matematica", "nome": "Matemática", "cor": "purple", "area": "matematica"},
        {"id": MATERIA_HIST_ID, "slug": "historia", "nome": "História", "cor": "gold", "area": "humanas"},
    ])
    fake.table("questoes").execute.side_effect = [
        query_result(data=[{"id": f"mat-{i}"} for i in range(5)]),   # pool matemática
        query_result(data=[{"id": f"hist-{i}"} for i in range(5)]),  # pool humanas
    ]

    with patch("routers.simulados.supabase_admin", fake):
        selecionadas = simulados._selecionar_questoes_tentativa(modelo, USUARIO_ID)

    assert len(selecionadas) == 3
    areas = [s["area"] for s in selecionadas]
    assert areas.count("matematica") == 2
    assert areas.count("humanas") == 1
    numeros = sorted(s["numero"] for s in selecionadas)
    assert numeros == [1, 2, 3]


def test_selecionar_questoes_tentativa_422_quando_area_sem_questoes():
    fake = FakeSupabase()
    modelo = {"id": MODELO_ID, "tipo_prova_id": None, "total_questoes": None}

    fake.table("sessoes_simulado").execute.return_value = query_result(data=[])
    fake.table("modelos_simulado_areas").execute.return_value = query_result(data=[
        {"area": "redacao", "quantidade_questoes": 1},
    ])
    fake.table("materias").execute.return_value = query_result(data=[])  # nenhuma matéria de redação cadastrada

    with patch("routers.simulados.supabase_admin", fake):
        try:
            simulados._selecionar_questoes_tentativa(modelo, USUARIO_ID)
            assert False, "deveria levantar HTTPException"
        except Exception as erro:
            assert getattr(erro, "status_code", None) == 422
