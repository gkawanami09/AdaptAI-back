-- Questões/listas/simulado de teste, para validar a adaptação do plano de
-- estudos a erros e acertos (services/plano_estudos_wizard_service.py:
-- _desempenho_por_materia_e_topico, usado por deterministic_generator.py).
-- Executar manualmente no Supabase (SQL editor).
--
-- Só cadastra CATÁLOGO (questões, alternativas, listas, modelo de simulado)
-- — nada por usuário. Os acertos/erros de verdade (tentativas_questoes),
-- que são o que o gerador de plano realmente lê, só existem depois que
-- você responder essas questões pelo app (tela de lista de questões ou de
-- simulado), logado como o usuário de teste.
--
-- Limiares relevantes para o teste (services/plano_estudos/deterministic_generator.py):
--   MIN_TENTATIVAS_CONFIAVEL = 5  -> precisa responder pelo menos 5 questões
--     da mesma matéria para a taxa de erro dela contar pra alguma coisa.
--   LIMIAR_MATERIA_FRACA / LIMIAR_TOPICO_FRACO = 0.4  -> taxa de erro >= 40%
--     é o que classifica a matéria/tópico como "fraca" (ganha reforço extra
--     no plano — services/plano_estudos_wizard_service.py:_reforco_materias_fracas).
-- Cada matéria de teste tem 6 questões — responder todas (>=5 tentativas) e
-- errar pelo menos 3 (>=50% de erro) deve ser o suficiente pra ver a matéria
-- subir de prioridade e ganhar reforço no próximo replanejamento.
--
-- Todo conteúdo aqui é placeholder — títulos prefixados com "[TESTE]".

-- 1) 6 questões de teste por matéria (2 fáceis, 2 médias, 2 difíceis), com
-- 5 alternativas (A-E) cada. Usa o mesmo tópico já vinculado nas aulas de
-- teste (migrations/seed_aulas_teste.sql) quando existir.
WITH alvo AS (
  SELECT m.id AS materia_id, m.nome AS materia_nome, t.topico_id, serie.indice, serie.dificuldade
  FROM public.materias m
  LEFT JOIN public.topicos t ON t.materia_id = m.id AND t.slug = CASE m.slug
    WHEN 'matematica' THEN 'funcoes'
    WHEN 'fisica' THEN 'cinematica'
    WHEN 'quimica' THEN 'estequiometria'
    WHEN 'biologia' THEN 'ecologia'
    WHEN 'historia' THEN 'revolucao-industrial'
    WHEN 'redacao' THEN 'repertorio-sociocultural'
    ELSE NULL
  END
  CROSS JOIN (VALUES (1, 'facil'), (2, 'facil'), (3, 'medio'), (4, 'medio'), (5, 'dificil'), (6, 'dificil'))
    AS serie(indice, dificuldade)
  WHERE m.slug IN ('matematica', 'fisica', 'quimica', 'biologia', 'historia', 'geografia', 'portugues', 'redacao', 'ingles')
),
novas AS (
  INSERT INTO public.questoes (tipo_prova_id, materia_id, topico_id, dificuldade, enunciado, explicacao, ativo)
  SELECT
    (SELECT id FROM public.tipos_prova WHERE slug = 'enem' LIMIT 1),
    alvo.materia_id,
    alvo.topico_id,
    alvo.dificuldade,
    '[TESTE] ' || alvo.materia_nome || ' — questão ' || alvo.indice || ' (' || alvo.dificuldade || ')',
    'Questão de teste gerada para validar a adaptação do plano de estudos a erros/acertos.',
    true
  FROM alvo
  WHERE NOT EXISTS (
    SELECT 1 FROM public.questoes q
    WHERE q.materia_id = alvo.materia_id
      AND q.enunciado = '[TESTE] ' || alvo.materia_nome || ' — questão ' || alvo.indice || ' (' || alvo.dificuldade || ')'
  )
  RETURNING id
)
INSERT INTO public.alternativas_questao (questao_id, letra, conteudo, ordem)
SELECT novas.id, letras.letra, '[TESTE] Alternativa ' || letras.letra, letras.ordem
FROM novas
CROSS JOIN (VALUES ('A', 0), ('B', 1), ('C', 2), ('D', 3), ('E', 4)) AS letras(letra, ordem);

-- 2) Alternativa "A" sempre correta nas questões de teste — de propósito,
-- pra facilitar o teste manual: marcar A = acerto, qualquer outra = erro.
UPDATE public.questoes q
SET alternativa_correta = alt.id
FROM public.alternativas_questao alt
WHERE alt.questao_id = q.id
  AND alt.letra = 'A'
  AND q.enunciado LIKE '[TESTE] %'
  AND q.alternativa_correta IS NULL;

-- 3) Uma lista de questões "fixa" por matéria, agrupando as 6 questões de
-- teste dela — é o que aparece na tela de prática de questões do aluno.
INSERT INTO public.listas_questoes (titulo, descricao, tipo_prova_id, materia_id, tipo_lista, slug)
SELECT
  '[TESTE] Prática de ' || m.nome,
  'Lista de teste gerada para validar a adaptação do plano de estudos a erros/acertos.',
  (SELECT id FROM public.tipos_prova WHERE slug = 'enem' LIMIT 1),
  m.id,
  'fixa',
  'teste-lista-' || m.slug
FROM public.materias m
WHERE m.slug IN ('matematica', 'fisica', 'quimica', 'biologia', 'historia', 'geografia', 'portugues', 'redacao', 'ingles')
  AND NOT EXISTS (SELECT 1 FROM public.listas_questoes l WHERE l.slug = 'teste-lista-' || m.slug);

INSERT INTO public.itens_lista_questoes (lista_questoes_id, questao_id, ordem)
SELECT l.id, q.id, row_number() OVER (PARTITION BY l.id ORDER BY q.criado_em)
FROM public.listas_questoes l
JOIN public.questoes q ON q.materia_id = l.materia_id AND q.enunciado LIKE '[TESTE] %'
WHERE l.slug LIKE 'teste-lista-%'
  AND NOT EXISTS (
    SELECT 1 FROM public.itens_lista_questoes i
    WHERE i.lista_questoes_id = l.id AND i.questao_id = q.id
  );

-- 4) Um modelo de simulado completo de teste, pra também poder testar o
-- fluxo de simulado inteiro (routers/simulados.py monta o pool a partir de
-- `questoes` com o mesmo tipo_prova_id do modelo).
INSERT INTO public.modelos_simulado (tipo_prova_id, titulo, descricao, tipo_modelo, total_questoes, duracao_minutos, ativo, slug)
SELECT
  (SELECT id FROM public.tipos_prova WHERE slug = 'enem' LIMIT 1),
  '[TESTE] Simulado ENEM completo',
  'Simulado de teste gerado para validar o fluxo completo e o resultado por área.',
  'completo',
  20,
  180,
  true,
  'teste-simulado-enem'
WHERE NOT EXISTS (SELECT 1 FROM public.modelos_simulado ms WHERE ms.slug = 'teste-simulado-enem');
