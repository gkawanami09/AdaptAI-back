-- Suporte aos requisitos novos da área administrativa: descrição de
-- matéria e a entidade "Área do Conhecimento" (hoje só uma lista fixa de
-- 5 valores usada no campo `area` de `materias`, sem CRUD próprio).
-- Executar manualmente no Supabase (SQL editor).

ALTER TABLE public.materias
  ADD COLUMN IF NOT EXISTS descricao text;

-- Entidade nova e independente — não substitui nem referencia o campo
-- `area` (text) já usado em `materias`/`questoes_sessao_simulado`/
-- `resultados_area_simulado`/`modelos_simulado_areas`, que continua sendo
-- o enum fixo de 5 valores usado nas regras de negócio existentes
-- (sorteio de simulado, cálculo de desempenho por área etc.). Essa
-- migração maior de acoplar tudo isso à tabela nova fica fora do escopo
-- pedido aqui.
CREATE TABLE IF NOT EXISTS public.areas_conhecimento (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  nome text NOT NULL,
  slug text NOT NULL UNIQUE,
  descricao text,
  ativo boolean NOT NULL DEFAULT true,
  criado_em timestamp with time zone NOT NULL DEFAULT now(),
  CONSTRAINT areas_conhecimento_pkey PRIMARY KEY (id)
);
