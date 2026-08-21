#!/usr/bin/env node
'use strict';

/**
 * Aplica a revisão de qualidade (Matemática/Português/Biologia/Química/Física):
 *  1. Prefixa o título de aulas já cadastradas que são live/exercício (Física).
 *  2. Cadastra os vídeos novos e verificados (título conferido via oEmbed do
 *     YouTube, mais confiável que WebFetch) para Português, Biologia e Química.
 *
 * Login feito com a conta de admin no início do processo (token de curta
 * duração não é persistido em nenhum arquivo).
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
    patch: async (p, body) => {
      const r = await fetch(`${BASE_URL}${p}`, { method: 'PATCH', headers, body: JSON.stringify(body) });
      const t = await r.text();
      if (!r.ok) throw new Error(`PATCH ${p} -> ${r.status}: ${t}`);
      return JSON.parse(t);
    },
  };
}

const MATERIAS = {
  Matemática: 'c29992d5-8063-405e-89e8-236cec8ffc2d',
  Português: '94fd268b-7003-4ce5-b63f-9ddf8cc877c7',
  Biologia: '0aea872e-c91b-4cc0-9c94-c7aee3e57f62',
  Química: '451871f9-31be-487e-b64c-c01171ee91ea',
  Física: '85d35541-245b-4ee8-969a-a3451e393775',
};

// --- 1) Prefixos de título em aulas já cadastradas (Física) ---------------
const RENOMEAR = [
  {
    materia: 'Física',
    tituloAtual: 'Cinemática: Física para o ENEM',
    novoTitulo: '[Live de revisão] Cinemática: Física para o ENEM',
    video: { titulo: '[Live de revisão] Cinemática: Física para o ENEM', video_link: 'https://www.youtube.com/watch?v=cQHlNDwoT9M', descricao: 'Live de revisão de cinemática para o ENEM.' },
    duracao: 900,
  },
  {
    materia: 'Física',
    tituloAtual: 'Com Certeza Cai no ENEM: Leis de Newton — Descomplica',
    novoTitulo: '[Live] Com Certeza Cai no ENEM: Leis de Newton — Descomplica',
    video: { titulo: '[Live] Com Certeza Cai no ENEM: Leis de Newton — Descomplica', video_link: 'https://www.youtube.com/watch?v=Qqp_Gidms9w', descricao: 'Aula ao vivo (live) sobre leis de Newton, tema recorrente no ENEM.' },
    duracao: 2700,
  },
  {
    materia: 'Física',
    tituloAtual: 'Energia Mecânica — Exercício Cinética e Potencial Gravitacional',
    novoTitulo: '[Exercícios resolvidos] Energia Mecânica — Cinética e Potencial Gravitacional',
    video: { titulo: '[Exercícios resolvidos] Energia Mecânica — Cinética e Potencial Gravitacional', video_link: 'https://www.youtube.com/watch?v=LxPtRn1RmBA', descricao: 'Exercício resolvido de energia cinética e potencial gravitacional.' },
    duracao: 900,
  },
];

// --- 2) Aulas novas verificadas via oEmbed ---------------------------------
const NOVAS_AULAS = [
  // Português
  { materia: 'Português', topico: 'Interpretação de texto', titulo: 'Norma Culta x Língua Falada', dificuldade: 'basico', mais_cobrado: false,
    video: { titulo: 'NORMA CULTA x LÍNGUA FALADA | INTERPRETAÇÃO DE TEXTO NO ENEM - Aula de Português', video_link: 'https://www.youtube.com/watch?v=Op0Xjo8ub8c', descricao: 'Diferenças entre norma culta e língua falada na interpretação de texto.' }, duracao: 700 },
  { materia: 'Português', topico: 'Interpretação de texto', titulo: 'Linguagem Formal x Linguagem Informal', dificuldade: 'basico', mais_cobrado: false,
    video: { titulo: 'LINGUAGEM FORMAL x LINGUAGEM INFORMAL | INTERPRETAÇÃO DE TEXTO NO ENEM - Aula de Português', video_link: 'https://www.youtube.com/watch?v=UDs5B5JUE8g', descricao: 'Diferenças entre linguagem formal e informal na interpretação de texto.' }, duracao: 700 },
  { materia: 'Português', topico: 'Funções da linguagem', titulo: 'Ícone, Índice e Símbolo (Tipos de Signo)', dificuldade: 'medio', mais_cobrado: false,
    video: { titulo: 'ÍCONE, ÍNDICE E SÍMBOLO (TIPOS DE SIGNO) | Resumo de Português para o Enem', video_link: 'https://www.youtube.com/watch?v=DVZVJ4SB0pI', descricao: 'Tipos de signo (semiótica) cobrados no ENEM.' }, duracao: 700 },
  { materia: 'Português', topico: 'Variação linguística', titulo: 'Norma Culta e Linguagem Coloquial', dificuldade: 'basico', mais_cobrado: true,
    video: { titulo: 'NORMA CULTA E LINGUAGEM COLOQUIAL | Resumo de Português para o Enem. Professora Mercedes Bonorino', video_link: 'https://www.youtube.com/watch?v=ICSjP_tFqgc', descricao: 'Diferenças entre norma culta e linguagem coloquial.' }, duracao: 700 },
  { materia: 'Português', topico: 'Funções da linguagem', titulo: 'Linguagem Verbal e Não Verbal', dificuldade: 'basico', mais_cobrado: false,
    video: { titulo: 'LINGUAGEM VERBAL E NÃO VERBAL | Resumo de Português para o Enem', video_link: 'https://www.youtube.com/watch?v=Aw7CZ8ysHbo', descricao: 'Diferenças entre linguagem verbal e não verbal.' }, duracao: 700 },
  { materia: 'Português', topico: 'Variação linguística', titulo: '[Exercícios resolvidos] Norma Culta x Linguagem Coloquial', dificuldade: 'medio', mais_cobrado: false,
    video: { titulo: 'NORMA CULTA X LINGUAGEM COLOQUIAL (EXERCÍCIOS RESOLVIDOS) | Resumo de Português para o Enem', video_link: 'https://www.youtube.com/watch?v=XRvQBRZ_ucA', descricao: 'Exercícios resolvidos sobre norma culta x linguagem coloquial.' }, duracao: 900 },
  { materia: 'Português', topico: 'Figuras de linguagem', titulo: 'Figuras de Linguagem — Resumo de Literatura', dificuldade: 'medio', mais_cobrado: false,
    video: { titulo: 'FIGURAS DE LINGUAGEM | Resumo de Literatura para o Enem', video_link: 'https://www.youtube.com/watch?v=wp0yyCn4WHI', descricao: 'Resumo de figuras de linguagem sob a ótica da literatura.' }, duracao: 700 },
  { materia: 'Português', topico: 'Funções da linguagem', titulo: 'Metalinguagem — Resumo de Literatura', dificuldade: 'medio', mais_cobrado: false,
    video: { titulo: 'METALINGUAGEM | Resumo de Literatura para o Enem', video_link: 'https://www.youtube.com/watch?v=joWy9JUlslY', descricao: 'Explicação do conceito de metalinguagem na literatura.' }, duracao: 700 },
  { materia: 'Português', topico: 'Interpretação de texto', titulo: '[Aulão/Revisão geral] 10 Temas de Português que Mais Caem', dificuldade: 'medio', mais_cobrado: true,
    video: { titulo: 'AULÃO ENEM DE PORTUGUÊS: 10 temas que mais caem | Aulão Enem 2024 | Fernanda e Mercedes', video_link: 'https://www.youtube.com/watch?v=SwjUGs1JPHk', descricao: 'Aulão de revisão geral com os 10 temas de Português que mais caem no ENEM.' }, duracao: 5400 },

  // Biologia
  { materia: 'Biologia', topico: 'Ecologia — conceitos e cadeias alimentares', titulo: 'O que é Ecologia', dificuldade: 'basico', mais_cobrado: true,
    video: { titulo: 'O QUE É ECOLOGIA | Resumo de Biologia para o Enem & Encceja. Profe Juliana Evelyn Santos', video_link: 'https://www.youtube.com/watch?v=KKHBE-b9Lbw', descricao: 'Conceito introdutório de ecologia.' }, duracao: 700 },
  { materia: 'Biologia', topico: 'Genética', titulo: 'Primeira Lei de Mendel', dificuldade: 'medio', mais_cobrado: true,
    video: { titulo: 'PRIMEIRA LEI DE MENDEL | GENÉTICA. Resumo de Biologia Enem. Profe. Juliana Evelyn Santos', video_link: 'https://www.youtube.com/watch?v=o9XcjlufW2k', descricao: 'Explicação da Primeira Lei de Mendel.' }, duracao: 900 },
  { materia: 'Biologia', topico: 'Genética', titulo: 'Alelos: Genes Dominantes e Recessivos', dificuldade: 'medio', mais_cobrado: false,
    video: { titulo: 'ALELOS: genes dominantes e recessivos | Curso de Genética Básica | Biologia Enem | Cláudia Aguiar', video_link: 'https://www.youtube.com/watch?v=zJhsN9oRq60', descricao: 'Conceito de alelos dominantes e recessivos.' }, duracao: 900 },
  { materia: 'Biologia', topico: 'Citologia', titulo: 'DNA e RNA', dificuldade: 'medio', mais_cobrado: true,
    video: { titulo: 'DNA E RNA | Resumo de Biologia para o Enem', video_link: 'https://www.youtube.com/watch?v=QNZlZomZ40w', descricao: 'Estrutura e função do DNA e RNA.' }, duracao: 700 },
  { materia: 'Biologia', topico: 'Citologia', titulo: 'Citologia: Células Eucariontes e Procariontes', dificuldade: 'basico', mais_cobrado: true,
    video: { titulo: 'CITOLOGIA: células eucariontes e procariontes | Resumo de Biologia para o Enem', video_link: 'https://www.youtube.com/watch?v=5meS2gddSLA', descricao: 'Diferenças entre células eucariontes e procariontes.' }, duracao: 700 },
  { materia: 'Biologia', topico: 'Evolução', titulo: 'Evidências da Evolução', dificuldade: 'medio', mais_cobrado: false,
    video: { titulo: 'EVIDÊNCIAS DA EVOLUÇÃO | Biologia para o Enem | Cláudia de Souza Aguiar', video_link: 'https://www.youtube.com/watch?v=7KHEmraKSRc', descricao: 'Principais evidências da evolução biológica.' }, duracao: 900 },
  { materia: 'Biologia', topico: 'Ecologia — conceitos e cadeias alimentares', titulo: '[Aulão/Revisão geral] 10 Temas de Biologia que Mais Caem (2025)', dificuldade: 'medio', mais_cobrado: true,
    video: { titulo: 'AULÃO ENEM DE BIOLOGIA: OS TEMAS QUE MAIS CAEM | AULÃO ENEM 2025', video_link: 'https://www.youtube.com/watch?v=7LG4D_USSrU', descricao: 'Aulão de revisão geral com os temas de Biologia que mais caem no ENEM (edição mais recente escolhida entre 3 versões equivalentes).' }, duracao: 5400 },

  // Química
  { materia: 'Química', topico: 'Estequiometria', titulo: '[Exercícios resolvidos] Estequiometria', dificuldade: 'medio', mais_cobrado: true,
    video: { titulo: 'ESTEQUIOMETRIA: RESOLUÇÃO DE EXERCÍCIOS | Resumo de Química para o Enem', video_link: 'https://www.youtube.com/watch?v=HRiAwJJ_nfU', descricao: 'Exercícios resolvidos de estequiometria.' }, duracao: 1080 },
  { materia: 'Química', topico: 'Termoquímica', titulo: 'Lei de Hess (Termoquímica)', dificuldade: 'medio', mais_cobrado: true,
    video: { titulo: 'LEI DE HESS (TERMOQUÍMICA) | Resumo de Química para o Enem', video_link: 'https://www.youtube.com/watch?v=mOO3Q4Bnytc', descricao: 'Explicação da Lei de Hess em termoquímica.' }, duracao: 900 },
  { materia: 'Química', topico: 'Termoquímica', titulo: 'Reação de Combustão', dificuldade: 'medio', mais_cobrado: false,
    video: { titulo: 'REAÇÃO DE COMBUSTÃO | Resumo de Química para o Enem', video_link: 'https://www.youtube.com/watch?v=CuzrJ2lYxeY', descricao: 'Explicação das reações de combustão.' }, duracao: 700 },
  { materia: 'Química', topico: 'Ligações químicas', titulo: 'Ligações Metálicas', dificuldade: 'basico', mais_cobrado: false,
    video: { titulo: 'LIGAÇÕES METÁLICAS | Resumo de Química para o Enem e ENCCEJA. Professora Larissa Campos', video_link: 'https://www.youtube.com/watch?v=tdMDGtSVLjs', descricao: 'Explicação sobre ligações metálicas.' }, duracao: 700 },
  { materia: 'Química', topico: 'Ligações químicas', titulo: 'Ligações Covalentes', dificuldade: 'basico', mais_cobrado: true,
    video: { titulo: 'LIGAÇÕES COVALENTES | Resumo de Química para o Enem e ENCCEJA. Profe Larissa Campos', video_link: 'https://www.youtube.com/watch?v=FRNQUMVBwss', descricao: 'Explicação sobre ligações covalentes.' }, duracao: 700 },
  { materia: 'Química', topico: 'Ligações químicas', titulo: 'Propriedades Químicas e Físicas da Matéria', dificuldade: 'basico', mais_cobrado: false,
    video: { titulo: 'PROPRIEDADES QUÍMICAS E FÍSICAS DA MATÉRIA | Resumo de Química para o Enem', video_link: 'https://www.youtube.com/watch?v=9rfIcvbdMO0', descricao: 'Diferença entre propriedades químicas e físicas da matéria.' }, duracao: 700 },
  { materia: 'Química', topico: 'Química orgânica — funções orgânicas', titulo: 'Alotropia: Oxigênio e Formas do Carbono', dificuldade: 'medio', mais_cobrado: false,
    video: { titulo: 'ALOTROPIA: oxigênio e formas do carbono | Química Enem | Larissa Campos', video_link: 'https://www.youtube.com/watch?v=Iy5qAD8WYBM', descricao: 'Explicação do fenômeno de alotropia.' }, duracao: 700 },

  // Matemática
  { materia: 'Matemática', topico: 'Razão, proporção e regra de três', titulo: '[Questões resolvidas] Regra de Três Simples', dificuldade: 'medio', mais_cobrado: false,
    video: { titulo: '💎 Caiu no ENEM - Regra de Três Simples - Duas questões resolvidas - Professora Angela Matemática', video_link: 'https://www.youtube.com/watch?v=sNEzlDe4WxA', descricao: 'Duas questões de regra de três simples já cobradas no ENEM, resolvidas.' }, duracao: 900 },
];

async function main() {
  console.log('Fazendo login...');
  const token = await login();
  const api = cliente(token);
  console.log('Login OK (admin confirmado).\n');

  const mapaTopicos = {};
  for (const [materia, id] of Object.entries(MATERIAS)) {
    const dados = await api.get(`/admin/materias/${id}/topicos`);
    mapaTopicos[materia] = {};
    for (const t of dados.topicos) mapaTopicos[materia][t.nome.trim().toLowerCase()] = t.topico_id;
  }

  // --- Renomear (título prefixado) ---
  console.log('--- Corrigindo títulos (live/exercício) ---');
  for (const item of RENOMEAR) {
    const materiaId = MATERIAS[item.materia];
    const lista = await api.get(`/admin/aulas/por-materia/${materiaId}`);
    const aula = lista.aulas.find((a) => a.titulo === item.tituloAtual);
    if (!aula) {
      console.log(`NÃO ENCONTRADA: [${item.materia}] "${item.tituloAtual}"`);
      continue;
    }
    try {
      await api.patch(`/admin/aulas/${aula.id}`, {
        titulo: item.novoTitulo,
        conteudos: [{ tipo: 'video', ordem: 0, duracao: item.duracao, ativo: true, video: item.video }],
      });
      console.log(`RENOMEADA: [${item.materia}] "${item.tituloAtual}" -> "${item.novoTitulo}"`);
    } catch (erro) {
      console.log(`FALHOU RENOMEAR: [${item.materia}] "${item.tituloAtual}" -> ${erro.message}`);
    }
  }

  // --- Novas aulas ---
  console.log('\n--- Cadastrando aulas novas ---');
  let ok = 0;
  const falhas = [];
  for (const aula of NOVAS_AULAS) {
    const materiaId = MATERIAS[aula.materia];
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
      conteudos: [{ tipo: 'video', ordem: 0, duracao: aula.duracao, ativo: true, video: aula.video }],
    };
    try {
      await api.post('/admin/aulas', payload);
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

main().catch((e) => { console.error('ERRO FATAL:', e.message); process.exitCode = 1; });
