-- Migração consolidada para o painel administrativo (usuários, dashboard,
-- relatórios, configurações). Substitui admin_painel.sql +
-- admin_configuracoes_tabela.sql (mesmo conteúdo, unificado num único
-- arquivo). Executar manualmente no Supabase (SQL editor).

-- 1) streak_historico — snapshot diário da ofensiva por usuário.
-- `estatisticas_usuario` só guarda ofensiva atual/máxima (um número), não a
-- série ao longo do tempo — o admin precisa de uma série para montar o
-- gráfico de histórico de ofensiva (routers/admin/usuarios.py, endpoint
-- /admin/usuarios/{id}/ofensiva-historico).
CREATE TABLE IF NOT EXISTS public.streak_historico (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  usuario_id uuid NOT NULL REFERENCES public.perfis(id),
  data date NOT NULL,
  ofensiva_dias integer NOT NULL DEFAULT 0 CHECK (ofensiva_dias >= 0),
  criado_em timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT streak_historico_usuario_data_key UNIQUE (usuario_id, data)
);

CREATE INDEX IF NOT EXISTS idx_streak_historico_usuario_data
  ON public.streak_historico (usuario_id, data DESC);

-- 2) log_atividade — log de atividade/auditoria genérico. `usuario_id` é
-- nullable para permitir eventos de sistema (sem usuário associado).
-- `tipo` é o discriminador do evento (ex: 'login', 'questao_respondida',
-- 'conquista_desbloqueada'). Usado hoje pelo histórico de atividades do
-- admin (routers/admin/usuarios.py) e pelas "atividades recentes" do
-- dashboard; deixado genérico o bastante para telemetria futura sem
-- precisar de nova tabela.
CREATE TABLE IF NOT EXISTS public.log_atividade (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  usuario_id uuid REFERENCES public.perfis(id),
  tipo text NOT NULL,
  descricao text,
  metadata jsonb,
  criado_em timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_log_atividade_usuario_criado
  ON public.log_atividade (usuario_id, criado_em DESC);

-- 3) acoes_administrativas — registro de medidas de moderação (suspensão,
-- banimento, reset de ofensiva etc). `usuario_id` é o alvo da ação;
-- `administrador_id` é quem executou (nullable pois pode ter sido removido
-- ou a ação pode ter vindo de um processo automático).
CREATE TABLE IF NOT EXISTS public.acoes_administrativas (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  usuario_id uuid NOT NULL REFERENCES public.perfis(id),
  administrador_id uuid REFERENCES public.perfis(id),
  tipo text NOT NULL,
  motivo text,
  duracao_dias integer,
  criado_em timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_acoes_administrativas_usuario_criado
  ON public.acoes_administrativas (usuario_id, criado_em DESC);

-- 4) configuracoes — tabela chave/valor para configurações globais do painel
-- admin (gerais, autenticacao, conteudo, ia, notificacoes, integracoes).
-- Substitui a persistência anterior em arquivo JSON local
-- (routers/admin/configuracoes.py).
CREATE TABLE IF NOT EXISTS public.configuracoes (
  chave text PRIMARY KEY,
  valor jsonb NOT NULL,
  atualizado_em timestamptz NOT NULL DEFAULT now()
);
