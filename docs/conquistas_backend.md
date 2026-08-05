# Conquistas — Backend

Área do aluno. Rota autenticada via JWT (`Authorization: Bearer <token>`), validada por `pegar_usuario_atual` (`utils/autenticacao.py`). Todos os dados retornados são exclusivos do aluno autenticado — nenhum parâmetro de usuário é aceito.

---

## Endpoint

GET /aluno/conquistas

Retorna todos os dados da página "Conquistas" em uma única chamada: subtítulo, resumo (ofensiva, XP, nível, medalhas), conquistas desbloqueadas/bloqueadas e missões diárias/semanais.

### Autenticação

Obrigatória. `401 Unauthorized` se o token estiver ausente ou inválido.

### Request

Sem path params, sem query params, sem payload (GET puro).

### Response

```json
{
  "subtitulo": "4 de 9 conquistas encontradas",
  "ofensiva_dias": 8,
  "xp_total": 4820,
  "nivel_atual": 12,
  "xp_proximo_nivel": 5000,
  "total_medalhas": 4,
  "conquistas_desbloqueadas": [
    { "icone": "🏆", "titulo": "Primeira Semana", "descricao": "Complete 7 dias de estudo", "raridade": "comum", "xp": 100 }
  ],
  "conquistas_bloqueadas": [
    { "icone": "🛡️", "titulo": "Matemática Sem Medo", "descricao": "Acerte 80% em Matemática", "raridade": "epico" }
  ],
  "missoes_diarias": [
    { "label": "Resolver 10 questões", "xp": 50, "completed": true }
  ],
  "missoes_semanais": [
    { "label": "Completar plano semanal", "xp": 200, "current": 5, "target": 7 }
  ]
}
```

Nota: `conquistas_bloqueadas[]` nunca inclui a chave `xp` — o schema Pydantic (`ConquistaBloqueada`) simplesmente não declara esse campo, então ele é omitido do JSON serializado (não é enviado como `null`).

### Interfaces TypeScript

Idênticas ao contrato fornecido — não alteradas:

```ts
type ConquistaRaridade = 'comum' | 'incomum' | 'raro' | 'epico' | 'lendario'

type ConquistaDesbloqueada = {
  icone: string
  titulo: string
  descricao: string
  raridade: ConquistaRaridade
  xp: number
}

type ConquistaBloqueada = {
  icone: string
  titulo: string
  descricao: string
  raridade: ConquistaRaridade
}

type MissaoDiaria = {
  label: string
  xp: number
  completed: boolean
}

type MissaoSemanal = {
  label: string
  xp: number
  current: number
  target: number
}

type GetConquistasResponse = {
  subtitulo: string
  ofensiva_dias: number
  xp_total: number
  nivel_atual: number
  xp_proximo_nivel: number
  total_medalhas: number
  conquistas_desbloqueadas: ConquistaDesbloqueada[]
  conquistas_bloqueadas: ConquistaBloqueada[]
  missoes_diarias: MissaoDiaria[]
  missoes_semanais: MissaoSemanal[]
}
```

### Status HTTP

- `200 OK`: dados retornados com sucesso (mesmo quando arrays estão vazios).
- `401 Unauthorized`: token ausente ou inválido.

---

## Origem dos dados na database

Nenhuma tabela nova foi criada. Tabelas reutilizadas (nomes reais do schema em `SQL_reference.txt`):

- `estatisticas_usuario`: XP total e ofensiva atual do aluno.
- `conquistas`: catálogo de conquistas disponíveis (`titulo`, `descricao`, `icone`, `raridade`, `xp_recompensa`, `ativo`).
- `conquistas_usuario`: conquistas já desbloqueadas por aluno (`usuario_id`, `conquista_id`, `desbloqueado_em`).
- `missoes`: catálogo de missões (`titulo`, `tipo_missao` = `diaria`/`semanal`, `valor_alvo`, `xp_recompensa`, `ativo`).
- `progresso_missoes_usuario`: progresso do aluno em cada missão por período (`usuario_id`, `missao_id`, `periodo_inicio`, `periodo_fim`, `valor_atual`, `concluido_em`).

### Resumo (`ofensiva_dias`, `xp_total`, `nivel_atual`, `xp_proximo_nivel`, `total_medalhas`)

| Campo | Origem |
|---|---|
| `xp_total` | `estatisticas_usuario.xp_total` do aluno autenticado. `0` se o aluno ainda não tem registro em `estatisticas_usuario`. |
| `ofensiva_dias` | `estatisticas_usuario.ofensiva_atual_dias`. `0` se não houver registro. |
| `total_medalhas` | Contagem de itens em `conquistas_desbloqueadas` (ver abaixo) — não é uma coluna separada. |
| `nivel_atual` / `xp_proximo_nivel` | **Calculados**, não lidos de coluna. Ver "Regra de nível" abaixo. |

