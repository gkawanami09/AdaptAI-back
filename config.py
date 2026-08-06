import os
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_PUBLISHABLE_KEY = os.getenv("SUPABASE_PUBLISHABLE_KEY")
SUPABASE_SECRET_KEY = os.getenv("SUPABASE_SECRET_KEY")


def _comma_separated_env(name: str, default: list[str]) -> list[str]:
    value = os.getenv(name)
    if not value:
        return default

    return [item.strip().rstrip("/") for item in value.split(",") if item.strip()]


CORS_ORIGINS = _comma_separated_env(
    "CORS_ORIGINS",
    [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
)

# Configuração da camada de IA (services/ai/). AI_PROVIDER seleciona o
# mecanismo de inferência (ollama | openai_compatible) — o modelo em si
# (Qwen, Gemma, Llama, GPT...) é definido apenas por AI_MODEL, sem
# precisar trocar de provider.
AI_PROVIDER = os.getenv("AI_PROVIDER", "ollama")
AI_BASE_URL = os.getenv("AI_BASE_URL", "http://localhost:11434")
AI_MODEL = os.getenv("AI_MODEL", "qwen2.5:14b")
AI_TIMEOUT = float(os.getenv("AI_TIMEOUT", "60"))
AI_MAX_TOKENS = int(os.getenv("AI_MAX_TOKENS", "2000"))
AI_TEMPERATURE = float(os.getenv("AI_TEMPERATURE", "0.3"))
