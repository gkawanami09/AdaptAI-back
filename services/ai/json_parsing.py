import json
import re

from pydantic import BaseModel, ValidationError

from services.ai.base import AIRespostaInvalidaError

_BLOCO_JSON = re.compile(r"\{.*\}", re.DOTALL)


def extrair_e_validar_json(conteudo: str, schema: type[BaseModel]):
    """Extrai o primeiro bloco JSON da resposta do modelo e valida contra
    o schema Pydantic esperado. Modelos às vezes envolvem o JSON em
    texto extra ou blocos de código markdown, mesmo quando instruídos a
    não fazer isso — por isso a extração é tolerante a isso.
    """
    match = _BLOCO_JSON.search(conteudo)
    if not match:
        raise AIRespostaInvalidaError(
            f"Resposta da IA não contém um bloco JSON reconhecível: {conteudo[:200]!r}"
        )

    try:
        dados = json.loads(match.group(0))
    except json.JSONDecodeError as erro:
        raise AIRespostaInvalidaError(f"JSON inválido retornado pela IA: {erro}") from erro

    try:
        return schema.model_validate(dados)
    except ValidationError as erro:
        raise AIRespostaInvalidaError(
            f"JSON da IA não corresponde ao schema esperado: {erro}. Recebido: {dados!r}"
        ) from erro
