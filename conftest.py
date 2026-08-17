import os

# database.py cria clientes reais do Supabase na hora do import
# (create_client(SUPABASE_URL, ...)), o que quebra a coleta dos testes em
# qualquer ambiente sem um .env com credenciais reais — como a CI, que não
# versiona esse arquivo. Os testes nunca usam esses clientes de verdade
# (sempre mockam supabase/supabase_admin via patch), então valores dummy
# bastam pra só permitir o import. setdefault() não sobrescreve um .env
# local já carregado por quem estiver rodando os testes com credenciais
# reais.
os.environ.setdefault("SUPABASE_URL", "http://localhost:54321")
os.environ.setdefault("SUPABASE_PUBLISHABLE_KEY", "test-anon-key")
os.environ.setdefault("SUPABASE_SECRET_KEY", "test-service-key")
