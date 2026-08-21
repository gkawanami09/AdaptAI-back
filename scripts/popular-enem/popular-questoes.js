#!/usr/bin/env node
'use strict';

/**
 * Popula questões via POST /admin/questoes, a partir de data-questoes.js.
 * Lê nomes (materia/topico/tipoProva) e resolve para UUID em tempo de
 * execução — assim data-questoes.js pode crescer a cada novo lote sem
 * precisar saber IDs de antemão.
 *
 * Login: reaproveita o padrão dos scripts de aulas — variáveis de ambiente
 * ENEM_API_URL + (ENEM_API_TOKEN pronto, ou ENEM_LOGIN_EMAIL/ENEM_LOGIN_SENHA
 * pra logar e pegar um token novo). Precisa ser uma conta com tipo_usuario=admin.
 */

const fs = require('fs');
const path = require('path');

const { QUESTOES } = require('./data-questoes');

const BASE_URL = process.env.ENEM_API_URL || 'http://127.0.0.1:8000';
const DIFICULDADES_VALIDAS = ['facil', 'medio', 'dificil'];
const LETRAS_VALIDAS = ['A', 'B', 'C', 'D', 'E'];

async function obterToken() {
  if (process.env.ENEM_API_TOKEN) return process.env.ENEM_API_TOKEN;

  const email = process.env.ENEM_LOGIN_EMAIL;
  const senha = process.env.ENEM_LOGIN_SENHA;
  if (!email || !senha) {
    throw new Error('Defina ENEM_API_TOKEN, ou ENEM_LOGIN_EMAIL + ENEM_LOGIN_SENHA (conta admin).');
  }

  const r = await fetch(`${BASE_URL}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, senha }),
  });
  const d = await r.json();
  if (!r.ok) throw new Error(`Login falhou: ${r.status} ${JSON.stringify(d)}`);
  if (d.usuario.tipo_usuario !== 'admin') {
    throw new Error(`Conta não é admin (tipo_usuario=${d.usuario.tipo_usuario})`);
  }
  return d.session.access_token;
}

function criarCliente(token) {
  const headers = { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` };
  return {
    get: async (caminho) => {
      const r = await fetch(`${BASE_URL}${caminho}`, { headers });
      const t = await r.text();
      if (!r.ok) throw new Error(`GET ${caminho} -> ${r.status}: ${t}`);
      return JSON.parse(t);
    },
    post: async (caminho, corpo) => {
      const r = await fetch(`${BASE_URL}${caminho}`, { method: 'POST', headers, body: JSON.stringify(corpo) });
      const t = await r.text();
      if (!r.ok) throw new Error(`${r.status}: ${t}`);
      return JSON.parse(t);
    },
  };
}

function validarQuestao(q) {
  const erros = [];

  if (!q.enunciado || !q.enunciado.trim()) erros.push('enunciado vazio');
  if (!DIFICULDADES_VALIDAS.includes(q.dificuldade)) {
    erros.push(`dificuldade inválida: "${q.dificuldade}" (use ${DIFICULDADES_VALIDAS.join('|')} — não confundir com o enum de aula, que usa "basico")`);
  }

  const alternativas = q.alternativas || [];
  if (alternativas.length < 2 || alternativas.length > 5) {
    erros.push(`alternativas deve ter entre 2 e 5 itens (encontrado: ${alternativas.length})`);
  }
  const letras = alternativas.map((a) => a.letra);
  if (new Set(letras).size !== letras.length) erros.push('letras de alternativa duplicadas');
  for (const alt of alternativas) {
    if (!LETRAS_VALIDAS.includes(alt.letra)) erros.push(`letra inválida: "${alt.letra}"`);
    if (!alt.texto || !alt.texto.trim()) erros.push(`alternativa "${alt.letra}" sem texto`);
  }
  const corretas = alternativas.filter((a) => a.correta === true);
  if (corretas.length !== 1) erros.push(`deve haver exatamente 1 alternativa correta (encontrado: ${corretas.length})`);

  return erros;
}

