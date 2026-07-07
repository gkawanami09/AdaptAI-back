from supabase import create_client, Client
from config import SUPABASE_URL, SUPABASE_PUBLISHABLE_KEY, SUPABASE_SECRET_KEY

supabase: Client = create_client(
    SUPABASE_URL,
    SUPABASE_PUBLISHABLE_KEY
)

supabase_admin: Client = create_client(
    SUPABASE_URL,
    SUPABASE_SECRET_KEY
)