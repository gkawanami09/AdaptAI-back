# Chat da Ada — Backend

Área do aluno. Rota autenticada via JWT (`Authorization: Bearer <token>`), validada por `pegar_usuario_atual` (`utils/autenticacao.py`). Uma conversa pertence exclusivamente ao aluno que a criou — qualquer tentativa de acessar/alterar uma conversa de outro aluno retorna `404` (não `403`, para não revelar existência do recurso).

---

## Arquitetura

```
routers/chat.py            -> controller (validação, HTTP, DTOs)
services/conversation_service.py -> persistência de conversas/mensagens (Supabase)
services/chat_ai_service.py      -> único ponto de chamada da IA para o chat (logging, tratamento de erro)
services/chat_context_builder.py -> monta system prompt + histórico + mensagem nova
services/ai/base.py              -> AIProvider.responder_chat (contrato usado pelos providers)
services/ai/providers/*          -> implementações concretas (Ollama, OpenAI-compatible)
services/ai/prompts/chat.py      -> SYSTEM_PROMPT centralizado da Ada
services/ai/tools/base.py        -> AITool / ToolExecutor (preparação para ferramentas futuras)
```

O controller nunca chama `get_ai_provider()` diretamente nem monta prompts — toda chamada de IA para o chat passa por `ChatAIService.gerar_resposta()`.

---

## Banco

Reutiliza as tabelas já existentes `conversas_ia` e `mensagens_ia` — nenhuma tabela nova foi criada. Como o modelo de IA usado é gratuito, contagem de tokens, modelo usado e feedback do aluno não são persistidos nesta fase (ver seção "Decisões conscientes" abaixo).

### `conversas_ia` (existente)

| Coluna usada | Observações |
| --- | --- |
| id | PK uuid |
| usuario_id | dono da conversa (FK -> perfis) |
| titulo | padrão `"Nova conversa"`, atualizado automaticamente após a primeira mensagem |
| tipo_contexto | o chat usa sempre `'chat_geral'` (valor já suportado pelo CHECK existente) |
| criado_em / atualizado_em | `atualizado_em` é tocado a cada nova mensagem |

### `mensagens_ia` (existente)

| Coluna usada | Observações |
| --- | --- |
| id | PK uuid |
| conversa_id | FK -> conversas_ia |
| autor | `usuario` \| `assistente` \| `sistema` — mapeado internamente para `user` \| `assistant` \| `system` |
| conteudo | texto da mensagem |
| criado_em | usado para ordenação cronológica |

Mensagens são sempre recuperadas em ordem crescente de `criado_em` (`ConversationService.listar_mensagens`).

### Decisões conscientes (fora de escopo por ora)

- **Tokens/modelo por mensagem**: não persistidos — `mensagens_ia` não tem essas colunas e, com um modelo gratuito, não há necessidade de custo a rastrear. `modelo` ainda é retornado no response de `POST /mensagens` (vem de `config.AI_MODEL` em tempo de execução), só não é salvo no banco.
- **Feedback (curtir/não curtir)**: endpoint não implementado — não há coluna para armazenar isso em `mensagens_ia`. Pode ser adicionado depois com uma migração simples caso vire requisito.

---

## Autenticação

Todos os endpoints exigem `Authorization: Bearer <JWT>`. `401 Unauthorized` (`{"detail": "..."}`) se ausente/inválido — mesmo padrão dos demais módulos.

---

## Endpoints

### 1. Listar conversas

GET /aluno/chat/conversas

Retorna todas as conversas do aluno autenticado, ordenadas por `atualizadoEm` decrescente.

**Response 200**

```json
{
  "conversas": [
    {
      "id": "uuid",
      "slug": "funcoes-do-segundo-grau-a1b2c3d4",
      "titulo": "Funções do segundo grau",
      "atualizadoEm": "2026-08-07T13:00:00+00:00"
    }
  ]
}
```

Lista vazia (`"conversas": []`) quando o aluno nunca conversou com a Ada.

**Status HTTP:** `200` sempre · `401` sessão expirada

---

### 2. Criar conversa

POST /aluno/chat/conversas

**Payload**

