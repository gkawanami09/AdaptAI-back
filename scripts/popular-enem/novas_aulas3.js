#!/usr/bin/env node
'use strict';

/**
 * Terceira leva de aulas adicionais (Física e Geografia), pesquisadas na
 * quarta rodada do usuário. Todos os itens conferidos via WebFetch + YouTube
 * oEmbed antes de entrar aqui.
 *
 * EXCLUÍDO por não existir: Hv1hOFrfMAs ("Cinemática — exercícios
 * resolvidos") — o endpoint oficial oEmbed do YouTube devolve 404 para esse
 * vídeo, ou seja, o link não é real/está fora do ar.
 *
 * EXCLUÍDOS por já estarem cadastrados (mesmo video_link já no banco):
 *  - UM_RzhJakEQ, 2h9vDmzYmig (Física)
 *  - 2uXUSLF10R0, s27F-IRjekg, kb4Xxnmc7oY (Geografia)
 * "Extras identificados" do documento não foram verificados nesta rodada.
 */

const BASE_URL = process.env.ENEM_API_URL;
const TOKEN = process.env.ENEM_API_TOKEN;

const MATERIA_IDS = {
  Física: '85d35541-245b-4ee8-969a-a3451e393775',
  Geografia: '106df0d7-e9eb-4132-8a36-40ac3c22ede1',
};

