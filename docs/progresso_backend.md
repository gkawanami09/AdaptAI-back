# Meu Progresso — Backend

Área do aluno. Rota autenticada via JWT (`Authorization: Bearer <token>`), validada por `pegar_usuario_atual` (`utils/autenticacao.py`). Todos os dados retornados são exclusivos do aluno autenticado — nenhum parâmetro de usuário é aceito.

---

## Endpoint

GET /aluno/progresso

Retorna todos os dados da página "Meu Progresso" em uma única chamada: resumo (meta mensal, horas estudadas, ofensiva, XP), evolução de acertos por matéria, horas estudadas por dia da semana, ranking de matérias, mapa de calor de dias estudados e metas mensais.

### Autenticação

Obrigatória. `401 Unauthorized` se o token estiver ausente ou inválido.

### Request

Sem path params, sem query params, sem payload (GET puro).

### Response

```json
{
  "resumo": {
    "meta_mensal_percentual": 62,
    "horas_estudadas": "47h",
    "ofensiva_dias": 8,
    "xp_total": 4820
  },
  "evolucao_acertos": {
    "categories": ["Sem 1", "Sem 2", "Sem 3", "Sem 4"],
    "series": [
      { "name": "Matemática", "color": "blue", "values": [58, 62, 65, 70] }
    ]
  },
  "horas_por_dia": [
    { "label": "Seg", "value": 2.6 }
  ],
  "ranking_materias": [
    { "label": "Biologia", "percent": 78, "color": "green" }
  ],
  "heatmap": {
    "weekday_labels": ["D", "S", "T", "Q", "Q", "S", "S"],
    "weeks": [[0, 3, 3, 0, 0, 4, 0]]
  },
  "metas_mensais": [
    { "label": "Questões resolvidas", "value": 320, "target": 500, "color": "purple" }
  ]
}
```

### Interfaces TypeScript

Idênticas ao contrato fornecido — não alteradas:

```ts
type ProgressoResumo = {
  meta_mensal_percentual: number
  horas_estudadas: string
  ofensiva_dias: number
  xp_total: number
}

type ProgressoEvolucaoSerie = {
  name: string
  color: 'blue' | 'green' | 'red'
  values: number[]
}

type ProgressoEvolucaoAcertos = {
  categories: string[]
  series: ProgressoEvolucaoSerie[]
}

type ProgressoHorasPorDia = {
  label: string
  value: number
}

type ProgressoRankingMateria = {
  label: string
  percent: number
  color: 'purple' | 'teal' | 'gold' | 'red' | 'blue' | 'green' | 'orange'
}

type ProgressoHeatmap = {
  weekday_labels: string[]
  weeks: number[][]
}

type ProgressoMetaMensal = {
  label: string
  value: number
  target: number
  color: 'purple' | 'teal' | 'gold' | 'red' | 'blue' | 'green' | 'orange'
}

type GetProgressoResponse = {
  resumo: ProgressoResumo
  evolucao_acertos: ProgressoEvolucaoAcertos
  horas_por_dia: ProgressoHorasPorDia[]
  ranking_materias: ProgressoRankingMateria[]
  heatmap: ProgressoHeatmap
  metas_mensais: ProgressoMetaMensal[]
}
```

### Status HTTP

- `200 OK`: dados retornados com sucesso (mesmo quando arrays estão vazios).
- `401 Unauthorized`: token ausente ou inválido.

---

## Origem dos dados na database

Nenhuma tabela nova foi criada. Tabelas reutilizadas (nomes reais do schema em `SQL_reference.txt`):

- `estatisticas_usuario`: XP total e ofensiva.
- `atividade_diaria`: minutos estudados por dia, questões respondidas por dia, simulados concluídos por dia — granularidade diária já agregada.
- `metas_mensais_usuario`: metas do aluno por mês (`inicio_mes`, `meta_questoes`, `meta_minutos_estudo`, `meta_simulados`).
- `tentativas_questoes` (join `questoes.materia_id`): respostas do aluno às questões, usadas para acertos por matéria.
- `materias`: nome das matérias para rótulos de série/ranking.

### `resumo`

| Campo | Origem |
|---|---|
| `xp_total` | `estatisticas_usuario.xp_total` do aluno. |
| `ofensiva_dias` | `estatisticas_usuario.ofensiva_atual_dias`. |
| `horas_estudadas` | Soma de `atividade_diaria.minutos_estudo` do mês corrente (do dia 1 até hoje), formatada como `"{horas}h"` (arredondado para baixo). |
| `meta_mensal_percentual` | Média entre até 3 percentuais: `questoes_respondidas_mes / meta_questoes`, `minutos_estudados_mes / meta_minutos_estudo`, `simulados_mes / meta_simulados` — cada um lido de `metas_mensais_usuario` (registro com `inicio_mes` = primeiro dia do mês corrente) contra a soma de `atividade_diaria` do mês. Cada percentual é limitado a 100. Se não houver meta cadastrada para o mês, retorna `0`. |

### `evolucao_acertos`

