from unittest.mock import MagicMock, patch

from services.plano_estudos_wizard_service import PlanoEstudosWizardService


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
