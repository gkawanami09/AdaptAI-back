import json
import re

from pydantic import BaseModel, ValidationError

from services.ai.base import AIRespostaInvalidaError

_BLOCO_JSON = re.compile(r"\{.*\}", re.DOTALL)
_INICIO_ARRAY = re.compile(r'"(\w+)"\s*:\s*\[')


def _recuperar_array_truncado(conteudo: str) -> dict | None:
    """Quando o modelo estoura o orçamento de tokens no meio de um array de
    itens (ex.: questões geradas em lote — ver services/ai/prompts/questoes.py),
    o JSON vem cortado no meio de um objeto e json.loads falha por inteiro,
    descartando itens já completos e válidos junto com o incompleto.

    Acha o primeiro array `"chave": [...]` na resposta e devolve só os
    objetos `{...}` completos e balanceados encontrados nele, descartando o
    (no máximo um) objeto incompleto no final. Não tenta consertar nada
    dentro de um objeto — só decide onde cortar a lista.
    """
    match_array = _INICIO_ARRAY.search(conteudo)
    if not match_array:
        return None

    chave = match_array.group(1)
    cursor = match_array.end()

    objetos: list[str] = []
    profundidade = 0
    inicio_objeto = None
    dentro_de_string = False
    escapando = False

    for i in range(cursor, len(conteudo)):
        char = conteudo[i]

        if dentro_de_string:
            if escapando:
                escapando = False
            elif char == "\\":
                escapando = True
            elif char == '"':
                dentro_de_string = False
            continue

        if char == '"':
            dentro_de_string = True
        elif char == "{":
            if profundidade == 0:
                inicio_objeto = i
            profundidade += 1
        elif char == "}":
            profundidade -= 1
            if profundidade == 0 and inicio_objeto is not None:
                objetos.append(conteudo[inicio_objeto : i + 1])
                inicio_objeto = None
        elif char == "]" and profundidade == 0:
            break

    if not objetos:
        return None

    itens_validos = []
    for bruto in objetos:
        try:
            itens_validos.append(json.loads(bruto))
        except json.JSONDecodeError:
            continue

    if not itens_validos:
        return None

    return {chave: itens_validos}


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
    except json.JSONDecodeError as erro_json:
        dados = _recuperar_array_truncado(match.group(0))
        if dados is None:
            raise AIRespostaInvalidaError(f"JSON inválido retornado pela IA: {erro_json}") from erro_json

    try:
        return schema.model_validate(dados)
    except ValidationError as erro:
        raise AIRespostaInvalidaError(
            f"JSON da IA não corresponde ao schema esperado: {erro}. Recebido: {dados!r}"
        ) from erro
