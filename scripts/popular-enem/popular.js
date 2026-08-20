#!/usr/bin/env node
'use strict';

/**
 * Popula o sistema de estudos ENEM via API REST (/admin/materias, /admin/topicos,
 * /admin/aulas, /admin/questoes), usando os schemas Pydantic reais do backend
 * (schemas/materia_schema.py, topicos_schema.py, aulas_schema.py, questoes_schema.py).
 *
 * Uso:
 *   node scripts/popular-enem/popular.js
 *
 * Também aceita variáveis de ambiente para rodar sem prompts:
 *   ENEM_API_URL, ENEM_API_TOKEN, ENEM_AULAS_POR_MATERIA, ENEM_QUESTOES_POR_MATERIA
 */

const fs = require('fs');
const path = require('path');
const readline = require('readline/promises');
const { stdin, stdout } = require('process');

const { MATERIAS, TOPICOS, CONTEUDO } = require('./data');

const DIFICULDADES_AULA = ['basico', 'medio', 'dificil'];
const DIFICULDADES_QUESTAO = ['facil', 'medio', 'dificil'];
const LETRAS_VALIDAS = ['A', 'B', 'C', 'D', 'E'];

// ---------------------------------------------------------------------------
// Entrada do usuário
// ---------------------------------------------------------------------------

async function coletarConfiguracao() {
  const rl = readline.createInterface({ input: stdin, output: stdout });

  const perguntar = async (mensagem, padrao) => {
    const resposta = (await rl.question(`${mensagem}${padrao ? ` [${padrao}]` : ''}: `)).trim();
    return resposta || padrao;
  };

  let baseUrl = process.env.ENEM_API_URL;
  let token = process.env.ENEM_API_TOKEN;
  let aulasPorMateria = process.env.ENEM_AULAS_POR_MATERIA;
  let questoesPorMateria = process.env.ENEM_QUESTOES_POR_MATERIA;

  if (!baseUrl) baseUrl = await perguntar('URL base da API', 'http://localhost:8000');
  if (!token) token = await perguntar('Token de administrador (Bearer)');
  if (!aulasPorMateria) aulasPorMateria = await perguntar('Quantas aulas por matéria', '2');
  if (!questoesPorMateria) questoesPorMateria = await perguntar('Quantas questões por matéria', '2');

  rl.close();

  if (!token) {
    throw new Error('Token de administrador é obrigatório.');
  }

  return {
    baseUrl: baseUrl.replace(/\/+$/, ''),
    token,
    aulasPorMateria: Math.max(0, parseInt(aulasPorMateria, 10) || 0),
    questoesPorMateria: Math.max(0, parseInt(questoesPorMateria, 10) || 0),
  };
}

// ---------------------------------------------------------------------------
// Cliente HTTP
// ---------------------------------------------------------------------------

