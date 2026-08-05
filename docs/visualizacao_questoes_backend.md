# Visualização de Questões — Backend Requirements

Área do aluno. Todas as rotas exigem usuário autenticado (JWT via `Authorization: Bearer <token>`, validado com `pegar_usuario_atual`). Os dados retornados consideram sempre apenas o aluno autenticado (respostas, favoritos e progresso são por usuário).

Identificação da lista de questões é feita sempre pelo `slug`, nunca pelo `id`, em qualquer rota que referencie a lista diretamente na URL.

---

## Endpoint

GET /aluno/questoes/{slug}

Retorna os dados completos de uma lista de questões para exibição na página de Visualização de Questões: informações da lista, progresso do aluno autenticado e todas as questões com alternativas e estado atual (respondida, favorita, correta).

--------------------------------------------
Path Params
--------------------------------------------

- `slug` (obrigatório): identificador amigável da lista de questões (`listas_questoes.slug`).

--------------------------------------------
Query Params
--------------------------------------------

Nenhum.

--------------------------------------------
Payload
--------------------------------------------

Nenhum (GET).

--------------------------------------------
Response
--------------------------------------------

```json
{
  "slug": "lista-funcoes",
  "titulo": "Lista: Funções",
  "materia": "Matemática",
  "dificuldade": "Médio",
  "vestibular": "ENEM",
  "status": "em_andamento",
  "questoes_totais": 12,
  "questoes_concluidas": 8,
  "progresso_percentual": 66,
  "questoes": [
    {
      "id": "uuid-questao-1",
      "subject": "Matemática",
      "subjectColor": "blue",
      "examInfo": "ENEM 2020 · Fácil",
      "question": "Resolva a equação do 2º grau x² - 7x + 12 = 0 e identifique suas raízes.",
      "options": [
        "As raízes são x = 3 e x = 4.",
        "As raízes são x = 2 e x = 6.",
        "A equação não possui raízes reais.",
        "As raízes são x = -3 e x = -4.",
        "A raiz é única: x = 7."
      ],
      "hint": "Use a Fórmula de Bhaskara com a = 1, b = -7 e c = 12.",
      "respondida": true,
      "opcaoSelecionada": 0,
      "correta": true,
      "favorita": false
    }
  ]
}
```

--------------------------------------------
Descrição dos campos
--------------------------------------------

- `slug` / `titulo` / `materia` / `dificuldade` / `vestibular`: dados da lista (`listas_questoes` + `materias` + `tipos_prova`).
- `status`: estado da lista para o aluno autenticado (`em_andamento` ou `finalizada`).
- `questoes_totais`: quantidade de questões da lista (`itens_lista_questoes` da lista).
- `questoes_concluidas` / `progresso_percentual`: calculados a partir das respostas do aluno autenticado para as questões da lista.
- `questoes[].id`: id da questão (`questoes.id`).
- `questoes[].subject` / `subjectColor`: nome e cor da matéria da questão.
- `questoes[].examInfo`: rótulo composto (ex.: `"{vestibular} {ano} · {dificuldade}"`).
- `questoes[].question`: enunciado (`questoes.enunciado`).
- `questoes[].options`: textos das alternativas (`alternativas_questao.conteudo`), ordenados por `ordem`. O índice do array (0-based) é o identificador de opção usado no PATCH de resposta.
- `questoes[].hint`: dica (`questoes.dica`).
- `questoes[].respondida` / `opcaoSelecionada` / `correta`: estado da resposta do aluno autenticado para essa questão.
- `questoes[].favorita`: se o aluno autenticado marcou a questão como favorita.

--------------------------------------------
Campos obrigatórios
--------------------------------------------

- `slug`, `titulo`, `materia`, `dificuldade`, `vestibular`, `status`, `questoes_totais`, `questoes_concluidas`, `progresso_percentual`, `questoes`.
- Em cada questão: `id`, `subject`, `subjectColor`, `examInfo`, `question`, `options`, `hint`, `respondida`, `opcaoSelecionada`, `correta`, `favorita`.

