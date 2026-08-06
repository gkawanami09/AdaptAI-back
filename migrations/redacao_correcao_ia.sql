-- Migração para persistir o resultado da correção (motor Python + IA).
-- Executar manualmente no Supabase (SQL editor).

ALTER TABLE public.redacoes_enviadas
  ADD COLUMN IF NOT EXISTS analise_ia jsonb;

COMMENT ON COLUMN public.redacoes_enviadas.analise_ia IS
  'Payload completo pronto para GET /aluno/redacao/envios/{id}: notaTotal, statusLabel, competencias, insights, pontosMelhoria, repertoriosSugeridos, resumoAda.';
