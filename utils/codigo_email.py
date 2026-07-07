import hashlib
import hmac
import os
import random
from datetime import datetime, timedelta, timezone


def gerar_codigo_email() -> str:
    return str(random.randint(100000, 999999))


def gerar_hash_codigo(codigo: str) -> str:
    codigo_back = os.getenv("EMAIL_CODE_SECRET")

    return hmac.new(
        codigo_back.encode(),
        codigo.encode(),
        hashlib.sha256
    ).hexdigest()


def codigo_expiracao_minutos(minutos: int = 10):
    return datetime.now(timezone.utc) + timedelta(minutes=minutos)