const NOVAS_AULAS = [
  // Física
  {
    materia: 'Física', topico: 'Cinemática (MU e MUV)',
    titulo: 'Cinemática: Física para o ENEM', dificuldade: 'basico', mais_cobrado: true,
    video: { titulo: 'CINEMÁTICA: FÍSICA PARA O ENEM!', video_link: 'https://www.youtube.com/watch?v=cQHlNDwoT9M', descricao: 'Revisão completa de cinemática para o ENEM.' }, duracao: 900,
  },
  {
    materia: 'Física', topico: 'Leis de Newton',
    titulo: 'Com Certeza Cai no ENEM: Leis de Newton — Descomplica', dificuldade: 'medio', mais_cobrado: true,
    video: { titulo: 'AO VIVO | COM CERTEZA CAI NO ENEM: LEIS DE NEWTON | DESCOMPLICA', video_link: 'https://www.youtube.com/watch?v=Qqp_Gidms9w', descricao: 'Aula ao vivo sobre leis de Newton, tema recorrente no ENEM.' }, duracao: 2700,
  },
  {
    materia: 'Física', topico: 'Energia mecânica e trabalho',
    titulo: 'Energia Mecânica — Exercício Cinética e Potencial Gravitacional', dificuldade: 'medio', mais_cobrado: true,
    video: { titulo: 'ENERGIA MECÂNICA: exercício sobre energia cinética e potencial gravitacional | Física para o Enem', video_link: 'https://www.youtube.com/watch?v=LxPtRn1RmBA', descricao: 'Exercício resolvido de energia cinética e potencial gravitacional.' }, duracao: 900,
  },
  {
    materia: 'Física', topico: 'Energia mecânica e trabalho',
    titulo: 'Física para o ENEM — Energia Mecânica', dificuldade: 'medio', mais_cobrado: true,
    video: { titulo: 'Física para o ENEM - Energia mecânica', video_link: 'https://www.youtube.com/watch?v=NRVHSRRtZnE', descricao: 'Aula completa sobre energia mecânica para o ENEM.' }, duracao: 1200,
  },
  {
    materia: 'Física', topico: 'Eletrodinâmica (circuitos, potência elétrica)',
    titulo: 'Eletrodinâmica — Top Conteúdo ENEM 2023', dificuldade: 'medio', mais_cobrado: true,
    video: { titulo: 'Eletrodinâmica | Física | TOP CONTEÚDO ENEM 2023', video_link: 'https://www.youtube.com/watch?v=WgwmBwgWNnE', descricao: 'Revisão dos principais pontos de eletrodinâmica para o ENEM.' }, duracao: 1500,
  },
  {
    materia: 'Física', topico: 'Hidrostática (Pascal, Arquimedes, Stevin)',
    titulo: 'Resumo de Hidrostática — Descomplica', dificuldade: 'medio', mais_cobrado: false,
    video: { titulo: 'RESUMO DE HIDROSTÁTICA | Física para o ENEM | Descomplica', video_link: 'https://www.youtube.com/watch?v=50IGmzB2eCQ', descricao: 'Resumo de hidrostática (Pascal, Arquimedes, Stevin) para o ENEM.' }, duracao: 1080,
  },
  {
    materia: 'Física', topico: 'Hidrostática (Pascal, Arquimedes, Stevin)',
    titulo: 'Hidrostática — Teorema de Stevin', dificuldade: 'medio', mais_cobrado: false,
    video: { titulo: 'HIDROSTÁTICA | TEOREMA DE STEVIN | RESUMO PARA O ENEM', video_link: 'https://www.youtube.com/watch?v=M58YeFoINmk', descricao: 'Resumo focado no teorema de Stevin.' }, duracao: 900,
  },

  // Geografia
  {
    materia: 'Geografia', topico: 'Globalização',
    titulo: 'Globalização — Resumo de Geografia para o Enem', dificuldade: 'basico', mais_cobrado: true,
    video: { titulo: 'GLOBALIZAÇÃO | Resumo de Geografia para o Enem', video_link: 'https://www.youtube.com/watch?v=1JnFqa8bJps', descricao: 'Resumo do tema globalização para o ENEM.' }, duracao: 900,
  },
  {
    materia: 'Geografia', topico: 'Globalização',
    titulo: 'Globalização: Conceito, Pilares e Ferramentas', dificuldade: 'basico', mais_cobrado: true,
    video: { titulo: 'GLOBALIZAÇÃO: conceito, pilares e ferramentas | Geografia para o Enem | Prof. Eduardo', video_link: 'https://www.youtube.com/watch?v=w_vIXOXb7ls', descricao: 'Conceito, pilares e ferramentas da globalização.' }, duracao: 1080,
  },
  {
    materia: 'Geografia', topico: 'Geopolítica mundial',
    titulo: 'Geopolítica e Globalização — Prof. Saulo Takami', dificuldade: 'medio', mais_cobrado: true,
    video: { titulo: 'Geopolítica e Globalização - Geografia para ENEM e Vestibulares - Prof. Saulo Takami', video_link: 'https://www.youtube.com/watch?v=UiBxDFMgkI0', descricao: 'Relação entre geopolítica e globalização.' }, duracao: 1500,
  },
  {
    materia: 'Geografia', topico: 'Urbanização brasileira',
    titulo: 'A Urbanização Mundial: o Fenômeno Urbano', dificuldade: 'basico', mais_cobrado: true,
    video: { titulo: 'A urbanização mundial: o fenômeno urbano - Geografia - Ensino Médio', video_link: 'https://www.youtube.com/watch?v=ybmloQuzDg0', descricao: 'O fenômeno da urbanização mundial.' }, duracao: 900,
  },
  {
    materia: 'Geografia', topico: 'Urbanização brasileira',
    titulo: 'O que é Urbanização', dificuldade: 'basico', mais_cobrado: true,
    video: { titulo: 'O QUE É URBANIZAÇÃO? | Resumo de Geografia para o Enem', video_link: 'https://www.youtube.com/watch?v=hmXcEhWOp0k', descricao: 'Resumo introdutório sobre urbanização.' }, duracao: 700,
  },
  {
    materia: 'Geografia', topico: 'Demografia e população',
    titulo: 'Demografia e Transição Demográfica', dificuldade: 'basico', mais_cobrado: false,
    video: { titulo: 'DEMOGRAFIA E TRANSIÇÃO DEMOGRÁFICA | Resumo de Geografia Enem', video_link: 'https://www.youtube.com/watch?v=pQbVa6mO8kI', descricao: 'Resumo sobre demografia e transição demográfica.' }, duracao: 900,
  },
  {
    materia: 'Geografia', topico: 'Domínios morfoclimáticos do Brasil',
    titulo: 'Domínios Morfoclimáticos: Amazônia, Cerrado e Caatinga', dificuldade: 'medio', mais_cobrado: false,
    video: { titulo: 'Domínios morfoclimáticos brasileiros: amazônia, cerrado e caatinga - Geografia - Ensino Médio', video_link: 'https://www.youtube.com/watch?v=OIC3Xm5DEAU', descricao: 'Características dos domínios Amazônia, Cerrado e Caatinga.' }, duracao: 900,
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
