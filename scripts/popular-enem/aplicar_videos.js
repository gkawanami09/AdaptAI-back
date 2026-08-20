#!/usr/bin/env node
'use strict';

/**
 * Preenche o conteudo (video) das aulas pendentes cadastradas por popular.js,
 * usando os links reais pesquisados e verificados via WebFetch (ver videos_pendentes.json).
 */

const BASE_URL = process.env.ENEM_API_URL;
const TOKEN = process.env.ENEM_API_TOKEN;

const pendentes = require('./pendentes_nossos.json');
const videos = require('./videos_pendentes.json');

async function patchAula(aula, video) {
  const resposta = await fetch(`${BASE_URL}/admin/aulas/${aula.id}`, {
    method: 'PATCH',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${TOKEN}`,
    },
    body: JSON.stringify({
      conteudos: [
        {
          tipo: 'video',
          ordem: 0,
          duracao: video.duracao,
          ativo: true,
          video: {
            titulo: video.titulo,
            video_link: video.video_link,
            descricao: `Vídeo verificado via busca em 2026-08-19: "${video.titulo}".`,
          },
        },
      ],
    }),
  });

  const texto = await resposta.text();
  if (!resposta.ok) {
    throw new Error(`${resposta.status}: ${texto}`);
  }
  return JSON.parse(texto);
}

async function main() {
  let ok = 0;
  let falhas = [];

  for (const aula of pendentes) {
    const video = videos[aula.titulo];
    if (!video) {
      falhas.push({ titulo: aula.titulo, erro: 'sem vídeo mapeado' });
      continue;
    }
    try {
      await patchAula(aula, video);
      ok++;
      console.log(`OK: ${aula.titulo}`);
    } catch (erro) {
      falhas.push({ titulo: aula.titulo, erro: erro.message });
      console.log(`FALHOU: ${aula.titulo} -> ${erro.message}`);
    }
  }

  console.log(`\nConcluído. ${ok}/${pendentes.length} aulas atualizadas com vídeo real.`);
  if (falhas.length) {
    console.log(`${falhas.length} falhas:`);
    falhas.forEach((f) => console.log(`  - ${f.titulo}: ${f.erro}`));
  }
}

main();
