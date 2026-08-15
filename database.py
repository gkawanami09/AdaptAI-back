from supabase import create_client, Client
from supabase.client import ClientOptions
from httpx import Client as HttpxClient, Limits
from config import SUPABASE_URL, SUPABASE_PUBLISHABLE_KEY, SUPABASE_SECRET_KEY

# No Windows, um httpx.Client com pool de conexoes keep-alive compartilhado
# entre threads (FastAPI roda rotas sync no threadpool) causa uma race
# condition no socket non-blocking, gerando WinError 10035 aleatoriamente.
# Desabilitar o keep-alive forca uma conexao nova por requisicao e evita a race.
_no_keepalive_options = ClientOptions(
    httpx_client=HttpxClient(limits=Limits(max_keepalive_connections=0))
)

supabase: Client = create_client(
    SUPABASE_URL,
    SUPABASE_PUBLISHABLE_KEY,
    options=_no_keepalive_options
)

supabase_admin: Client = create_client(
    SUPABASE_URL,
    SUPABASE_SECRET_KEY,
    options=_no_keepalive_options
)