- Busca `tentativas_questoes` do aluno no mês corrente, com join `questoes!inner(materia_id)` (mesmo padrão de join usado em `routers/dashboard.py`).
- Cada tentativa é agrupada por matéria e por "semana do mês" (`((dia - 1) // 7) + 1`), gerando `categories` = `["Sem 1", "Sem 2", ...]` apenas para as semanas em que houve pelo menos uma tentativa.
- `values[]` de cada série = percentual de acerto (`acertos / total * 100`, arredondado) na semana correspondente; `0` se a matéria não teve tentativa naquela semana específica.
- `color` é atribuída ciclicamente a partir de `["blue", "green", "red"]`, na ordem em que as matérias aparecem — sem tabela de cor fixa por matéria nessa série, pois o contrato restringe a paleta a essas 3 cores.
- Se não houver nenhuma tentativa no mês, retorna `{"categories": [], "series": []}`.

### `horas_por_dia`

- `atividade_diaria.minutos_estudo` da semana corrente (segunda a domingo, `weekday()` do Python), um item fixo por dia (`Seg`...`Dom`), `value = minutos / 60` arredondado a 1 casa decimal.
- Dias sem registro em `atividade_diaria` retornam `value: 0`.

### `ranking_materias`

- Mesma fonte de `evolucao_acertos` (`tentativas_questoes` join `questoes.materia_id`), mas sem recorte de mês — considera todo o histórico do aluno.
- Percentual de acerto por matéria, ordenado decrescente (`percent` maior primeiro) — a posição no array já reflete o ranking.
- `color` ciclada a partir de `["purple", "teal", "gold", "red", "blue", "green", "orange"]`, na ordem pós-ordenação (1º colocado recebe a primeira cor da lista, e assim por diante).
- Retorna `[]` se o aluno nunca respondeu nenhuma questão.

### `heatmap`

- `weekday_labels` fixo: `["D", "S", "T", "Q", "Q", "S", "S"]` (domingo a sábado).
- `weeks`: últimas 5 semanas (domingo a sábado), calculadas a partir de `atividade_diaria.minutos_estudo` por dia.
- Nível por dia (0 a 4), calculado por faixa de minutos estudados:
  - `0` → nenhum minuto registrado.
  - `1` → 1 a 29 minutos.
  - `2` → 30 a 59 minutos.
  - `3` → 60 a 119 minutos.
  - `4` → 120 minutos ou mais.
- Dias sem registro em `atividade_diaria` contam como nível `0`.

### `metas_mensais`

- Lê `metas_mensais_usuario` do mês corrente (`inicio_mes` = primeiro dia do mês).
- Um item por meta configurada (só inclui a meta se o campo correspondente for maior que zero):
  - `"Questões resolvidas"` (`purple`): `value` = soma de `atividade_diaria.questoes_respondidas` do mês; `target` = `meta_questoes`.
  - `"Horas de estudo"` (`blue`): `value`/`target` em horas (minutos / 60, arredondado); `target` = `meta_minutos_estudo`.
  - `"Simulados feitos"` (`teal`): `value` = soma de `atividade_diaria.simulados_concluidos`; `target` = `meta_simulados`.
- Retorna `[]` se não houver registro de metas para o mês corrente.

---

## Regras de negócio

- "Mês corrente" e "semana corrente" são sempre calculados a partir da data atual em UTC (`datetime.now(timezone.utc).date()`), consistente com o padrão usado em `routers/dashboard.py` e `routers/plano_estudos.py`.
- Nenhum dado de outro aluno é acessado; toda consulta filtra por `usuario_id = <id do usuário autenticado>`.
- Todos os arrays retornam vazios (`[]`) em vez de `null` quando não há dados suficientes, conforme exigido pelo contrato.
- `meta_mensal_percentual` nunca ultrapassa 100 por meta individual (capado antes da média), evitando que uma meta estourada infle o percentual agregado acima do esperado pela UI.

## Observações para futuras integrações do frontend

- O agrupamento semanal de `evolucao_acertos` usa "semana do mês" (dia 1–7 = Sem 1, 8–14 = Sem 2, etc.), não semana ISO — isso é uma decisão de implementação, já que o contrato não especifica o método de corte. Se o frontend esperar semanas alinhadas a segunda-feira (ISO), ajustar `numero_semana_do_mes` em `routers/progresso.py`.
- `evolucao_acertos.series` só inclui matérias com pelo menos uma tentativa no mês corrente — matérias sem nenhuma atividade não aparecem como série zerada.
- `ranking_materias` considera o histórico completo do aluno (todas as tentativas já registradas), não apenas o mês corrente, diferente de `evolucao_acertos`. Caso o produto queira ranking mensal, é necessário replicar o filtro de data usado em `evolucao_acertos`.
- `metas_mensais` depende de existir um registro em `metas_mensais_usuario` para o mês corrente — não há criação automática dessa meta; se o fluxo de onboarding/planejamento não cria esse registro todo mês, o array virá vazio mesmo com atividade do aluno.
