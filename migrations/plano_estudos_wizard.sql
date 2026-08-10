-- Migração para o wizard de criação de plano de estudos (IA).
-- Executar manualmente no Supabase (SQL editor).

ALTER TABLE public.planos_estudo
  ADD COLUMN IF NOT EXISTS provas_selecionadas text[] NOT NULL DEFAULT '{}',
  ADD COLUMN IF NOT EXISTS materias_selecionadas text[] NOT NULL DEFAULT '{}',
  ADD COLUMN IF NOT EXISTS tempo_por_dia_minutos integer CHECK (tempo_por_dia_minutos > 0),
  ADD COLUMN IF NOT EXISTS dias_estudo text[] NOT NULL DEFAULT '{}',
  ADD COLUMN IF NOT EXISTS status_geracao text NOT NULL DEFAULT 'concluido'
    CHECK (status_geracao = ANY (ARRAY['gerando'::text, 'concluido'::text, 'erro'::text])),
  ADD COLUMN IF NOT EXISTS mensagem_erro text;

-- Cronograma gerado pela IA para um plano criado via wizard. Independente
-- de tarefas_estudo (que alimenta o quadro do dia a dia com itens
-- acionáveis já ligados a aula/lista/simulado/tema) — aqui só guardamos
-- as sessões brutas retornadas pela IA (materia + duração + tipo por dia),
-- que o backend recompõe em semanas/dias na leitura.
CREATE TABLE IF NOT EXISTS public.planos_estudo_sessoes (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  plano_estudo_id uuid NOT NULL,
  materia_slug text NOT NULL,
  data_agendada date NOT NULL,
  duracao_minutos integer NOT NULL CHECK (duracao_minutos > 0),
  tipo text NOT NULL,
  ordem integer NOT NULL DEFAULT 0,
  criado_em timestamp with time zone NOT NULL DEFAULT now(),
  CONSTRAINT planos_estudo_sessoes_pkey PRIMARY KEY (id),
  CONSTRAINT planos_estudo_sessoes_plano_estudo_id_fkey
    FOREIGN KEY (plano_estudo_id) REFERENCES public.planos_estudo(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_planos_estudo_sessoes_plano_id
  ON public.planos_estudo_sessoes (plano_estudo_id);
