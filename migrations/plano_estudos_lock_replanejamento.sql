-- Lock otimista para o replanejamento automático do plano de estudos.
-- Executar manualmente no Supabase (SQL editor).
--
-- replanejar_apos_conclusao() é acionado por dois endpoints diferentes
-- (conclusão de aula e conclusão de tarefa de questões) e faz um
-- DELETE das tarefas/sessões futuras seguido de INSERT, sem transação.
-- Duas chamadas concorrentes para o mesmo plano (duplo clique, retry,
-- duas abas) podiam gerar tarefas duplicadas ou uma leitura no meio do
-- caminho vendo um dia vazio. Esta coluna serve de lock: só entra no
-- replanejamento quem conseguir virá-la de false para true.

ALTER TABLE public.planos_estudo
  ADD COLUMN IF NOT EXISTS replanejamento_em_andamento boolean NOT NULL DEFAULT false;