--------------------------------------------
Campos opcionais
--------------------------------------------

Nenhum. `opcaoSelecionada` e `correta` são `null` quando a questão ainda não foi respondida pelo aluno.

--------------------------------------------
Status HTTP
--------------------------------------------

- `200 OK`: lista retornada com sucesso.
- `401 Unauthorized`: token ausente ou inválido.
- `404 Not Found`: nenhuma lista encontrada para o `slug` informado.

--------------------------------------------
Observações de banco
--------------------------------------------

- Reutiliza `listas_questoes`, `itens_lista_questoes`, `questoes`, `alternativas_questao`, `materias`, `tipos_prova`.
- Ver seção "Modelagem do banco" para o campo `slug` (ainda não existente em `listas_questoes`) e para as tabelas de progresso/resposta/favorito do aluno.

---

## Endpoint

PATCH /aluno/questoes/{slug}/questoes/{questaoId}

Registra a resposta escolhida pelo aluno autenticado para uma questão da lista e retorna o novo estado da questão e do progresso da lista.

--------------------------------------------
Path Params
--------------------------------------------

- `slug` (obrigatório): identificador amigável da lista.
- `questaoId` (obrigatório): id da questão (`questoes.id`).

--------------------------------------------
Query Params
--------------------------------------------

Nenhum.

--------------------------------------------
Payload
--------------------------------------------

```json
{
  "opcao_selecionada": 0
}
```

--------------------------------------------
Response
--------------------------------------------

```json
{
  "id": "uuid-questao-1",
  "respondida": true,
  "opcaoSelecionada": 0,
  "correta": true,
  "questoes_concluidas": 9,
  "progresso_percentual": 75
}
```

--------------------------------------------
Descrição dos campos
--------------------------------------------

- `opcao_selecionada` (payload): índice (0-based) da alternativa escolhida, relativo ao array `options` retornado no GET da lista. O backend converte o índice para a alternativa correspondente (ordenada por `ordem`) para gravar e para comparar com `questoes.alternativa_correta`.
- `correta` (response): resultado do comparativo entre a alternativa escolhida e `questoes.alternativa_correta`.
- `questoes_concluidas` / `progresso_percentual`: valores recalculados da lista após a resposta, para atualização incremental da barra de progresso sem novo GET completo.

--------------------------------------------
Campos obrigatórios
--------------------------------------------

- Payload: `opcao_selecionada`.
- Response: `id`, `respondida`, `opcaoSelecionada`, `correta`, `questoes_concluidas`, `progresso_percentual`.

--------------------------------------------
Campos opcionais
--------------------------------------------

Nenhum.

--------------------------------------------
Regras de negócio
--------------------------------------------

- A questão deve pertencer à lista identificada pelo `slug` (via `itens_lista_questoes`); caso contrário, `404`.
- `opcao_selecionada` deve corresponder a um índice válido dentro do total de alternativas da questão; caso contrário, `422`.
- Não é permitido responder uma questão de uma lista já finalizada pelo aluno; caso a lista esteja finalizada, `422`.
- Uma nova chamada para a mesma questão sobrescreve a resposta anterior do aluno (permite corrigir a escolha enquanto a lista não é finalizada).

--------------------------------------------
Status HTTP
--------------------------------------------

- `200 OK`: resposta registrada com sucesso.
- `401 Unauthorized`: token ausente ou inválido.
- `404 Not Found`: lista ou questão não encontrada, ou questão não pertence à lista informada.
- `422 Unprocessable Entity`: `opcao_selecionada` fora do intervalo de alternativas, ou lista já finalizada.

--------------------------------------------
Observações de banco
--------------------------------------------

- Grava/atualiza registro em tabela de respostas do aluno (ver `respostas_lista_questoes_aluno` na seção "Modelagem do banco").
- Consulta `alternativas_questao` (ordenada por `ordem`) e `questoes.alternativa_correta` para determinar `correta`.

---

## Endpoint

PATCH /aluno/questoes/favoritos/{questaoId}

Alterna o estado de favorito de uma questão para o aluno autenticado.