function criarCliente(baseUrl, token) {
  async function requisitar(metodo, caminho, corpo) {
    const resposta = await fetch(`${baseUrl}${caminho}`, {
      method: metodo,
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`,
      },
      body: corpo !== undefined ? JSON.stringify(corpo) : undefined,
    });

    let dados = null;
    const texto = await resposta.text();
    if (texto) {
      try {
        dados = JSON.parse(texto);
      } catch {
        dados = texto;
      }
    }

    if (!resposta.ok) {
      const detalhe =
        (dados && typeof dados === 'object' && (dados.detail || dados.mensagem)) ||
        (typeof dados === 'string' ? dados : JSON.stringify(dados));
      const erro = new Error(`${metodo} ${caminho} -> ${resposta.status}: ${detalhe}`);
      erro.status = resposta.status;
      throw erro;
    }

    return dados;
  }

  return {
    get: (caminho) => requisitar('GET', caminho),
    post: (caminho, corpo) => requisitar('POST', caminho, corpo),
  };
}

// ---------------------------------------------------------------------------
// Validações (espelham as regras dos schemas Pydantic)
// ---------------------------------------------------------------------------

function validarAula(aula) {
  const erros = [];

  if (!aula.materia_id) erros.push('materia_id é obrigatório');
  if (!aula.titulo || aula.titulo.length < 2 || aula.titulo.length > 150) {
    erros.push('titulo deve ter entre 2 e 150 caracteres');
  }
  if (!DIFICULDADES_AULA.includes(aula.dificuldade)) {
    erros.push(`dificuldade inválida para aula: "${aula.dificuldade}" (use ${DIFICULDADES_AULA.join('|')})`);
  }
  if (!Number.isInteger(aula.ordem) || aula.ordem < 0) {
    erros.push('ordem deve ser um inteiro >= 0');
  }

  for (const [indice, conteudo] of (aula.conteudos || []).entries()) {
    if (!['video', 'texto'].includes(conteudo.tipo)) {
      erros.push(`conteudos[${indice}].tipo inválido: "${conteudo.tipo}"`);
    }
    if (!Number.isInteger(conteudo.ordem) || conteudo.ordem < 0) {
      erros.push(`conteudos[${indice}].ordem deve ser um inteiro >= 0`);
    }
    if (!Number.isInteger(conteudo.duracao) || conteudo.duracao < 0) {
      erros.push(`conteudos[${indice}].duracao deve ser um inteiro >= 0`);
    }
    if (conteudo.tipo === 'video' && !conteudo.video?.video_link) {
      erros.push(`conteudos[${indice}] do tipo video precisa de video.video_link`);
    }
    if (conteudo.tipo === 'texto' && !conteudo.texto?.descricao) {
      erros.push(`conteudos[${indice}] do tipo texto precisa de texto.descricao`);
    }
  }

  return erros;
}

function validarQuestao(questao) {
  const erros = [];

  if (!questao.materia_id) erros.push('materia_id é obrigatório');
  if (!questao.enunciado || !questao.enunciado.trim()) erros.push('enunciado é obrigatório');
  if (!DIFICULDADES_QUESTAO.includes(questao.dificuldade)) {
    erros.push(`dificuldade inválida para questão: "${questao.dificuldade}" (use ${DIFICULDADES_QUESTAO.join('|')})`);
  }

  const alternativas = questao.alternativas || [];
  if (alternativas.length < 2 || alternativas.length > 5) {
    erros.push(`alternativas deve ter entre 2 e 5 itens (encontrado: ${alternativas.length})`);
  }

  const letras = alternativas.map((a) => a.letra);
  if (new Set(letras).size !== letras.length) {
    erros.push('alternativas possuem letras duplicadas');
  }
  for (const alt of alternativas) {
    if (!LETRAS_VALIDAS.includes(alt.letra)) erros.push(`letra de alternativa inválida: "${alt.letra}"`);
    if (!alt.texto || !alt.texto.trim()) erros.push(`alternativa "${alt.letra}" sem texto`);
  }

  const corretas = alternativas.filter((a) => a.correta === true);
  if (corretas.length !== 1) {
    erros.push(`deve haver exatamente 1 alternativa correta (encontrado: ${corretas.length})`);
  }

  return erros;
}

// ---------------------------------------------------------------------------
// Garantia de matérias e tópicos
// ---------------------------------------------------------------------------

async function garantirMateria(api, materia, relatorio) {
  const busca = await api.get(`/admin/materias?busca=${encodeURIComponent(materia.nome)}&limite=100`);
  const existente = (busca.materias || []).find(
    (m) => m.nome.trim().toLowerCase() === materia.nome.trim().toLowerCase()
  );

  if (existente) {
    return existente.id;
  }

  try {
    const criada = await api.post('/admin/materias', {
      nome: materia.nome,
      area: materia.area,
      icone: materia.icone,
      cor: materia.cor,
      descricao: materia.descricao,
      ordem: 0,
      ativo: true,
    });
    return criada.materia.id;
  } catch (erro) {
    relatorio.erros.push(`[Matéria] ${materia.nome}: ${erro.message}`);
    return null;
  }
}

async function garantirTopicos(api, materiaId, nomesTopicos, relatorio) {
  const mapa = {};

  let existentes = [];
  try {
    const resposta = await api.get(`/admin/topicos/${materiaId}`);
    existentes = resposta.topicos || [];
  } catch (erro) {
    if (erro.status !== 404) {
      relatorio.erros.push(`[Tópicos] materia_id=${materiaId}: ${erro.message}`);
    }
  }

  for (const topico of existentes) {
    mapa[topico.nome?.trim().toLowerCase()] = topico.topico_id;
  }

  for (const nome of nomesTopicos) {
    const chave = nome.trim().toLowerCase();
    if (mapa[chave]) continue;

    try {
      const criado = await api.post('/admin/topicos', {
        materia_id: materiaId,
        nome,
        descricao: null,
        ordem: 0,
        icone: null,
        ativo: true,
      });
      mapa[chave] = criado.topico.id ?? criado.topico.topico_id;
    } catch (erro) {
      relatorio.erros.push(`[Tópico] ${nome}: ${erro.message}`);
    }
  }

  return mapa;
}

// ---------------------------------------------------------------------------
// Cadastro de aulas e questões
// ---------------------------------------------------------------------------

function montarPayloadAula(itemAula, materiaId, topicoId) {
  return {
    materia_id: materiaId,
    topico_id: topicoId || null,
    titulo: itemAula.titulo,
    resumo: itemAula.resumo ?? null,
    dificuldade: itemAula.dificuldade,
    mais_cobrado: !!itemAula.mais_cobrado,
    ordem: 0,
    ativo: true,
    conteudos: itemAula.conteudos.map((c) => ({
      tipo: c.tipo,
      ordem: c.ordem,
      duracao: c.duracao,
      ativo: c.ativo !== false,
      ...(c.tipo === 'video'
        ? { video: { titulo: c.titulo, video_link: c.video_link, descricao: c.descricao ?? null } }
        : { texto: { titulo: c.titulo, descricao: c.descricao } }),
    })),
  };
}

function montarPayloadQuestao(itemQuestao, materiaId, topicoId) {
  return {
    materia_id: materiaId,
    topico_id: topicoId || null,
    aula_id: null,
    tipo_prova_id: null,
    ano: itemQuestao.ano ?? null,
    dificuldade: itemQuestao.dificuldade,
    enunciado: itemQuestao.enunciado,
    imagem_url: itemQuestao.imagem_url ?? null,
    dica: itemQuestao.dica ?? null,
    explicacao: itemQuestao.explicacao ?? null,
    ativo: true,
    alternativas: itemQuestao.alternativas.map((a) => ({
      letra: a.letra,
      texto: a.texto,
      correta: !!a.correta,
    })),
  };
}

async function processarMateria(api, materia, config, relatorio) {
  const linha = {
    materia: materia.nome,
    aulasCriadas: 0,
    questoesCriadas: 0,
    erros: 0,
    status: 'ok',
  };

  const materiaId = await garantirMateria(api, materia, relatorio);
  if (!materiaId) {
    linha.status = 'falhou (matéria)';
    relatorio.linhas.push(linha);
    return;
  }

  const nomesTopicos = TOPICOS[materia.nome] || [];
  const mapaTopicos = await garantirTopicos(api, materiaId, nomesTopicos, relatorio);

  const conteudo = CONTEUDO[materia.nome] || { aulas: [], questoes: [] };

  const aulas = conteudo.aulas.slice(0, config.aulasPorMateria);
  for (const itemAula of aulas) {
    if (itemAula.verificado === false) {
      relatorio.avisos.push(
        `[Aula] "${itemAula.titulo}" (${materia.nome}): conteúdo não verificado — fonte "${itemAula.fonte}", revisar antes de publicar em produção.`
      );
    }

    const topicoId = mapaTopicos[itemAula.topico?.trim().toLowerCase()] || null;
    const payload = montarPayloadAula(itemAula, materiaId, topicoId);
    const errosValidacao = validarAula(payload);

    if (errosValidacao.length) {
      relatorio.erros.push(`[Aula] "${itemAula.titulo}": ${errosValidacao.join('; ')}`);
      linha.erros += 1;
      continue;
    }

    try {
      await api.post('/admin/aulas', payload);
      linha.aulasCriadas += 1;
      relatorio.backup.aulas.push({ materia: materia.nome, ...payload });
    } catch (erro) {
      relatorio.erros.push(`[Aula] "${itemAula.titulo}": ${erro.message}`);
      linha.erros += 1;
    }
  }

  const questoes = conteudo.questoes.slice(0, config.questoesPorMateria);
  for (const itemQuestao of questoes) {
    if (itemQuestao.verificado === false) {
      relatorio.avisos.push(
        `[Questão] "${itemQuestao.enunciado.slice(0, 60)}..." (${materia.nome}): conteúdo não verificado — fonte "${itemQuestao.fonte}", revisar antes de publicar em produção.`
      );
    }

    const topicoId = mapaTopicos[itemQuestao.topico?.trim().toLowerCase()] || null;
    const payload = montarPayloadQuestao(itemQuestao, materiaId, topicoId);
    const errosValidacao = validarQuestao(payload);

    if (errosValidacao.length) {
      relatorio.erros.push(`[Questão] "${itemQuestao.enunciado.slice(0, 60)}...": ${errosValidacao.join('; ')}`);
      linha.erros += 1;
      continue;
    }

    try {
      await api.post('/admin/questoes', payload);
      linha.questoesCriadas += 1;
      relatorio.backup.questoes.push({ materia: materia.nome, ...payload });
    } catch (erro) {
      relatorio.erros.push(`[Questão] "${itemQuestao.enunciado.slice(0, 60)}...": ${erro.message}`);
      linha.erros += 1;
    }
  }

  if (linha.erros > 0) linha.status = 'com erros';
  relatorio.linhas.push(linha);
}

// ---------------------------------------------------------------------------
// Relatório final
// ---------------------------------------------------------------------------

function gerarCsv(linhas) {
  const cabecalho = 'materia,aulas_criadas,questoes_criadas,erros,status';
  const corpo = linhas.map(
    (l) => `${l.materia},${l.aulasCriadas},${l.questoesCriadas},${l.erros},${l.status}`
  );
  return [cabecalho, ...corpo].join('\n');
}

function salvarRelatorios(relatorio) {
  const jsonPath = path.join(__dirname, 'resultado_cadastro.json');
  const csvPath = path.join(__dirname, 'resumo_cadastro.csv');

  fs.writeFileSync(
    jsonPath,
    JSON.stringify(
      {
        geradoEm: new Date().toISOString(),
        resumo: relatorio.linhas,
        avisos: relatorio.avisos,
        erros: relatorio.erros,
        backup: relatorio.backup,
      },
      null,
      2
    ),
    'utf-8'
  );

  fs.writeFileSync(csvPath, gerarCsv(relatorio.linhas), 'utf-8');

  return { jsonPath, csvPath };
}

// ---------------------------------------------------------------------------
// Execução principal
// ---------------------------------------------------------------------------

async function main() {
  const config = await coletarConfiguracao();
  const api = criarCliente(config.baseUrl, config.token);

  const relatorio = {
    linhas: [],
    avisos: [],
    erros: [],
    backup: { aulas: [], questoes: [] },
  };

  console.log(`\nPopulando ${MATERIAS.length} matérias (${config.aulasPorMateria} aulas e ${config.questoesPorMateria} questões cada)...\n`);

  for (const materia of MATERIAS) {
    console.log(`> Processando ${materia.nome}...`);
    await processarMateria(api, materia, config, relatorio);
  }

  const { jsonPath, csvPath } = salvarRelatorios(relatorio);

  console.log('\n=== Relatório final ===\n');
  console.table(
    relatorio.linhas.map((l) => ({
      Matéria: l.materia,
      'Aulas criadas': l.aulasCriadas,
      'Questões criadas': l.questoesCriadas,
      Erros: l.erros,
      Status: l.status,
    }))
  );

  if (relatorio.avisos.length) {
    console.log(`\nAvisos (${relatorio.avisos.length}):`);
    relatorio.avisos.forEach((a) => console.log(`  ⚠ ${a}`));
  }

  if (relatorio.erros.length) {
    console.log(`\nErros (${relatorio.erros.length}):`);
    relatorio.erros.forEach((e) => console.log(`  ✗ ${e}`));
  }

  console.log(`\nBackup salvo em: ${jsonPath}`);
  console.log(`Resumo CSV salvo em: ${csvPath}`);
}

main().catch((erro) => {
  console.error('\nFalha ao executar o script:', erro.message);
  process.exitCode = 1;
});
