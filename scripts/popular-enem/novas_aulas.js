#!/usr/bin/env node
'use strict';

/**
 * Aulas adicionais pesquisadas na segunda rodada do usuário (Matemática e
 * Português). Cada item foi conferido via WebFetch/HTTP antes de ir para cá.
 *
 * Itens EXCLUÍDOS por não terem passado na verificação:
 *  - 4 links do Khan Academy com slug profundo (estatística, desvio-padrão,
 *    probabilidade, função quadrática): o domínio khanacademy.org é uma SPA
 *    que devolve HTTP 200 para QUALQUER caminho, inclusive inexistente — não
 *    dá pra confirmar que aquele slug específico existe de verdade.
 *  - 3 vídeos que já estão cadastrados no banco (duplicados): X5BUC6Lc8gw
 *    (Estatística), hj51vJWZZ-A (Função quadrática), RXqDkeK6Qbg (Coesão).
 */

const BASE_URL = process.env.ENEM_API_URL;
const TOKEN = process.env.ENEM_API_TOKEN;

const MATERIA_IDS = {
  Matemática: 'c29992d5-8063-405e-89e8-236cec8ffc2d',
  Português: '94fd268b-7003-4ce5-b63f-9ddf8cc877c7',
};

const NOVAS_AULAS = [
  // Matemática
  {
    materia: 'Matemática',
    topico: 'Razão, proporção e regra de três',
    titulo: 'Regra de três simples — Blog do Enem',
    dificuldade: 'basico',
    mais_cobrado: true,
    conteudo: {
      tipo: 'texto',
      duracao: 480,
      texto: {
        titulo: 'Regra de três simples — Blog do Enem',
        descricao: 'Artigo do Blog do Enem sobre regra de três simples, com referência ao vídeo do Khan Academy traduzido pela Fundação Lemann. Fonte: https://blogdoenem.com.br/matematica-enem-regra-de-tres-simples/',
      },
    },
  },
  {
    materia: 'Matemática',
    topico: 'Razão, proporção e regra de três',
    titulo: 'Razão, proporção e regra de três composta — Blog do Enem',
    dificuldade: 'basico',
    mais_cobrado: true,
    conteudo: {
      tipo: 'texto',
      duracao: 480,
      texto: {
        titulo: 'Razão, proporção e regra de três composta — Blog do Enem',
        descricao: 'Artigo do Blog do Enem sobre regra de três composta, com exemplos práticos (obra com trabalhadores, horas e dias). Fonte: https://blogdoenem.com.br/razao-proporcao-matematica-enem/',
      },
    },
  },
  {
    materia: 'Matemática',
    topico: 'Porcentagem',
    titulo: 'Porcentagem Utilizando Regra de Três - Brasil Escola',
    dificuldade: 'basico',
    mais_cobrado: true,
    conteudo: {
      tipo: 'video',
      duracao: 700,
      video: {
        titulo: 'Porcentagem Utilizando Regra de Três - Brasil Escola',
        video_link: 'https://www.youtube.com/watch?v=jGnossl7ggQ',
        descricao: 'Como resolver problemas de porcentagem usando o método de regra de três.',
      },
    },
  },

  // Português
  {
    materia: 'Português',
    topico: 'Funções da linguagem',
    titulo: 'Interpretação de Texto ENEM: Questão sobre Funções da Linguagem',
    dificuldade: 'medio',
    mais_cobrado: false,
    conteudo: {
      tipo: 'video',
      duracao: 700,
      video: {
        titulo: 'Interpretação de Texto ENEM: Questão sobre FUNÇÕES DA LINGUAGEM',
        video_link: 'https://www.youtube.com/watch?v=1XgbOcZWXnE',
        descricao: 'Resolução comentada de questão do ENEM sobre funções da linguagem.',
      },
    },
  },
  {
    materia: 'Português',
    topico: 'Funções da linguagem',
    titulo: 'Função Metalinguística da Linguagem',
    dificuldade: 'basico',
    mais_cobrado: false,
    conteudo: {
      tipo: 'video',
      duracao: 700,
      video: {
        titulo: 'FUNÇÃO METALINGUÍSTICA DA LINGUAGEM | INTERPRETAÇÃO DE TEXTO NO ENEM - Aula de Português',
        video_link: 'https://www.youtube.com/watch?v=lVm_5EmyhpQ',
        descricao: 'Explicação da função metalinguística e como ela é cobrada em questões do ENEM.',
      },
    },
  },
  {
    materia: 'Português',
    topico: 'Variação linguística',
    titulo: 'Variações Linguísticas — Resumo de Português para o Enem',
    dificuldade: 'basico',
    mais_cobrado: true,
    conteudo: {
      tipo: 'video',
      duracao: 700,
      video: {
        titulo: 'VARIAÇÕES LINGUÍSTICAS | Resumo de Português para o Enem',
        video_link: 'https://www.youtube.com/watch?v=EdMkT69cVjs',
        descricao: 'Resumo dos tipos de variação linguística cobrados no ENEM.',
      },
    },
  },
  {
    materia: 'Português',
    topico: 'Variação linguística',
    titulo: 'Exercícios de Variação Linguística',
    dificuldade: 'medio',
    mais_cobrado: false,
    conteudo: {
      tipo: 'video',
      duracao: 700,
      video: {
        titulo: 'Exercícios de Variação Linguística [Prof Noslen]',
        video_link: 'https://www.youtube.com/watch?v=dffRZNrhQ7w',
        descricao: 'Resolução de exercícios sobre variação linguística no estilo ENEM.',
      },
    },
  },
  {
    materia: 'Português',
    topico: 'Coesão e coerência textual',
    titulo: 'Coesão e coerência — Prof. Noslen',
    dificuldade: 'medio',
    mais_cobrado: false,
    conteudo: {
      tipo: 'video',
      duracao: 700,
      video: {
        titulo: 'Coesão e coerência [Prof. Noslen]',
        video_link: 'https://www.youtube.com/watch?v=IIU6i3UXyi0',
        descricao: 'Explicação sobre coesão e coerência textual para o ENEM.',
      },
    },
  },
  {
    materia: 'Português',
    topico: 'Gêneros textuais',
    titulo: 'Gêneros Textuais: Aprenda de forma Fácil e Rápida',
    dificuldade: 'basico',
    mais_cobrado: false,
    conteudo: {
      tipo: 'video',
      duracao: 700,
      video: {
        titulo: 'Gêneros Textuais: Aprenda de forma FÁCIL E RÁPIDA!',
        video_link: 'https://www.youtube.com/watch?v=qNDreTc3w0s',
        descricao: 'Explicação rápida sobre os principais gêneros textuais cobrados no ENEM.',
      },
    },
  },
  {
    materia: 'Português',
    topico: 'Modernismo',
    titulo: 'Modernismo brasileiro — Lá Vem o Enem (Rede Paraíba)',
    dificuldade: 'medio',
    mais_cobrado: true,
    conteudo: {
      tipo: 'texto',
      duracao: 900,
      texto: {
        titulo: 'Modernismo brasileiro — Lá Vem o Enem (Rede Paraíba)',
        descricao: 'Videoaula do Prof. Rodrigo Paes sobre as três gerações do Modernismo brasileiro (1922-1960), produzida pela Rede Paraíba. Fonte: https://jornaldaparaiba.com.br/educacao/la-vem-o-enem-videoaula-literatura-modernismo',
      },
    },
  },
  {
    materia: 'Português',
    topico: 'Figuras de linguagem',
    titulo: 'Figuras de linguagem no ENEM — PrePara Enem',
    dificuldade: 'medio',
    mais_cobrado: false,
    conteudo: {
      tipo: 'texto',
      duracao: 600,
      texto: {
        titulo: 'Figuras de linguagem no ENEM — PrePara Enem',
        descricao: 'Artigo com as 7 figuras de linguagem mais cobradas no ENEM (ironia, comparação, metáfora, metonímia, elipse, antítese, paradoxo) e 2 questões comentadas. Fonte: https://www.preparaenem.com/enem/figuras-de-linguagem-no-enem.htm',
      },
    },
  },
  {
    materia: 'Português',
    topico: 'Intertextualidade',
    titulo: 'Intertextualidade, interdiscursividade e paródia no ENEM — PrePara Enem',
    dificuldade: 'medio',
    mais_cobrado: false,
    conteudo: {
      tipo: 'texto',
      duracao: 600,
      texto: {
        titulo: 'Intertextualidade, interdiscursividade e paródia no ENEM — PrePara Enem',
        descricao: 'Artigo com definições de intertextualidade, interdiscursividade e paródia, exemplos literários (Drummond, Chico Buarque) e 6 questões comentadas. Fonte: https://www.preparaenem.com/enem/intertextualidade-interdiscursividade-e-parodia-no-enem.htm',
      },
    },
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
  const resposta = await fetch(`${BASE_URL}${caminho}`, {
    headers: { Authorization: `Bearer ${TOKEN}` },
  });
  const texto = await resposta.text();
  if (!resposta.ok) throw new Error(`${resposta.status}: ${texto}`);
  return JSON.parse(texto);
}

async function main() {
  const mapaTopicos = {};
  for (const [materia, materiaId] of Object.entries(MATERIA_IDS)) {
    const dados = await apiGet(`/admin/materias/${materiaId}/topicos`);
    mapaTopicos[materia] = {};
    for (const t of dados.topicos) {
      mapaTopicos[materia][t.nome.trim().toLowerCase()] = t.topico_id;
    }
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
        {
          tipo: aula.conteudo.tipo,
          ordem: 0,
          duracao: aula.conteudo.duracao,
          ativo: true,
          ...(aula.conteudo.tipo === 'video' ? { video: aula.conteudo.video } : { texto: aula.conteudo.texto }),
        },
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