async function main() {
  console.log('Fazendo login...');
  const token = await obterToken();
  const api = criarCliente(token);
  console.log('Login OK.\n');

  const materiasResp = await api.get('/admin/materias?limite=100');
  const materiaIdPorNome = {};
  for (const m of materiasResp.materias) materiaIdPorNome[m.nome.trim().toLowerCase()] = m.id;

  const tiposProvaResp = await api.get('/admin/tipos-prova?limite=50');
  const tipoProvaIdPorNome = {};
  for (const t of tiposProvaResp.tipos_prova || tiposProvaResp.tipos || []) {
    tipoProvaIdPorNome[t.nome.trim().toLowerCase()] = t.id;
  }

  const mapaTopicos = {};
  async function topicoId(materiaNome, topicoNome) {
    if (!topicoNome) return null;
    const chaveMateria = materiaNome.trim().toLowerCase();
    if (!mapaTopicos[chaveMateria]) {
      const materiaId = materiaIdPorNome[chaveMateria];
      const resp = await api.get(`/admin/materias/${materiaId}/topicos`);
      mapaTopicos[chaveMateria] = {};
      for (const t of resp.topicos) mapaTopicos[chaveMateria][t.nome.trim().toLowerCase()] = t.topico_id;
    }
    return mapaTopicos[chaveMateria][topicoNome.trim().toLowerCase()] || null;
  }

  async function jaExiste(materiaId, enunciado) {
    const trecho = enunciado.slice(0, 60);
    const resp = await api.get(
      `/admin/questoes?materia_id=${materiaId}&busca=${encodeURIComponent(trecho)}&limite=10`
    );
    return (resp.questoes || []).some((q) => q.enunciado.trim() === enunciado.trim());
  }

  const relatorio = { linhas: [], backup: [] };

  for (const q of QUESTOES) {
    const linha = {
      materia: q.materia,
      topico: q.topico || '',
      ano: q.ano ?? '',
      fonte: q.fonte || '',
      verificado: q.verificado !== false,
      status: '',
    };

    const materiaId = materiaIdPorNome[q.materia.trim().toLowerCase()];
    if (!materiaId) {
      linha.status = `erro: matéria "${q.materia}" não encontrada`;
      relatorio.linhas.push(linha);
      console.log(`FALHOU: ${linha.status}`);
      continue;
    }

    const erros = validarQuestao(q);
    if (erros.length) {
      linha.status = `erro de validação: ${erros.join('; ')}`;
      relatorio.linhas.push(linha);
      console.log(`FALHOU: [${q.materia}] ${q.enunciado.slice(0, 50)}... -> ${linha.status}`);
      continue;
    }

    if (await jaExiste(materiaId, q.enunciado)) {
      linha.status = 'pulada (já existe — mesmo enunciado)';
      relatorio.linhas.push(linha);
      console.log(`PULADA (duplicada): [${q.materia}] ${q.enunciado.slice(0, 50)}...`);
      continue;
    }

    const payload = {
      materia_id: materiaId,
      topico_id: await topicoId(q.materia, q.topico),
      aula_id: null,
      tipo_prova_id: q.tipoProva ? tipoProvaIdPorNome[q.tipoProva.trim().toLowerCase()] || null : null,
      ano: q.ano ?? null,
      dificuldade: q.dificuldade,
      enunciado: q.enunciado,
      imagem_url: q.imagem_url ?? null,
      dica: q.dica ?? null,
      explicacao: q.explicacao ?? null,
      ativo: true,
      alternativas: q.alternativas.map((a) => ({ letra: a.letra, texto: a.texto, correta: !!a.correta })),
    };

    try {
      await api.post('/admin/questoes', payload);
      linha.status = 'ok';
      relatorio.backup.push({ ...q, materia_id: materiaId, topico_id: payload.topico_id });
      console.log(`OK: [${q.materia}] ${q.enunciado.slice(0, 60)}...`);
    } catch (erro) {
      linha.status = `falhou: ${erro.message}`;
      console.log(`FALHOU: [${q.materia}] ${q.enunciado.slice(0, 50)}... -> ${erro.message}`);
    }
    relatorio.linhas.push(linha);
  }

  const jsonPath = path.join(__dirname, 'resultado_questoes.json');
  const csvPath = path.join(__dirname, 'resumo_questoes.csv');
  fs.writeFileSync(jsonPath, JSON.stringify(relatorio, null, 2), 'utf-8');
  fs.writeFileSync(
    csvPath,
    ['materia,topico,ano,fonte,verificado,status', ...relatorio.linhas.map((l) =>
      [l.materia, l.topico, l.ano, `"${(l.fonte || '').replace(/"/g, "'")}"`, l.verificado, l.status].join(',')
    )].join('\n'),
    'utf-8'
  );

  console.log('\n=== Resumo ===');
  console.table(relatorio.linhas.map((l) => ({
    Matéria: l.materia,
    Tópico: l.topico,
    Ano: l.ano,
    Verificado: l.verificado,
    Status: l.status,
  })));
  console.log(`\nBackup: ${jsonPath}`);
  console.log(`CSV: ${csvPath}`);
}

main().catch((e) => { console.error('ERRO FATAL:', e.message); process.exitCode = 1; });
