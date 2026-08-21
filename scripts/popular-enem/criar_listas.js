#!/usr/bin/env node
'use strict';

/**
 * Cria uma lista de questões "fixa" por matéria, reunindo todas as questões
 * cadastradas atualmente para aquela matéria (POST /admin/listas-questoes).
 */

const BASE_URL = process.env.ENEM_API_URL || 'http://127.0.0.1:8000';

async function obterToken() {
  if (process.env.ENEM_API_TOKEN) return process.env.ENEM_API_TOKEN;
  const r = await fetch(`${BASE_URL}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email: process.env.ENEM_LOGIN_EMAIL, senha: process.env.ENEM_LOGIN_SENHA }),
  });
  const d = await r.json();
  if (!r.ok) throw new Error(`Login falhou: ${r.status} ${JSON.stringify(d)}`);
  if (d.usuario.tipo_usuario !== 'admin') throw new Error(`Conta não é admin`);
  return d.session.access_token;
}

function cliente(token) {
  const headers = { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` };
  return {
    get: async (p) => {
      const r = await fetch(`${BASE_URL}${p}`, { headers });
      const t = await r.text();
      if (!r.ok) throw new Error(`GET ${p} -> ${r.status}: ${t}`);
      return JSON.parse(t);
    },
    post: async (p, body) => {
      const r = await fetch(`${BASE_URL}${p}`, { method: 'POST', headers, body: JSON.stringify(body) });
      const t = await r.text();
      if (!r.ok) throw new Error(`POST ${p} -> ${r.status}: ${t}`);
      return JSON.parse(t);
    },
  };
}

async function main() {
  const token = await obterToken();
  const api = cliente(token);

  const materiasResp = await api.get('/admin/materias?limite=100');

  let ok = 0;
  for (const materia of materiasResp.materias) {
    const questoesResp = await api.get(`/admin/questoes?materia_id=${materia.id}&limite=50&ativo=true`);
    const questoes = questoesResp.questoes || [];
    if (questoes.length === 0) continue;

    const payload = {
      titulo: `Questões de ${materia.nome} — ENEM`,
      descricao: `Lista com as questões cadastradas para ${materia.nome}.`,
      tipo_prova_id: null,
      materia_id: materia.id,
      topico_id: null,
      dificuldade: null,
      tipo_lista: 'fixa',
      itens: questoes.map((q, indice) => ({ questao_id: q.id, ordem: indice })),
    };

    try {
      await api.post('/admin/listas-questoes', payload);
      ok++;
      console.log(`OK: "${payload.titulo}" (${questoes.length} questões)`);
    } catch (erro) {
      console.log(`FALHOU: "${payload.titulo}" -> ${erro.message}`);
    }
  }

  console.log(`\nConcluído. ${ok} listas criadas.`);
}

main().catch((e) => { console.error('ERRO FATAL:', e.message); process.exitCode = 1; });
