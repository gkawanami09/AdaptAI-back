#!/usr/bin/env node
'use strict';

/**
 * Quarta leva de aulas adicionais (História e Redação), pesquisadas na
 * quinta rodada do usuário. Todos os itens conferidos via WebFetch + YouTube
 * oEmbed antes de entrar aqui.
 *
 * EXCLUÍDO por não existir: d8cLHxX3Khg ("Brasil Colônia — economia
 * colonial, escravidão e revoltas") — oEmbed devolveu 403 e a página real do
 * YouTube tem <title> vazio (" - YouTube"), sinal de vídeo indisponível/removido.
 *
 * EXCLUÍDOS por já estarem cadastrados: vVFWcUj1pDY, pqEDSyU6tsw,
 * HGrq8Eit31E, LgOmiodOGCE (História); WWfLsuP7yE8, iYlD_rOddSA, ebcqTD8Al7g
 * (Redação).
 */

const BASE_URL = process.env.ENEM_API_URL;
const TOKEN = process.env.ENEM_API_TOKEN;

const MATERIA_IDS = {
  História: '0d5da9e8-699c-4fb3-84b1-5b66f92ab6fa',
  Redação: 'a28a5651-7c92-4450-bb2d-fc00d3fc387d',
};

const NOVAS_AULAS = [
  // História
  {
    materia: 'História', topico: 'Escravidão no Brasil',
    titulo: 'Abolição da Escravidão no Brasil', dificuldade: 'medio', mais_cobrado: true,
    video: { titulo: 'ABOLIÇÃO DA ESCRAVIDÃO NO BRASIL | Resumo de História para o Enem', video_link: 'https://www.youtube.com/watch?v=ew0FRBxf2eM', descricao: 'Resumo sobre o processo de abolição da escravidão no Brasil.' }, duracao: 900,
  },
  {
    materia: 'História', topico: 'Era Vargas',
    titulo: 'Estado Novo (Era Vargas)', dificuldade: 'medio', mais_cobrado: true,
    video: { titulo: 'ESTADO NOVO (Era Vargas) | Resumo de História do Brasil para o Enem', video_link: 'https://www.youtube.com/watch?v=Biv7yyLtKwg', descricao: 'Resumo sobre o período do Estado Novo dentro da Era Vargas.' }, duracao: 900,
  },
  {
    materia: 'História', topico: 'Revolução Industrial',
    titulo: 'Revolução Industrial — Resumo', dificuldade: 'medio', mais_cobrado: false,
    video: { titulo: 'REVOLUÇÃO INDUSTRIAL | Resumo de História para o Enem', video_link: 'https://www.youtube.com/watch?v=NFrNx3JOXSg', descricao: 'Resumo da Revolução Industrial para o ENEM.' }, duracao: 900,
  },
  {
    materia: 'História', topico: 'Guerra Fria e Segunda Guerra Mundial',
    titulo: 'Guerra Fria entre EUA e URSS: Conflitos e Características', dificuldade: 'medio', mais_cobrado: true,
    video: { titulo: 'GUERRA FRIA ENTRE OS EUA E A URSS: conflitos e características | RESUMO DE HISTÓRIA ENEM. Prof Dudu', video_link: 'https://www.youtube.com/watch?v=mjqfi1mOKLI', descricao: 'Conflitos e características da Guerra Fria entre EUA e URSS.' }, duracao: 1080,
  },
  {
    materia: 'História', topico: 'Revolução Francesa',
    titulo: 'Idade Contemporânea em 30 min (Revolução Francesa à Guerra Fria)', dificuldade: 'medio', mais_cobrado: false,
    video: { titulo: 'HISTÓRIA ENEM: Idade Contemporânea em 30 MIN (Revolução Francesa à Guerra Fria)', video_link: 'https://www.youtube.com/watch?v=TqHP4j0Wnmo', descricao: 'Resumo da Idade Contemporânea, da Revolução Francesa até a Guerra Fria.' }, duracao: 1800,
  },

  // Redação
  {
    materia: 'Redação', topico: 'Competência 1 — norma culta da língua',
    titulo: 'Redação no Enem: Competência 1 — Brasil Escola', dificuldade: 'basico', mais_cobrado: true,
    video: { titulo: 'Redação no Enem: Competência 1 - Brasil Escola', video_link: 'https://www.youtube.com/watch?v=NPQhmWOrfC8', descricao: 'Explicação sobre a competência 1 (domínio da norma culta) da redação do ENEM.' }, duracao: 700,
  },
  {
    materia: 'Redação', topico: 'Competência 1 — norma culta da língua',
    titulo: 'Competência 1 da Redação: Dicas para Tirar 1000', dificuldade: 'basico', mais_cobrado: true,
    video: { titulo: 'COMPETÊNCIA 1 DA REDAÇÃO | Veja as dicas para tirar 1000 na correção do Enem', video_link: 'https://www.youtube.com/watch?v=IGUuClBtdcM', descricao: 'Dicas práticas para gabaritar a competência 1 da redação.' }, duracao: 900,
  },
  {
    materia: 'Redação', topico: 'Competência 2 — compreensão do tema',
    titulo: 'Redação no Enem: Competência 2 — Brasil Escola', dificuldade: 'medio', mais_cobrado: true,
    video: { titulo: 'Redação no Enem: Competência 2 - Brasil Escola', video_link: 'https://www.youtube.com/watch?v=IdmY5obS_-M', descricao: 'Explicação sobre a competência 2 (compreensão da proposta e do tema).' }, duracao: 700,
  },
  {
    materia: 'Redação', topico: 'Competência 3 — argumentação',
    titulo: 'Competência 3 da Redação: Como Planejar seu Texto', dificuldade: 'medio', mais_cobrado: true,
    video: { titulo: 'COMPETÊNCIA 3 DA REDAÇÃO DO ENEM: COMO PLANEJAR SEU TEXTO', video_link: 'https://www.youtube.com/watch?v=j5U7GgaWOYk', descricao: 'Como planejar o texto para gabaritar a competência 3.' }, duracao: 900,
  },
  {
    materia: 'Redação', topico: 'Competência 4 — coesão textual',
    titulo: 'Nota Máxima na Competência 4: Coesão e Coerência', dificuldade: 'medio', mais_cobrado: true,
    video: { titulo: 'NOTA MÁXIMA NA COMPETÊNCIA 4! COESÃO E COERÊNCIA NA REDAÇÃO ENEM 2023', video_link: 'https://www.youtube.com/watch?v=mTpoEtaeb8o', descricao: 'Como alcançar nota máxima na competência 4 (coesão e coerência).' }, duracao: 900,
  },
  {
    materia: 'Redação', topico: 'Competência 5 — proposta de intervenção',
    titulo: 'Competência 5: Como Tirar 200 Pontos na Proposta de Intervenção', dificuldade: 'medio', mais_cobrado: true,
    video: { titulo: 'COMPETÊNCIA 5 DA REDAÇÃO DO ENEM: COMO TIRAR 200 PONTOS NA PROPOSTA DE INTERVENÇÃO', video_link: 'https://www.youtube.com/watch?v=-VPsVrUxe9o', descricao: 'Como estruturar a proposta de intervenção para tirar nota máxima.' }, duracao: 900,
  },
  {
    materia: 'Redação', topico: 'Competência 5 — proposta de intervenção',
    titulo: 'Competência 5 — Proposta de Intervenção (Manual INEP)', dificuldade: 'medio', mais_cobrado: true,
    video: { titulo: 'Como tirar 1000 na redação do ENEM - Competência 5 - Proposta de Intervenção - Manual INEP', video_link: 'https://www.youtube.com/watch?v=-Vrm13v8ikU', descricao: 'Proposta de intervenção explicada com base no manual do INEP.' }, duracao: 1080,
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
