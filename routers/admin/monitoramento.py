from fastapi import APIRouter, Depends
from utils.autenticacao import exigir_administrador
from services.monitoramento import monitor

router = APIRouter(
    prefix='/admin/monitoramento',
    tags=['Admin - Monitoramento'],
    dependencies=[Depends(exigir_administrador)]
)


@router.get('')
def obter_monitoramento():
    return {
        "sucesso": True,
        **monitor.resumo(),
    }