```json
{ "titulo": "string opcional" }
```

Se `titulo` não for enviado (ou vier vazio), o backend usa `"Nova conversa"` e atualiza automaticamente após a primeira mensagem trocada (resumo da primeira pergunta do aluno, truncado em 60 caracteres).

**Response 201**

```json
{
  "id": "uuid",
  "slug": "nova-conversa-a1b2c3d4",
  "titulo": "Nova conversa",
  "atualizadoEm": "2026-08-07T13:00:00+00:00"
}
```

**Status HTTP:** `201` criada · `401` sessão expirada

---

### 3. Buscar histórico de uma conversa

GET /aluno/chat/conversas/{conversationId}

**Response 200**

```json
{
  "id": "uuid",
  "slug": "nova-conversa-a1b2c3d4",
  "titulo": "Nova conversa",
  "mensagens": [
    {
      "id": "uuid",
      "sender": "ada",
      "texto": "Olá!",
      "timestamp": "2026-08-07T12:00:00+00:00",
      "anexos": [],
      "sugestoes": null
    }
  ]
}
```

`mensagens` vazio quando a conversa acabou de ser criada.

**Status HTTP:** `200` encontrada · `404` id inexistente ou de outro aluno · `401` sessão expirada

---

### 4. Enviar mensagem para a IA

POST /aluno/chat/conversas/{conversationId}/mensagens

Endpoint principal. Fluxo:

1. valida a conversa (pertence ao aluno autenticado)
2. salva a mensagem do usuário
3. recupera o histórico da conversa (ordem cronológica)
4. monta o contexto (`ChatContextBuilder`: system prompt + histórico + mensagem nova)
5. chama a IA (`ChatAIService.gerar_resposta`)
6. salva a resposta
7. atualiza `atualizado_em` da conversa e, se for a primeira mensagem, o título automático
8. retorna ambas as mensagens ao frontend

**Payload**

```json
{ "mensagem": "Explique função do segundo grau" }
```

**Response 200**

```json
{
  "user": {
    "id": "uuid",
    "sender": "user",
    "texto": "Explique função do segundo grau",
    "timestamp": "2026-08-07T12:00:00+00:00"
  },
  "assistant": {
    "id": "uuid",
    "sender": "ada",
    "texto": "Função do segundo grau é...",
    "timestamp": "2026-08-07T12:00:01+00:00"
  },
  "tempoProcessamentoMs": 1200,
  "modelo": "qwen2.5:14b",
  "sugestoes": null
}
```

`sugestoes` é reservado para quando as ferramentas de IA estiverem ativas (ver seção "Ferramentas").

Caso a IA falhe (`AIIndisponivelError` / `AIRespostaInvalidaError`), a mensagem do usuário já salva é mantida, **nenhuma resposta vazia é salva**, e o endpoint retorna:

**Response 503**

```json
{ "message": "Não foi possível gerar resposta." }
```

**Status HTTP:** `200` sucesso · `404` conversa inexistente/de outro aluno · `422` mensagem vazia · `401` sessão expirada · `503` IA indisponível

---

### 5. Excluir conversa

DELETE /aluno/chat/conversas/{conversationId}

**Status HTTP:** `204` excluída · `404` inexistente/de outro aluno · `401` sessão expirada

---

### 6. Renomear conversa

PATCH /aluno/chat/conversas/{conversationId}

**Payload**

```json
{ "titulo": "Funções" }
```

**Response 200**

```json
{
  "id": "uuid",
  "slug": "funcoes-a1b2c3d4",
  "titulo": "Funções",
  "atualizadoEm": "2026-08-07T13:05:00+00:00"
}
```

**Status HTTP:** `200` renomeada · `404` inexistente/de outro aluno · `422` título vazio · `401` sessão expirada

---

### 7. Regenerar última resposta

POST /aluno/chat/conversas/{conversationId}/regenerar

Descarta a última resposta da Ada e gera uma nova a partir da última mensagem do usuário na conversa.

**Response 200**

```json
{
  "assistant": {
    "id": "uuid",
    "sender": "ada",
    "texto": "nova resposta",
    "timestamp": "2026-08-07T12:10:00+00:00"
  }
}
```

