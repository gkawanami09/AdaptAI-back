-- Migração para o módulo de Redação.
-- Adiciona campos faltantes em temas_redacao e cria a tabela de competências.
-- Executar manualmente no Supabase (SQL editor).

CREATE EXTENSION IF NOT EXISTS unaccent;

ALTER TABLE public.temas_redacao
  ADD COLUMN IF NOT EXISTS slug text,
  ADD COLUMN IF NOT EXISTS tag text,
  ADD COLUMN IF NOT EXISTS tag_cor text
    CHECK (tag_cor = ANY (ARRAY['purple'::text, 'green'::text, 'blue'::text, 'teal'::text, 'gold'::text, 'red'::text, 'gray'::text])),
  ADD COLUMN IF NOT EXISTS dica_ada text;

-- Backfill de linhas existentes (slug derivado do título, tag/tag_cor com valor padrão).
UPDATE public.temas_redacao
SET slug = trim(both '-' from regexp_replace(lower(unaccent(titulo)), '[^a-z0-9]+', '-', 'g')) || '-' || substr(id::text, 1, 8)
WHERE slug IS NULL;

UPDATE public.temas_redacao
SET tag = 'Tema ENEM', tag_cor = 'purple'
WHERE tag IS NULL OR tag_cor IS NULL;

ALTER TABLE public.temas_redacao
  ALTER COLUMN slug SET NOT NULL,
  ALTER COLUMN tag SET NOT NULL,
  ALTER COLUMN tag_cor SET NOT NULL;

ALTER TABLE public.temas_redacao
  ADD CONSTRAINT temas_redacao_slug_key UNIQUE (slug);

-- O status inicial de um envio passa a ser 'pendente' (aguardando correção por IA).
-- Valores futuros: 'corrigindo', 'corrigida', 'erro'.
ALTER TABLE public.redacoes_enviadas
  DROP CONSTRAINT IF EXISTS redacoes_enviadas_status_check;

ALTER TABLE public.redacoes_enviadas
  ALTER COLUMN status SET DEFAULT 'pendente';

ALTER TABLE public.redacoes_enviadas
  ADD CONSTRAINT redacoes_enviadas_status_check
  CHECK (status = ANY (ARRAY['pendente'::text, 'corrigindo'::text, 'corrigida'::text, 'erro'::text, 'rascunho'::text, 'enviada'::text]));

CREATE TABLE IF NOT EXISTS public.competencias_redacao (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  tema_redacao_id uuid NOT NULL,
  number integer NOT NULL CHECK (number >= 1 AND number <= 5),
  title text NOT NULL,
  description text NOT NULL,
  color text NOT NULL CHECK (color = ANY (ARRAY['blue'::text, 'teal'::text, 'purple'::text, 'gold'::text, 'red'::text])),
  criado_em timestamp with time zone NOT NULL DEFAULT now(),
  CONSTRAINT competencias_redacao_pkey PRIMARY KEY (id),
  CONSTRAINT competencias_redacao_tema_redacao_id_fkey FOREIGN KEY (tema_redacao_id) REFERENCES public.temas_redacao(id)
);
