from pydantic import BaseModel


class ExcluirContaPayload(BaseModel):
    senha: str


class ExcluirContaResponse(BaseModel):
    sucesso: bool
