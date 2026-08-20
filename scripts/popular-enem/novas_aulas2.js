#!/usr/bin/env node
'use strict';

/**
 * Segunda leva de aulas adicionais (Biologia e Química), pesquisadas na
 * terceira rodada do usuário. Todos os 13 itens abaixo foram conferidos via
 * WebFetch antes de entrar aqui.
 *
 * EXCLUÍDOS por já estarem cadastrados (mesmo video_link já no banco):
 *  - KKELP-3_Dlk, Rr-zQYqRCzo, wlAR_cifwOM, JsLH-x_tSZ0, JmlI6bkigl8 (Biologia)
 *  - 7Z9CrQ4dVuY, z5GziuQoUxk (Química)
 * Os itens da seção "Extras identificados" do documento não foram
 * verificados nesta rodada — ficam de fora até serem checados.
 */

const BASE_URL = process.env.ENEM_API_URL;
const TOKEN = process.env.ENEM_API_TOKEN;

const MATERIA_IDS = {
  Biologia: '0aea872e-c91b-4cc0-9c94-c7aee3e57f62',
  Química: '451871f9-31be-487e-b64c-c01171ee91ea',
};

const NOVAS_AULAS = [
  // Biologia
  {
    materia: 'Biologia', topico: 'Ecologia — conceitos e cadeias alimentares',
    titulo: 'Ecologia — Introdução e Conceitos (Samuel Cunha)', dificuldade: 'basico', mais_cobrado: true,
    video: { titulo: 'ECOLOGIA - INTRODUÇÃO E CONCEITOS | Biologia com Samuel Cunha', video_link: 'https://www.youtube.com/watch?v=Z5cll6n3hHw', descricao: 'Introdução aos conceitos fundamentais de ecologia para o ENEM.' }, duracao: 900,
  },
  {
    materia: 'Biologia', topico: 'Evolução',
    titulo: 'Entenda a Teoria da Evolução', dificuldade: 'medio', mais_cobrado: false,
    video: { titulo: 'Entenda a Teoria da Evolução | BIOLOGIA - ENEM e Vestibulares', video_link: 'https://www.youtube.com/watch?v=h1jrNDPuvv8', descricao: 'Explicação da teoria da evolução biológica para o ENEM.' }, duracao: 1200,
  },
  {
    materia: 'Biologia', topico: 'Evolução',
    titulo: 'Evolução Biológica — Semana Inaugural ENEM 2020', dificuldade: 'medio', mais_cobrado: false,
    video: { titulo: 'AO VIVO | Biologia - ENEM 2020 | Evolução Biológica | Semana Inaugural', video_link: 'https://www.youtube.com/watch?v=8nXuRJPldXE', descricao: 'Aula ao vivo sobre evolução biológica.' }, duracao: 2880,
  },
  {
    materia: 'Biologia', topico: 'Evolução',
    titulo: 'Evolução no Enem — Brasil Escola', dificuldade: 'medio', mais_cobrado: false,
    video: { titulo: 'Evolução no Enem - Brasil Escola', video_link: 'https://www.youtube.com/watch?v=MkE5K9YFR9w', descricao: 'Como o tema evolução costuma ser cobrado no ENEM.' }, duracao: 700,
  },
  {
    materia: 'Biologia', topico: 'Evolução',
    titulo: 'Aula ao vivo: Ecologia, Genética e Evolução ENEM 2019', dificuldade: 'medio', mais_cobrado: true,
    video: { titulo: 'AULA AO VIVO: ECOLOGIA, GENÉTICA E EVOLUÇÃO ENEM 2019', video_link: 'https://www.youtube.com/watch?v=xTVNepq-6r8', descricao: 'Aulão cobrindo ecologia, genética e evolução juntas para o ENEM.' }, duracao: 5400,
  },

  // Química
  {
    materia: 'Química', topico: 'Estequiometria',
    titulo: 'Estequiometria — Resumo de Química para o Enem', dificuldade: 'basico', mais_cobrado: true,
    video: { titulo: 'ESTEQUIOMETRIA | Resumo de Química para o Enem', video_link: 'https://www.youtube.com/watch?v=HksYw1cX6FY', descricao: 'Resumo dos principais conceitos de estequiometria para o ENEM.' }, duracao: 1080,
  },
  {
    materia: 'Química', topico: 'Estequiometria',
    titulo: 'Revisão Enem Química: Estequiometria — Descomplica', dificuldade: 'basico', mais_cobrado: true,
    video: { titulo: 'REVISÃO ENEM | QUÍMICA: ESTEQUIOMETRIA | ESQUENTA ENEM | DESCOMPLICA', video_link: 'https://www.youtube.com/watch?v=SPc84n0ZBGY', descricao: 'Revisão de estequiometria pelo canal Descomplica.' }, duracao: 1320,
  },
  {
    materia: 'Química', topico: 'Estequiometria',
    titulo: 'Revisão de Química para o ENEM: Estequiometria', dificuldade: 'medio', mais_cobrado: true,
    video: { titulo: 'REVISÃO de QUÍMICA para o ENEM: ESTEQUIOMETRIA', video_link: 'https://www.youtube.com/watch?v=OYGdBvErrek', descricao: 'Revisão aprofundada de estequiometria para o ENEM.' }, duracao: 2100,
  },
  {
    materia: 'Química', topico: 'Estequiometria',
    titulo: 'Como Estequiometria Cai no ENEM', dificuldade: 'medio', mais_cobrado: true,
    video: { titulo: '🔥 COMO ESTEQUIOMETRIA CAI NO ENEM?', video_link: 'https://www.youtube.com/watch?v=Mza0Qn2mtMU', descricao: 'Análise de como a estequiometria costuma ser cobrada no ENEM.' }, duracao: 1500,
  },
  {
    materia: 'Química', topico: 'Termoquímica',
    titulo: 'Termoquímica — Variações de Entalpia', dificuldade: 'medio', mais_cobrado: true,
    video: { titulo: 'Química para o ENEM - Termoquímica (variações de entalpia)', video_link: 'https://www.youtube.com/watch?v=2xEjPZ9p1B8', descricao: 'Explicação sobre variações de entalpia em termoquímica.' }, duracao: 1680,
  },
  {
    materia: 'Química', topico: 'Ligações químicas',
    titulo: 'Química para o ENEM — Ligações Químicas', dificuldade: 'medio', mais_cobrado: false,
    video: { titulo: 'Química para o ENEM - Ligações químicas', video_link: 'https://www.youtube.com/watch?v=aVYn4HltbOc', descricao: 'Aula completa sobre ligações químicas para o ENEM.' }, duracao: 1800,
  },
  {
    materia: 'Química', topico: 'Ligações químicas',
    titulo: 'Ligações Químicas — Aula do Zero (Me Salva!)', dificuldade: 'basico', mais_cobrado: false,
    video: { titulo: 'Ligações Químicas | AULA do ZERO - Química | Me Salva! ENEM 2021', video_link: 'https://www.youtube.com/watch?v=X5xOEgJtCHU', descricao: 'Aula introdutória sobre ligações químicas, do zero.' }, duracao: 1320,
  },
  {
    materia: 'Química', topico: 'Química orgânica — funções orgânicas',
    titulo: 'A Química Orgânica Completa', dificuldade: 'dificil', mais_cobrado: true,
    video: { titulo: 'A QUÍMICA ORGÂNICA COMPLETA!! CARBONO, HIBRIDIZAÇÃO, CADEIA CARBÔNICA, RADICAIS, ETC.', video_link: 'https://www.youtube.com/watch?v=I_Wm0nhOGNc', descricao: 'Aula completa de química orgânica: carbono, hibridização, cadeias carbônicas e radicais.' }, duracao: 2700,
  },
];