--------------------------------------------
Path Params
--------------------------------------------

- `questaoId` (obrigatório): id da questão (`questoes.id`).

--------------------------------------------
Query Params
--------------------------------------------

Nenhum.

--------------------------------------------
Payload
--------------------------------------------

```json
{}
```

--------------------------------------------
Response
--------------------------------------------

```json
{
  "id": "uuid-questao-1",
  "favorita": true
}
```

--------------------------------------------
Descrição dos campos
--------------------------------------------

- `favorita`: novo estado do favorito após a alternância (toggle). Se já era favorita para o aluno, remove; caso contrário, adiciona.

--------------------------------------------
Campos obrigatórios
--------------------------------------------

- Response: `id`, `favorita`.

--------------------------------------------
Campos opcionais
--------------------------------------------

Nenhum.

--------------------------------------------
Status HTTP
--------------------------------------------

- `200 OK`: favorito atualizado com sucesso.
- `401 Unauthorized`: token ausente ou inválido.
- `404 Not Found`: questão não encontrada.

--------------------------------------------
Observações de banco
--------------------------------------------

- Reutiliza a tabela `questoes_favoritas` (já existente: `id`, `usuario_id`, `questao_id`, `criado_em`).
- Toggle: se existir registro com `usuario_id` + `questao_id`, deletar; caso não exista, inserir.

---

## Endpoint

POST /aluno/questoes/{slug}/finalizar

Finaliza a lista de questões para o aluno autenticado, quando todas as questões da lista foram respondidas.

--------------------------------------------
Path Params
--------------------------------------------

- `slug` (obrigatório): identificador amigável da lista.

--------------------------------------------
Query Params
--------------------------------------------

Nenhum.

--------------------------------------------
Payload
--------------------------------------------

```json
{}
```

--------------------------------------------
Response
--------------------------------------------

```json
{
  "status": "finalizada",
  "progresso_percentual": 100,
  "questoes_concluidas": 12,
  "questoes_totais": 12
}
```

--------------------------------------------
Descrição dos campos
--------------------------------------------

- `status`: novo status da lista para o aluno autenticado (`finalizada`).
- `progresso_percentual`, `questoes_concluidas`, `questoes_totais`: valores finais da lista.

--------------------------------------------
Campos obrigatórios
--------------------------------------------

- `status`, `progresso_percentual`, `questoes_concluidas`, `questoes_totais`.

--------------------------------------------
Campos opcionais
--------------------------------------------

Nenhum.

--------------------------------------------
Regras de negócio
--------------------------------------------

- Só é permitido finalizar quando `questoes_concluidas == questoes_totais` para o aluno autenticado; caso contrário, `422`.
- Finalizar uma lista já finalizada é idempotente: retorna `200` com o estado atual (não gera erro nem duplica registro).

--------------------------------------------
Status HTTP
--------------------------------------------

- `200 OK`: lista finalizada com sucesso (ou já estava finalizada).
- `401 Unauthorized`: token ausente ou inválido.
- `404 Not Found`: lista não encontrada.
- `422 Unprocessable Entity`: existem questões da lista ainda não respondidas pelo aluno.

--------------------------------------------
Observações de banco
--------------------------------------------

- Atualiza `status` e `concluido_em` na tabela de progresso do aluno para a lista (ver `progresso_lista_questoes_aluno` na seção "Modelagem do banco").

---

## Modelagem do banco

### Tabelas existentes reutilizadas

- `listas_questoes`: dados da lista (`id`, `titulo`, `materia_id`, `tipo_prova_id`, `dificuldade`, `tipo_lista`, ...).
- `itens_lista_questoes`: relação lista ↔ questão (`lista_questoes_id`, `questao_id`, `ordem`).
- `questoes`: enunciado, dica, dificuldade, matéria, alternativa correta (`alternativa_correta`).
- `alternativas_questao`: alternativas da questão (`questao_id`, `letra`, `conteudo`, `ordem`).
- `materias`: nome e cor da matéria, usados em `materia`/`subject`/`subjectColor`.
- `tipos_prova`: nome do vestibular.
- `questoes_favoritas`: já existente e cobre integralmente o requisito de favoritos — **não é necessária tabela nova**. Estrutura atual:
  - `id uuid PK`
  - `usuario_id uuid FK → perfis.id`
  - `questao_id uuid FK → questoes.id`
  - `criado_em timestamptz`

