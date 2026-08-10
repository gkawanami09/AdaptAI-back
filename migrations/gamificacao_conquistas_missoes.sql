-- Migração para o sistema interno de gamificação (conquistas + missões).
-- Executar manualmente no Supabase (SQL editor).

-- 1) slug único em conquistas/missoes — necessário para seed idempotente
-- (rodar a migration de novo não pode duplicar linha).
ALTER TABLE public.conquistas ADD COLUMN IF NOT EXISTS slug text;
ALTER TABLE public.missoes ADD COLUMN IF NOT EXISTS slug text;

UPDATE public.conquistas SET slug = 'primeira-semana' WHERE titulo = 'Primeira Semana' AND slug IS NULL;
UPDATE public.conquistas SET slug = '100-questoes' WHERE titulo = '100 Questões' AND slug IS NULL;
UPDATE public.conquistas SET slug = 'primeira-redacao' WHERE titulo = 'Primeira Redação' AND slug IS NULL;
UPDATE public.conquistas SET slug = '7-dias-ofensiva' WHERE titulo = '7 Dias de Ofensiva' AND slug IS NULL;
UPDATE public.conquistas SET slug = 'mestre-enem' WHERE titulo = 'Mestre do ENEM' AND slug IS NULL;
UPDATE public.conquistas SET slug = 'nota-1000' WHERE titulo = 'Nota 1000' AND slug IS NULL;

ALTER TABLE public.conquistas ALTER COLUMN slug SET NOT NULL;

ALTER TABLE public.conquistas DROP CONSTRAINT IF EXISTS conquistas_slug_key;
ALTER TABLE public.conquistas ADD CONSTRAINT conquistas_slug_key UNIQUE (slug);

ALTER TABLE public.missoes DROP CONSTRAINT IF EXISTS missoes_slug_key;
ALTER TABLE public.missoes ADD CONSTRAINT missoes_slug_key UNIQUE (slug);

-- 2) UNIQUE(usuario_id, conquista_id) — garante idempotência do desbloqueio
-- mesmo sob eventos concorrentes/duplicados (o service ainda trata o
-- conflito, mas a garantia real é no banco).
ALTER TABLE public.conquistas_usuario
  DROP CONSTRAINT IF EXISTS conquistas_usuario_usuario_conquista_key;
ALTER TABLE public.conquistas_usuario
  ADD CONSTRAINT conquistas_usuario_usuario_conquista_key UNIQUE (usuario_id, conquista_id);

-- 3) UNIQUE(usuario_id, missao_id, periodo_inicio, periodo_fim) — idem para
-- progresso de missão (evita duas linhas de progresso pro mesmo período).
ALTER TABLE public.progresso_missoes_usuario
  DROP CONSTRAINT IF EXISTS progresso_missoes_usuario_periodo_key;
ALTER TABLE public.progresso_missoes_usuario
  ADD CONSTRAINT progresso_missoes_usuario_periodo_key UNIQUE (usuario_id, missao_id, periodo_inicio, periodo_fim);

-- 4) Novas conquistas (as 3 que faltam do conjunto pedido pelo frontend).
-- tipo_condicao novos, avaliados em services/gamificacao/metricas.py:
--   percentual_acerto_materia — % de acerto na matéria referenciada por materia_id
--   questoes_erradas_revisadas — questões erradas revisadas com sucesso depois
--   minutos_estudo_dia — minutos estudados no melhor dia único
INSERT INTO public.conquistas (slug, titulo, descricao, icone, raridade, xp_recompensa, tipo_condicao, valor_condicao, materia_id, ativo)
SELECT 'matematica-sem-medo', 'Matemática Sem Medo', 'Acerte 80% em Matemática', '🧮', 'epico', 250, 'percentual_acerto_materia', 80, m.id, true
FROM public.materias m WHERE m.slug = 'matematica'
ON CONFLICT (slug) DO NOTHING;

INSERT INTO public.conquistas (slug, titulo, descricao, icone, raridade, xp_recompensa, tipo_condicao, valor_condicao, ativo)
VALUES ('revisor-de-erros', 'Revisor de Erros', 'Revise 50 questões erradas', '🔁', 'incomum', 150, 'questoes_erradas_revisadas', 50, true)
ON CONFLICT (slug) DO NOTHING;

INSERT INTO public.conquistas (slug, titulo, descricao, icone, raridade, xp_recompensa, tipo_condicao, valor_condicao, ativo)
VALUES ('maratonista', 'Maratonista', 'Estude 5h em um único dia', '🏃', 'raro', 200, 'minutos_estudo_dia', 300, true)
ON CONFLICT (slug) DO NOTHING;

-- 5) Missões (tabela ainda vazia). "anotacoes_revisadas" e
-- "plano_semanal_concluido" ficam ativo=false: não existe feature de
-- anotações nem tracking de "% do plano semanal" no projeto ainda, então
-- ficam registradas (histórico/futuro) mas fora da tela do aluno até a
-- funcionalidade de origem existir de verdade — evitar mostrar missão
-- permanentemente travada em 0%.
INSERT INTO public.missoes (slug, titulo, tipo_missao, metrica, valor_alvo, xp_recompensa, ativo) VALUES
  ('resolver-10-questoes', 'Resolver 10 questões', 'diaria', 'questoes_respondidas', 10, 50, true),
  ('assistir-1-aula', 'Assistir 1 aula', 'diaria', 'aulas_concluidas', 1, 30, true),
  ('estudar-1h30', 'Estudar 1h30', 'diaria', 'minutos_estudo', 90, 80, true),
  ('revisar-anotacoes', 'Revisar anotações', 'diaria', 'anotacoes_revisadas', 1, 20, false),
  ('completar-plano-semanal', 'Completar plano semanal', 'semanal', 'plano_semanal_concluido', 7, 200, false),
  ('resolver-50-questoes', 'Resolver 50 questões', 'semanal', 'questoes_respondidas', 50, 150, true),
  ('enviar-1-redacao', 'Enviar 1 redação', 'semanal', 'redacoes_enviadas', 1, 100, true)
ON CONFLICT (slug) DO NOTHING;
