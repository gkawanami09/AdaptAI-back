-- Migração para o gerador determinístico de plano de estudos.
-- Executar manualmente no Supabase (SQL editor), após plano_estudos_wizard.sql.

-- Data da prova: necessária para calcular a proximidade e priorizar o
-- conteúdo. Sem esse campo não é possível calcular dias_ate_prova.
ALTER TABLE public.tipos_prova
  ADD COLUMN IF NOT EXISTS data_prova date;

-- Cada sessão do cronograma agora referencia a aula real utilizada
-- (quando existir), para o aluno saber exatamente o que estudar.
ALTER TABLE public.planos_estudo_sessoes
  ADD COLUMN IF NOT EXISTS aula_id uuid,
  ADD COLUMN IF NOT EXISTS titulo text;

ALTER TABLE public.planos_estudo_sessoes
  DROP CONSTRAINT IF EXISTS planos_estudo_sessoes_aula_id_fkey;

ALTER TABLE public.planos_estudo_sessoes
  ADD CONSTRAINT planos_estudo_sessoes_aula_id_fkey
  FOREIGN KEY (aula_id) REFERENCES public.aulas(id);
