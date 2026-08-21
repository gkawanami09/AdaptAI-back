'use strict';

/**
 * Questões reais para popular /admin/questoes.
 *
 * Cada item usa nomes (materia/topico/tipoProva) em vez de UUID — o script
 * popular-questoes.js resolve os IDs em tempo de execução consultando a API,
 * então basta acrescentar itens aqui a cada novo lote verificado.
 *
 * Campos "fonte" e "verificado" são só para o relatório (nunca vão pro POST):
 *   verificado:true  -> gabarito conferido cruzando 2+ fontes independentes.
 *   verificado:false -> questão-modelo autoral (não é item oficial de prova).
 */

const QUESTOES = [
  {
    materia: 'Matemática',
    topico: 'Razão, proporção e regra de três',
    tipoProva: 'ENEM',
    ano: 2012,
    dificuldade: 'facil',
    enunciado:
      'Uma mãe recorreu à bula para verificar a dosagem de um remédio que precisava dar a seu filho. Na bula, recomendava-se a seguinte dosagem: 5 gotas para cada 2 kg de massa corporal a cada 8 horas. Se a mãe ministrou corretamente 30 gotas do remédio a seu filho a cada 8 horas, então a massa corporal dele é de:',
    dica: 'Monte a proporção entre gotas e massa corporal. As grandezas são diretamente proporcionais: mais massa corporal exige mais gotas.',
    explicacao:
      'Regra de três simples: 5 gotas está para 2 kg, assim como 30 gotas está para x kg. Como são grandezas diretamente proporcionais: 5/2 = 30/x → 5x = 60 → x = 12 kg.',
    alternativas: [
      { letra: 'A', texto: '12 kg', correta: true },
      { letra: 'B', texto: '15 kg', correta: false },
      { letra: 'C', texto: '20 kg', correta: false },
      { letra: 'D', texto: '24 kg', correta: false },
      { letra: 'E', texto: '75 kg', correta: false },
    ],
    fonte: 'ENEM 2012 (2º dia) — gabarito conferido em descomplica.com.br/gabarito-enem e plataformaassaad.com.br',
    verificado: true,
  },
  {
    materia: 'Biologia',
    topico: 'Ecologia — conceitos e cadeias alimentares',
    tipoProva: 'ENEM',
    ano: 2020,
    dificuldade: 'medio',
    enunciado:
      'Em um ecossistema é observada a seguinte teia alimentar: algas são consumidas por moluscos e por pequenos peixes; os moluscos são consumidos por aves e por pequenos peixes; os pequenos peixes são consumidos por aves. O menor nível trófico ocupado pelas aves é aquele do qual elas participam como consumidores de:',
    dica: 'Procure o caminho mais curto da base da cadeia (produtor) até as aves, contando cada nível trófico.',
    explicacao:
      'O caminho mais curto é: Algas (produtor) → Moluscos (consumidor primário) → Aves. Nesse caminho, as aves ocupam a posição de consumidor secundário (segunda ordem), pois se alimentam diretamente de um consumidor primário.',
    alternativas: [
      { letra: 'A', texto: 'primeira ordem', correta: false },
      { letra: 'B', texto: 'segunda ordem', correta: true },
      { letra: 'C', texto: 'terceira ordem', correta: false },
      { letra: 'D', texto: 'quarta ordem', correta: false },
      { letra: 'E', texto: 'quinta ordem', correta: false },
    ],
    fonte: 'ENEM 2020 Digital (2º dia, questão 102 caderno azul) — gabarito conferido em todamateria.com.br e plataformaassaad.com.br',
    verificado: true,
  },
  {
    materia: 'Português',
    topico: 'Interpretação de texto',
    tipoProva: 'ENEM',
    ano: 2012,
    dificuldade: 'medio',
    enunciado:
      '"Ele era o inimigo do rei", nas palavras de seu biógrafo, Lira Neto. Ou, ainda, "um romancista que colecionava desafetos, azucrinava D. Pedro II e acabou inventando o Brasil". Assim era José de Alencar (1829-1877), o conhecido autor de O Guarani e Iracema, tido como o pai do romance no Brasil. Além de criar clássicos da literatura brasileira com temas nativistas, indianistas e históricos, ele foi também folhetinista, diretor de jornal, autor de peças de teatro, advogado, deputado federal e até ministro da Justiça. Para ajudar na descoberta das múltiplas facetas desse personagem do século XIX, parte de seu acervo inédito será digitalizada. (História Viva, n. 99, 2011, adaptado). Com base no texto, que trata do papel do escritor José de Alencar e da futura digitalização de sua obra, depreende-se que:',
    dica: 'A resposta certa exige uma inferência: conecte a importância histórica de Alencar ("inventou o Brasil") ao significado de preservar sua obra.',
    explicacao:
      'O texto apresenta Alencar como figura central na formação da identidade brasileira. A digitalização de sua obra, portanto, não serve apenas para facilitar a leitura (alternativa A) ou por seu valor histórico isolado (C), mas para preservar a língua da época e a identidade nacional que sua obra ajudou a construir — por isso a alternativa D é a única que capta essa relação de causa e efeito.',
    alternativas: [
      { letra: 'A', texto: 'a digitalização dos textos é importante para que os leitores possam compreender seus romances.', correta: false },
      { letra: 'B', texto: 'o conhecido autor de O Guarani e Iracema foi importante porque deixou uma vasta obra literária com temática atemporal.', correta: false },
      { letra: 'C', texto: 'a divulgação das obras de José de Alencar, por meio da digitalização, demonstra sua importância para a história do Brasil Imperial.', correta: false },
      { letra: 'D', texto: 'a digitalização dos textos de José de Alencar terá importante papel na preservação da memória linguística e da identidade nacional.', correta: true },
      { letra: 'E', texto: 'o grande romancista José de Alencar é importante porque se destacou por sua temática indianista.', correta: false },
    ],
    fonte: 'ENEM 2012 (2º dia) — gabarito oficial INEP conferido em qconcursos.com, descomplica.com.br/gabarito-enem e resumov.com.br',
    verificado: true,
  },
  {
    materia: 'Química',
    topico: 'Estequiometria',
    tipoProva: 'ENEM',
    ano: 2025,
    dificuldade: 'medio',
    enunciado:
      'O Brasil é o maior produtor mundial de nióbio (massa molar = 93 g/mol), metal utilizado na fabricação de vários tipos de aço: automotivos, estruturais e inoxidáveis. O processo utilizado na produção do nióbio é a redução aluminotérmica de Nb2O5 com excesso de 10% de Al (massa molar = 27 g/mol), em relação à quantidade estequiométrica da reação, representada pela equação química: 3 Nb2O5(s) + 10 Al(s) → 6 Nb(s) + 5 Al2O3(s). Uma engenheira metalúrgica estimou a massa de alumínio necessária para produzir 9,3 kg de nióbio, nas condições descritas, para a produção de um lote de peças de aço encomendado por uma indústria, considerando um rendimento de 100%. (Disponível em: www.cbmm.com.br. Acesso em: 17 out. 2015, adaptado). A massa de alumínio, em quilograma, estimada pela engenheira é mais próxima de:',
    dica: 'Primeiro calcule a massa estequiométrica de Al usando a proporção molar da equação balanceada (10 mol Al : 6 mol Nb). Depois, some o excesso de 10% pedido no enunciado.',
    explicacao:
      'Pela proporção da equação (10 mol Al para 6 mol Nb), a massa estequiométrica de alumínio necessária para 9,3 kg de nióbio é 4,5 kg. Como o processo usa um excesso de 10% de Al, a massa total é 4,5 kg × 1,10 = 4,95 kg, valor mais próximo de 5,0 kg.',
    alternativas: [
      { letra: 'A', texto: '2,7 kg', correta: false },
      { letra: 'B', texto: '3,0 kg', correta: false },
      { letra: 'C', texto: '4,1 kg', correta: false },
      { letra: 'D', texto: '4,5 kg', correta: false },
      { letra: 'E', texto: '5,0 kg', correta: true },
    ],
    fonte: 'ENEM 2025 (2º dia) — gabarito conferido em descomplica.com.br, plataformaassaad.com.br, poliedroresolve.sistemapoliedro.com.br e aprovatotal.com.br',
    verificado: true,
  },
];

module.exports = { QUESTOES };
