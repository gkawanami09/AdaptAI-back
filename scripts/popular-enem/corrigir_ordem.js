#!/usr/bin/env node
'use strict';

/**
 * Corrige o bug de ordem: todas as aulas cadastradas pelos scripts desta
 * pasta foram criadas com ordem=0 fixo, então dentro de cada tópico (ou
 * "sem tópico" dentro da matéria) várias aulas ficam empatadas em 0.
 * Renumera sequencialmente (1, 2, 3, ...) dentro de cada grupo
 * materia_id+topico_id, ordenando por criado_em (ordem de criação).
 */

const BASE_URL = process.env.ENEM_API_URL || 'http://127.0.0.1:8000';
const EMAIL = process.env.ENEM_LOGIN_EMAIL;
const SENHA = process.env.ENEM_LOGIN_SENHA;

async function login() {
  const r = await fetch(`${BASE_URL}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email: EMAIL, senha: SENHA }),
  });
  const d = await r.json();
  if (!r.ok) throw new Error(`Login falhou: ${r.status} ${JSON.stringify(d)}`);
  if (d.usuario.tipo_usuario !== 'admin') throw new Error(`Conta não é admin (tipo_usuario=${d.usuario.tipo_usuario})`);
  return d.session.access_token;
}

async function main() {
  const token = await login();
  const headers = { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` };

  let todas = [];
  let pagina = 1;
  while (true) {
    const r = await fetch(`${BASE_URL}/admin/aulas?limite=50&pagina=${pagina}`, { headers });
    const d = await r.json();
    if (!d.aulas || d.aulas.length === 0) break;
    todas = todas.concat(d.aulas);
    if (todas.length >= d.total_registros) break;
    pagina++;
  }

  console.log(`Total de aulas no banco: ${todas.length}`);

  const grupos = new Map();
  for (const aula of todas) {
    const chave = `${aula.materia_id}::${aula.topico_id || 'sem-topico'}`;
    if (!grupos.has(chave)) grupos.set(chave, []);
    grupos.get(chave).push(aula);
  }

  const patches = [];
  for (const [, aulas] of grupos) {
    aulas.sort((a, b) => new Date(a.criado_em) - new Date(b.criado_em));
    aulas.forEach((aula, indice) => {
      const novaOrdem = indice + 1;
      if (aula.ordem !== novaOrdem) {
        patches.push({ id: aula.id, titulo: aula.titulo, de: aula.ordem, para: novaOrdem });
      }
    });
  }

  console.log(`Aulas a corrigir: ${patches.length} de ${todas.length}`);

  let ok = 0;
  for (const p of patches) {
    try {
      const r = await fetch(`${BASE_URL}/admin/aulas/${p.id}`, {
        method: 'PATCH',
        headers,
        body: JSON.stringify({ ordem: p.para }),
      });
      const texto = await r.text();
      if (!r.ok) throw new Error(`${r.status}: ${texto}`);
      ok++;
    } catch (erro) {
      console.log(`FALHOU: ${p.titulo} (${p.de} -> ${p.para}) -> ${erro.message}`);
    }
  }

  console.log(`\nConcluído. ${ok}/${patches.length} aulas renumeradas.`);
}

main().catch((e) => { console.error('ERRO FATAL:', e.message); process.exitCode = 1; });
