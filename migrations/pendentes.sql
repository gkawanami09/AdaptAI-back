-- Migrações pendentes de aplicação manual no Supabase (SQL editor).
-- Combina as migrations mais recentes ainda não rodadas no banco.

-- =====================================================================
-- 1) Sessões de plano de estudos do tipo "questões" agora referenciam
--    a lista de questões real utilizada, assim como já é feito para aula_id.
--    (era migrations/plano_estudos_sessoes_lista_questoes.sql)
-- =====================================================================

ALTER TABLE public.planos_estudo_sessoes
  ADD COLUMN IF NOT EXISTS lista_questoes_id uuid;

ALTER TABLE public.planos_estudo_sessoes
  DROP CONSTRAINT IF EXISTS planos_estudo_sessoes_lista_questoes_id_fkey;

ALTER TABLE public.planos_estudo_sessoes
  ADD CONSTRAINT planos_estudo_sessoes_lista_questoes_id_fkey
  FOREIGN KEY (lista_questoes_id) REFERENCES public.listas_questoes(id);

-- =====================================================================
-- 2) Recuperação de senha e preferências de uso de dados pela IA.
--    (era migrations/configuracoes_aluno_conta_seguranca.sql)
-- =====================================================================

-- Tokens de recuperação de senha (mesmo padrão de email_verificacoes:
-- guarda só o hash do token, uso único, expiração curta).
CREATE TABLE IF NOT EXISTS public.recuperacao_senha_tokens (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  user_id uuid NOT NULL REFERENCES auth.users(id),
  email text NOT NULL,
  token_hash text NOT NULL,
  usado boolean NOT NULL DEFAULT false,
  expira_em timestamp with time zone NOT NULL,
  criado_em timestamp with time zone NOT NULL DEFAULT now(),
  CONSTRAINT recuperacao_senha_tokens_token_hash_key UNIQUE (token_hash)
);

CREATE INDEX IF NOT EXISTS idx_recuperacao_senha_tokens_email
  ON public.recuperacao_senha_tokens (email, criado_em DESC);

-- Preferência do aluno sobre quais categorias de dados a IA pode utilizar
-- para gerar recomendações/insights (tela de transparência de dados).
CREATE TABLE IF NOT EXISTS public.preferencias_dados_ia (
  usuario_id uuid NOT NULL REFERENCES public.perfis(id),
  categoria_id text NOT NULL,
  utilizado boolean NOT NULL DEFAULT true,
  atualizado_em timestamp with time zone NOT NULL DEFAULT now(),
  CONSTRAINT preferencias_dados_ia_pkey PRIMARY KEY (usuario_id, categoria_id)
);

-- =====================================================================
-- 3) Lock otimista para o replanejamento automático do plano de estudos,
--    evitando corrida entre chamadas concorrentes de replanejar_apos_conclusao().
--    (era migrations/plano_estudos_lock_replanejamento.sql)
-- =====================================================================

ALTER TABLE public.planos_estudo
  ADD COLUMN IF NOT EXISTS replanejamento_em_andamento boolean NOT NULL DEFAULT false;

-- =====================================================================
-- 4) Novo contrato de simulados: tentativas com tempo limite, sorteio de
--    questões por área e resultado/revisão persistidos.
--    (era migrations/simulados_tentativas.sql)
-- =====================================================================

ALTER TABLE public.sessoes_simulado
  ADD COLUMN IF NOT EXISTS tempo_limite_segundos integer,
  ADD COLUMN IF NOT EXISTS questoes_respondidas integer NOT NULL DEFAULT 0;

ALTER TABLE public.sessoes_simulado DROP CONSTRAINT IF EXISTS sessoes_simulado_status_check;
ALTER TABLE public.sessoes_simulado ADD CONSTRAINT sessoes_simulado_status_check
  CHECK (status = ANY (ARRAY[
    'em_andamento'::text, 'concluido'::text, 'concluida'::text,
    'abandonado'::text, 'expirada'::text, 'cancelada'::text
  ]));

CREATE TABLE IF NOT EXISTS public.modelos_simulado_areas (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  modelo_simulado_id uuid NOT NULL,
  area text NOT NULL CHECK (area = ANY (ARRAY['matematica'::text, 'natureza'::text, 'humanas'::text, 'linguagens'::text, 'redacao'::text])),
  quantidade_questoes integer NOT NULL CHECK (quantidade_questoes > 0),
  CONSTRAINT modelos_simulado_areas_pkey PRIMARY KEY (id),
  CONSTRAINT modelos_simulado_areas_modelo_fkey FOREIGN KEY (modelo_simulado_id) REFERENCES public.modelos_simulado(id) ON DELETE CASCADE,
  CONSTRAINT modelos_simulado_areas_unicidade UNIQUE (modelo_simulado_id, area)
);

ALTER TABLE public.resultados_area_simulado
  ADD COLUMN IF NOT EXISTS respondidas integer NOT NULL DEFAULT 0;