**Status HTTP:** `200` nova resposta gerada · `404` conversa inexistente ou sem mensagens para regenerar · `401` sessão expirada · `503` IA indisponível

---

### 8. Listar modelos disponíveis

GET /aluno/chat/modelos

**Response 200**

```json
{
  "modelos": [
    { "id": "qwen2.5:14b", "nome": "Ada", "descricao": "Modelo padrão", "padrao": true }
  ]
}
```

Reflete `config.AI_MODEL` — preparado para futura seleção de modelo pelo aluno sem mudança de contrato.

**Status HTTP:** `200` sempre · `401` sessão expirada

---

## Ferramentas da IA (tool calling)

Endpoints preparados desde já para o frontend consumir, retornando `501 Not Implemented` até serem implementados:

```json
{ "status": "not_implemented" }
```

| Endpoint | Descrição | Payload |
| --- | --- | --- |
| `POST /aluno/chat/tools/questoes` | Gerar questões sobre um tema | `{ "tema": "string", "quantidade": 10 }` |
| `POST /aluno/chat/tools/resumo` | Gerar resumo de um conteúdo | `{ "conteudo": "string" }` |
| `POST /aluno/chat/tools/revisao` | Criar revisão personalizada | `{ "materia": "string" }` |
| `POST /aluno/chat/tools/plano-estudos` | Gerar plano de estudos | `{ "objetivo": "string" }` |
| `POST /aluno/chat/tools/redacao` | Corrigir redação (delega ao fluxo de redação) | `{ "texto": "string" }` |
| `POST /aluno/chat/tools/explicacao` | Explicar um conteúdo/tópico | `{ "topico": "string" }` |
| `POST /aluno/chat/tools/lista` | Gerar lista de exercícios | `{ "tema": "string", "quantidade": 10 }` |
| `POST /aluno/chat/tools/simulados` | Montar simulado personalizado | `{ "materias": ["string"], "quantidadeQuestoes": 20 }` |

Cada ferramenta futura deve implementar a interface `AITool` (`services/ai/tools/base.py`) e ser registrada em um `ToolExecutor`, mantendo o controller desacoplado da lógica de cada ferramenta.

**Status HTTP:** `501` não implementada (atual) · `200` quando implementada · `401` sessão expirada

---

## Prompt do sistema

Centralizado em `services/ai/prompts/chat.py` (`SYSTEM_PROMPT`), nunca hardcoded no controller ou no service de conversas. Define que a Ada responde em português, explica de forma didática, adapta a dificuldade, incentiva o aprendizado, nunca inventa informações, usa Markdown/listas quando fizer sentido e evita respostas excessivamente longas.

---

## Limite de histórico

`ChatContextBuilder` (`services/chat_context_builder.py`) limita o histórico enviado à IA a `MAX_MENSAGENS_HISTORICO` (20) mensagens mais recentes. Está marcado com TODO para evoluir para um limite por quantidade de tokens quando necessário.

---

## Streaming (evolução futura)

A implementação atual é síncrona (request/response). A arquitetura já separa a geração da resposta (`ChatAIService.gerar_resposta`) do controller, o que permite evoluir para SSE/WebSocket futuramente sem reescrever a camada de persistência — o controller apenas trocaria a chamada síncrona por uma que emite eventos incrementais.

---

## Fora de escopo nesta fase

O contrato originalmente especificado pelo frontend incluía `POST /aluno/chat/conversas/{id}/feedback` (curtir/não curtir resposta) e os campos `tokensUsados`/`tokens` no response. Como o modelo de IA usado é gratuito e `mensagens_ia` não tem coluna para feedback, esses dois pontos não foram implementados agora — ver "Decisões conscientes" na seção Banco. Se o frontend depender estritamente desses campos, avisar antes de integrar.

---

## Logging

`ChatAIService` registra (sem logar o conteúdo completo das mensagens do usuário):

- início da chamada (`model`, quantidade de mensagens enviadas)
- fim da chamada (`model`, duração em ms)
- erros (`AIIndisponivelError` / `AIRespostaInvalidaError`), com stacktrace via `logger.exception`