**Regra de nível**: o projeto não possui, em nenhum outro módulo, cálculo de nível/threshold de XP já implementado (a coluna `estatisticas_usuario.nivel` existe no schema, mas nenhum código do backend a escreve — nunca é atualizada, portanto não é confiável como fonte). Como o contrato exige `nivel_atual` e `xp_proximo_nivel`, foi adotada uma fórmula simples e determinística, isolada em `routers/conquistas.py::calcular_nivel`:

```
XP_POR_NIVEL = 1000
nivel_atual = (xp_total // 1000) + 1
xp_proximo_nivel = nivel_atual * 1000
```

Ou seja, cada nível custa 1000 XP fixos (nível 1: 0–999 XP, nível 2: 1000–1999 XP, etc.), e `xp_proximo_nivel` é sempre o teto do nível atual. Essa fórmula é um placeholder deliberado — se o produto já tiver (ou vier a ter) uma tabela de progressão de nível não-linear, substituir apenas essa função.

### `subtitulo`

Montado como `"{total_medalhas} de {total_conquistas} conquistas encontradas"`, onde `total_conquistas = len(conquistas_desbloqueadas) + len(conquistas_bloqueadas)` — ou seja, todas as conquistas ativas no catálogo (`conquistas.ativo = true`), desbloqueadas ou não.

### `conquistas_desbloqueadas` / `conquistas_bloqueadas`

- Busca todas as linhas de `conquistas` com `ativo = true`.
- Busca `conquistas_usuario` do aluno autenticado para saber quais `conquista_id` já foram desbloqueadas.
- Para cada conquista do catálogo: se o `id` está em `conquistas_usuario` do aluno, vai para `conquistas_desbloqueadas` (inclui `xp` = `conquistas.xp_recompensa`); caso contrário, vai para `conquistas_bloqueadas` (sem o campo `xp`).
- `icone` usa fallback `"🏆"` e `descricao` usa fallback de string vazia caso venham `null` do banco (ambas colunas são nullable em `conquistas`).
- Se não houver nenhuma conquista ativa cadastrada, ambos os arrays retornam `[]`.

### `missoes_diarias`

- Busca `missoes` com `tipo_missao = 'diaria'` e `ativo = true`.
- Para cada missão, busca o progresso do aluno em `progresso_missoes_usuario` filtrando `periodo_inicio = hoje` (data UTC corrente).
- `completed` é `true` se `progresso_missoes_usuario.concluido_em` estiver preenchido **ou** se `valor_atual >= valor_alvo` (dupla checagem, cobrindo o caso em que o progresso bateu a meta mas o job que marca `concluido_em` ainda não rodou).
- Se o aluno não tem nenhum registro de progresso para a missão hoje, considera `valor_atual = 0` e `completed = false`.
- Se não houver missão diária ativa cadastrada, retorna `[]`.

### `missoes_semanais`

- Busca `missoes` com `tipo_missao = 'semanal'` e `ativo = true`.
- Para cada missão, busca o progresso do aluno em `progresso_missoes_usuario` filtrando `periodo_inicio`/`periodo_fim` = semana corrente (segunda a domingo, mesmo cálculo usado em `routers/dashboard.py` e `routers/progresso.py`: `inicio_semana = hoje - timedelta(days=hoje.weekday())`).
- `current` é o `valor_atual` do progresso, limitado (`min`) ao `valor_alvo` da missão, para nunca exceder `target` na resposta.
- Se o aluno não tem progresso registrado para a semana, `current = 0`.
- Se não houver missão semanal ativa cadastrada, retorna `[]`.

---

## Regras de negócio

- Todas as consultas filtram por `usuario_id = <id do usuário autenticado>` — nenhum dado de outro aluno é exposto.
- Nenhum array retorna `null`; na ausência de dados, retornam `[]`, conforme exigido pelo contrato.
- `conquistas_bloqueadas[]` nunca inclui a chave `xp` (omissão estrutural via schema, não valor `null`).
- `raridade` é sempre um dos 5 valores do CHECK constraint da tabela `conquistas` (`comum`, `incomum`, `raro`, `epico`, `lendario`) — não há tradução/mapeamento, o valor do banco já corresponde ao contrato.
- "Hoje" e "semana corrente" usam `datetime.now(timezone.utc).date()`, consistente com o padrão dos demais módulos do projeto.

## Observações para futuras integrações do frontend

- `nivel_atual`/`xp_proximo_nivel` são calculados por fórmula fixa (1000 XP por nível), não persistidos. Qualquer mudança na progressão de nível deve ser feita apenas na função `calcular_nivel` em `routers/conquistas.py` — nenhuma migration é necessária para ajustar a curva de XP.
- O endpoint **não** desbloqueia conquistas nem atualiza progresso de missões — é somente leitura. A lógica de concessão de conquistas/atualização de `progresso_missoes_usuario` deve ser implementada nos fluxos que geram os eventos (responder questão, concluir aula, finalizar simulado etc.), fora do escopo desta tela.
- Caso o produto queira permitir múltiplos ciclos de missão diária/semanal no mesmo dia (ex.: reset em horário diferente de UTC), ajustar o cálculo de "hoje"/"semana corrente" em `routers/conquistas.py`.