### Alteração necessária em tabela existente

- `listas_questoes` não possui atualmente coluna `slug`. Como o requisito exige identificar a lista sempre por `slug` (nunca por `id`), é necessário adicionar:
  - `slug text UNIQUE NOT NULL` em `listas_questoes`, seguindo o mesmo padrão já usado em `aulas.slug`, `materias.slug` e `tipos_prova.slug` (gerado a partir do `titulo`, único).

### Tabelas de relacionamento necessárias (não existem equivalentes hoje)

O projeto possui `tentativas_questoes` e `tentativas_lista_questoes`, mas ambas foram desenhadas para o fluxo de simulados/sessões (`sessao_simulado_id`, `indice_questao_atual`, `tentativa_lista_id` opcional) e não representam de forma direta "resposta do aluno a uma questão dentro de uma lista de estudo", nem impedem duplicidade de resposta por questão. Para não sobrecarregar essas tabelas com uma semântica diferente, propõe-se duas tabelas novas, dedicadas ao fluxo de Banco de Questões / Visualização de Questões:

**`progresso_lista_questoes_aluno`** — progresso do aluno em uma lista.

| Coluna | Tipo | Observações |
|---|---|---|
| `id` | uuid PK | `gen_random_uuid()` |
| `usuario_id` | uuid FK → `perfis.id` | |
| `lista_questoes_id` | uuid FK → `listas_questoes.id` | |
| `status` | text CHECK (`em_andamento`, `finalizada`) | default `em_andamento` |
| `iniciado_em` | timestamptz | default `now()` |
| `concluido_em` | timestamptz | null até finalizar |
| `atualizado_em` | timestamptz | default `now()` |

- Constraint `UNIQUE (usuario_id, lista_questoes_id)`.
- `questoes_concluidas` e `progresso_percentual` são derivados (não persistidos): contagem de registros em `respostas_lista_questoes_aluno` para a lista, dividida pelo total de `itens_lista_questoes` da lista.

**`respostas_lista_questoes_aluno`** — resposta do aluno a uma questão de uma lista.

| Coluna | Tipo | Observações |
|---|---|---|
| `id` | uuid PK | `gen_random_uuid()` |
| `usuario_id` | uuid FK → `perfis.id` | |
| `lista_questoes_id` | uuid FK → `listas_questoes.id` | |
| `questao_id` | uuid FK → `questoes.id` | |
| `alternativa_selecionada_id` | uuid FK → `alternativas_questao.id` | |
| `correta` | boolean | calculado no momento da resposta |
| `respondido_em` | timestamptz | default `now()`, atualizado a cada nova tentativa |

- Constraint `UNIQUE (usuario_id, lista_questoes_id, questao_id)` — uma resposta vigente por questão/lista/aluno; responder novamente atualiza o registro existente (upsert), não duplica.
- `opcaoSelecionada` (índice 0-based no `options[]`) é derivado no momento da leitura, a partir da posição de `alternativa_selecionada_id` em `alternativas_questao` ordenada por `ordem` — não é persistido como índice.

### Relacionamentos

- `listas_questoes (1) → (N) itens_lista_questoes (N) → (1) questoes`: compõe o conteúdo da lista.
- `questoes (1) → (N) alternativas_questao`: opções de cada questão.
- `perfis (1) → (N) progresso_lista_questoes_aluno (N) → (1) listas_questoes`: status/progresso do aluno por lista.
- `perfis (1) → (N) respostas_lista_questoes_aluno`, vinculada a `lista_questoes_id` + `questao_id`: resposta do aluno por questão dentro de uma lista.
- `perfis (1) → (N) questoes_favoritas (N) → (1) questoes`: favoritos do aluno (já existente, reutilizada sem alteração).
