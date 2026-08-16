from pydantic import BaseModel, Field

class LoginUsuario(BaseModel):
    email: str
    senha: str = Field(min_length=6)
    
class ConfirmaEmail(BaseModel):
    email: str
    codigo: str

class EsqueciSenhaPayload(BaseModel):
    email: str

class RedefinirSenhaPayload(BaseModel):
    token: str
    nova_senha: str