async function apiPost(caminho, corpo) {
  const resposta = await fetch(`${BASE_URL}${caminho}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${TOKEN}` },
    body: JSON.stringify(corpo),
  });
  const texto = await resposta.text();
  if (!resposta.ok) throw new Error(`${resposta.status}: ${texto}`);
  return JSON.parse(texto);
}

async function apiGet(caminho) {
  const resposta = await fetch(`${BASE_URL}${caminho}`, { headers: { Authorization: `Bearer ${TOKEN}` } });
  const texto = await resposta.text();
  if (!resposta.ok) throw new Error(`${resposta.status}: ${texto}`);
  return JSON.parse(texto);
}

async function main() {
  const mapaTopicos = {};
  for (const [materia, materiaId] of Object.entries(MATERIA_IDS)) {
    const dados = await apiGet(`/admin/materias/${materiaId}/topicos`);
    mapaTopicos[materia] = {};
    for (const t of dados.topicos) mapaTopicos[materia][t.nome.trim().toLowerCase()] = t.topico_id;
  }

  let ok = 0;
  const falhas = [];

  for (const aula of NOVAS_AULAS) {
    const materiaId = MATERIA_IDS[aula.materia];
    const topicoId = mapaTopicos[aula.materia][aula.topico.trim().toLowerCase()] || null;

    const payload = {
      materia_id: materiaId,
      topico_id: topicoId,
      titulo: aula.titulo,
      resumo: null,
      dificuldade: aula.dificuldade,
      mais_cobrado: aula.mais_cobrado,
      ordem: 0,
      ativo: true,
      conteudos: [
        { tipo: 'video', ordem: 0, duracao: aula.duracao, ativo: true, video: aula.video },
      ],
    };

    try {
      await apiPost('/admin/aulas', payload);
      ok++;
      console.log(`OK: [${aula.materia}] ${aula.titulo}`);
    } catch (erro) {
      falhas.push({ titulo: aula.titulo, erro: erro.message });
      console.log(`FALHOU: [${aula.materia}] ${aula.titulo} -> ${erro.message}`);
    }
  }

  console.log(`\nConcluído. ${ok}/${NOVAS_AULAS.length} novas aulas cadastradas.`);
  if (falhas.length) {
    console.log(`${falhas.length} falhas:`);
    falhas.forEach((f) => console.log(`  - ${f.titulo}: ${f.erro}`));
  }
}

main();
