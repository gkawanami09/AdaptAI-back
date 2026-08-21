-- Migração para geração assíncrona de listas de questões via IA
-- (POST /aluno/banco-questoes/listas/gerar-ia + GET /aluno/banco-questoes/geracoes/{id}).
-- Executar manualmente no Supabase (SQL editor).

-- Uma linha por pedido de geração. O request devolve o id imediatamente
-- (status "gerando") e a geração roda em background (FastAPI BackgroundTasks);
-- o frontend faz polling em GET /geracoes/{id} até status virar "concluido"/"erro".
-- Segue a mesma convenção de status_geracao usada em planos_estudo
-- (migrations/plano_estudos_wizard.sql) por consistência.
CREATE TABLE IF NOT EXISTS public.geracoes_ia_listas (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  usuario_id uuid NOT NULL,
  status text NOT NULL DEFAULT 'gerando'
    CHECK (status = ANY (ARRAY['gerando'::text, 'concluido'::text, 'erro'::text])),
  parametros jsonb NOT NULL DEFAULT '{}'::jsonb,
  lista_questoes_id uuid,
  mensagem_erro text,
  criado_em timestamp with time zone NOT NULL DEFAULT now(),
  atualizado_em timestamp with time zone NOT NULL DEFAULT now(),
  CONSTRAINT geracoes_ia_listas_pkey PRIMARY KEY (id),
  CONSTRAINT geracoes_ia_listas_usuario_id_fkey
    FOREIGN KEY (usuario_id) REFERENCES public.perfis(id) ON DELETE CASCADE,
  CONSTRAINT geracoes_ia_listas_lista_questoes_id_fkey
    FOREIGN KEY (lista_questoes_id) REFERENCES public.listas_questoes(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_geracoes_ia_listas_usuario_id
  ON public.geracoes_ia_listas (usuario_id);

-- Usado pelo controle de cota (N gerações por usuário por dia).
CREATE INDEX IF NOT EXISTS idx_geracoes_ia_listas_usuario_criado_em
  ON public.geracoes_ia_listas (usuario_id, criado_em);
