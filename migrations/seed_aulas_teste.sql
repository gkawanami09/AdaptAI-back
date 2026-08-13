-- Aulas de teste para destravar a geração de plano de estudos.
-- Executar manualmente no Supabase (SQL editor).
--
-- Contexto: o gerador determinístico de plano de estudos
-- (services/plano_estudos/deterministic_generator.py) só agenda sessões a
-- partir da tabela `aulas`. Praticamente nenhuma matéria tinha aula
-- cadastrada (só "ciência da computação" tinha 1), então todo plano gerado
-- pelo onboarding saía vazio — sem tarefas, todo dia aparecendo como
-- "Descanso" na tela do aluno. Esta migração cadastra 1 aula mínima por
-- matéria usada no onboarding, para que o gerador tenha o que agendar.
--
-- Todo conteúdo aqui é placeholder — títulos prefixados com "[TESTE]" para
-- ficar óbvio que precisa ser substituído por conteúdo real depois.

-- 1) Uma aula de teste por matéria, vinculada ao tópico existente quando
-- houver (matemática, física, química, biologia, história, redação); as
-- que ainda não têm nenhum tópico cadastrado (geografia, português, inglês)
-- ficam com topico_id nulo — coluna é nullable, confirmado.
INSERT INTO public.aulas (materia_id, topico_id, titulo, slug, resumo, dificuldade, ativo, ordem)
SELECT m.id, t.topico_id, '[TESTE] Introdução a ' || m.nome, 'teste-' || m.slug, 'Aula de teste gerada para destravar o plano de estudos.', 'basico', true, 1
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
WHERE m.slug IN ('matematica', 'fisica', 'quimica', 'biologia', 'historia', 'geografia', 'portugues', 'redacao', 'ingles')
  AND NOT EXISTS (
    SELECT 1 FROM public.aulas a WHERE a.slug = 'teste-' || m.slug
  );

-- 2) Um conteúdo do tipo "texto" por aula de teste, com duração — é o que
-- o gerador soma para calcular o tempo da sessão (aulas_conteudo.duracao).
-- `id` e `atualizado_em` não têm default no banco — precisam vir explícitos.
INSERT INTO public.aulas_conteudo (id, aula_id, ordem, id_tipo, duracao, ativo, atualizado_em)
SELECT gen_random_uuid(), a.id, 1, tipo.id, 20, true, now()
FROM public.aulas a
CROSS JOIN (SELECT id FROM public.aulas_tipos WHERE nome = 'texto' LIMIT 1) tipo
WHERE a.slug LIKE 'teste-%'
  AND NOT EXISTS (
    SELECT 1 FROM public.aulas_conteudo ac WHERE ac.aula_id = a.id
  );

-- 3) Corpo de texto mínimo, para a aula não ficar vazia se o aluno abrir.
-- `atualizado_em` também não tem default aqui.
INSERT INTO public.aulas_texto (aulas_conteudo_id, titulo, descricao, atualizado_em)
SELECT ac.id, a.titulo, 'Conteúdo de teste — substituir por material real.', now()
FROM public.aulas_conteudo ac
JOIN public.aulas a ON a.id = ac.aula_id
WHERE a.slug LIKE 'teste-%'
  AND NOT EXISTS (
    SELECT 1 FROM public.aulas_texto at2 WHERE at2.aulas_conteudo_id = ac.id
  );
