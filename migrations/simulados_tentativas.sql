-- Suporte ao novo contrato de simulados (tentativas com tempo limite,
-- distribuição de questões por área, resultado/revisão persistidos).
-- Executar manualmente no Supabase (SQL editor).

-- 1) `sessoes_simulado` ganha o tempo limite da tentativa (pra checar
-- expiração no backend, fonte de verdade do tempo) e a contagem de
-- questões respondidas (pra "não respondidas" na tela de resultado sem
-- precisar recalcular tudo a cada leitura).
ALTER TABLE public.sessoes_simulado
  ADD COLUMN IF NOT EXISTS tempo_limite_segundos integer,
  ADD COLUMN IF NOT EXISTS questoes_respondidas integer NOT NULL DEFAULT 0;

-- Amplia o CHECK de status pra cobrir "concluida"/"expirada"/"cancelada"
-- (nomenclatura do novo contrato) sem quebrar linhas antigas gravadas com
-- "concluido"/"abandonado".
ALTER TABLE public.sessoes_simulado DROP CONSTRAINT IF EXISTS sessoes_simulado_status_check;
ALTER TABLE public.sessoes_simulado ADD CONSTRAINT sessoes_simulado_status_check
  CHECK (status = ANY (ARRAY[
    'em_andamento'::text, 'concluido'::text, 'concluida'::text,
    'abandonado'::text, 'expirada'::text, 'cancelada'::text
  ]));

-- 2) Configuração opcional de quantas questões sortear por área em cada
-- modelo de simulado (ex.: ENEM → linguagens 22, humanas 22, natureza 23,
-- matemática 23). Sem linha configurada pra um modelo, o backend cai no
-- sorteio "achatado" antigo (bate o total_questoes contra o banco inteiro
-- filtrado só por tipo_prova_id).
CREATE TABLE IF NOT EXISTS public.modelos_simulado_areas (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  modelo_simulado_id uuid NOT NULL,
  area text NOT NULL CHECK (area = ANY (ARRAY['matematica'::text, 'natureza'::text, 'humanas'::text, 'linguagens'::text, 'redacao'::text])),
  quantidade_questoes integer NOT NULL CHECK (quantidade_questoes > 0),
  CONSTRAINT modelos_simulado_areas_pkey PRIMARY KEY (id),
  CONSTRAINT modelos_simulado_areas_modelo_fkey FOREIGN KEY (modelo_simulado_id) REFERENCES public.modelos_simulado(id) ON DELETE CASCADE,
  CONSTRAINT modelos_simulado_areas_unicidade UNIQUE (modelo_simulado_id, area)
);

-- 3) `resultados_area_simulado` precisa saber quantas questões daquela
-- área foram de fato respondidas — o contrato pede percentual_acerto por
-- área sobre respondidas, não sobre o total atribuído à área.
ALTER TABLE public.resultados_area_simulado
  ADD COLUMN IF NOT EXISTS respondidas integer NOT NULL DEFAULT 0;
