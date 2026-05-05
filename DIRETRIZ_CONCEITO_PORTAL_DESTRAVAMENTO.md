# Diretriz de Conceito — Portal de Destravamento do Programa Conecta

## 1. Objetivo deste documento

Este documento define o conceito oficial do portal do Programa Conecta.

Ele deve ser usado como fonte de orientação para qualquer alteração futura no dashboard, páginas, textos, gráficos, indicadores, cards, tabelas, rankings, filtros, scripts e apresentações relacionadas ao portal.

A partir desta definição, qualquer mudança que descaracterize o conceito de **apoio à gestão e destravamento do projeto** deve ser evitada.

---

## 2. Conceito oficial do portal

O portal não deve ser tratado como painel de cobrança individual, competição entre pessoas ou ranking de desempenho pessoal.

O conceito oficial é:

> **Portal de apoio à gestão do Programa Conecta, com foco em visibilidade, priorização e destravamento das entregas.**

A função do portal é mostrar onde o projeto está avançando, onde está parado, onde existem impedimentos, onde existem ocorrências abertas e onde a gestão precisa atuar para remover travas.

O foco deve sair da pessoa e ir para o problema.

---

## 3. Princípio central

Toda informação exibida no portal deve responder a uma destas perguntas:

- O que está impedindo o projeto de avançar?
- Onde existe maior necessidade de apoio?
- Qual frente precisa de atenção da gestão?
- Quais cenários precisam ser destravados?
- Quais ocorrências estão concentrando risco?
- Existem itens sem responsável claro?
- Há decisões pendentes?
- Onde devemos priorizar ação?

Se uma nova tela, gráfico ou indicador não ajudar a responder essas perguntas, provavelmente não deve entrar no portal.

---

## 4. O que o portal deve ser

O portal deve ser:

- uma visão executiva de acompanhamento;
- uma ferramenta de apoio à decisão;
- um mapa de gargalos e impedimentos;
- um instrumento para priorizar ações;
- um apoio para reuniões de gestão;
- uma forma de dar visibilidade ao trabalho;
- um mecanismo para tirar ruído e trazer clareza;
- um painel para mostrar onde a gestão precisa ajudar.

---

## 5. O que o portal não deve ser

O portal não deve ser:

- ranking de cobrança individual;
- competição entre líderes;
- disputa entre frentes;
- placar de vencedores e perdedores;
- ferramenta para expor pessoas;
- painel para apontar culpados;
- comparação negativa entre áreas;
- mecanismo de pressão pública;
- vitrine de quem está melhor ou pior.

Se uma alteração voltar a usar linguagem de corrida, pódio, campeão, perdedor, lanterna, cobrança, pressão ou comparação pessoal, ela deve ser barrada.

---

## 6. Linguagem recomendada

Usar linguagem de gestão, apoio e destravamento.

### Termos recomendados

- Visão Executiva
- Saúde da Execução
- Mapa de Apoio
- Frentes com Necessidade de Ação
- Fila de Destravamento
- Prioridades de Gestão
- Pontos de Atenção
- Impedimentos Ativos
- Ocorrências Abertas
- Responsável de Tratativa
- Índice de Apoio
- Matriz de Atenção Executiva
- Cenários que Exigem Ação
- Itens Pendentes de Avanço

### Termos que devem ser evitados

- Ranking
- Competição
- Corrida
- Pódio
- Campeão
- Vencedor
- Perdedor
- Lanterna
- Quem está na frente
- Quem está atrás
- Placar
- Pontuação de jogo
- Líder da rodada
- Cheiro de vitória
- Missão cumprida no sentido competitivo

---

## 7. Regra para indicadores

Os indicadores devem priorizar leitura gerencial, não exposição individual.

Sempre que possível, apresentar dados por:

- frente;
- status;
- cenário;
- tipo de impedimento;
- ocorrência;
- responsável de tratativa;
- criticidade;
- necessidade de apoio;
- situação executiva.

Evitar destaque visual que transforme uma pessoa em alvo de cobrança.

Quando for necessário mostrar responsável, usar o contexto de **tratativa**, **apoio** ou **dono da ação**, e não de culpa.

---

## 8. Regra para gráficos

Os gráficos devem converter as informações linha a linha do CSV em visão de gestão.

Gráficos recomendados:

- Saúde da execução por status;
- Frentes com maior necessidade de ação;
- Cenários com maior concentração de ocorrências;
- Distribuição de ocorrências por responsável de tratativa;
- Matriz executiva de atenção;
- Fila de destravamento;
- Itens bloqueados por frente;
- Não iniciados por frente;
- Ocorrências abertas por cenário.

Os gráficos não devem ser usados para reforçar competição pessoal.

---

## 9. Índice de Apoio

O antigo conceito de "pontos" deve ser evitado, pois remete a jogo ou ranking.

O termo oficial deve ser:

> **Índice de Apoio**

A lógica recomendada é ponderada:

```text
Índice de Apoio = (Bloqueados × 5) + (Ocorrências Abertas × 3) + (Não Iniciados × 1)
```

Essa regra evita que o painel seja apenas uma contagem bruta de volume e ajuda a dar mais peso para itens realmente críticos.

### Interpretação

- Bloqueado pesa mais porque já existe impedimento ativo.
- Ocorrência aberta pesa bastante porque representa problema em tratamento.
- Não iniciado pesa menos porque pode ser apenas fila natural de execução.
- Quanto maior o índice, maior a necessidade de atenção e apoio da gestão.

O índice não deve ser interpretado como falha da frente ou das pessoas.

Deve ser interpretado como sinal de necessidade de apoio.

---

## 10. Regra para frentes

A visão por frente deve mostrar onde existe maior necessidade de apoio, e não qual frente está melhor ou pior.

Título recomendado:

> **Frentes com maior necessidade de ação**

Ou:

> **Mapa de apoio por frente**

Evitar:

> Frentes em competição

> Ranking de frentes

> Melhor frente

> Pior frente

---

## 11. Regra para líderes e responsáveis

Quando houver visão por líder, o conceito deve ser de apoio e tratativa.

Título recomendado:

> **Mapa de apoio por líder**

Ou:

> **Distribuição de cenários por responsável de tratativa**

Evitar:

> Ranking de líderes

> Líder da rodada

> Quem está na frente

> Quem está puxando a fila

A leitura correta deve ser:

> Esta visão ajuda a entender volume, concentração de trabalho e necessidade de apoio, não desempenho individual.

---

## 12. Regra para ocorrências

Ocorrências devem ser apresentadas como travamentos reais do projeto.

Priorizar:

- abertas;
- sem responsável;
- por cenário;
- por frente;
- por responsável de tratativa;
- por status;
- por concentração;
- por impacto.

A linguagem deve reforçar que ocorrência aberta é ponto de ação, não falha pessoal.

---

## 13. Regra para Top 20

O Top 20 deve ser tratado como fila de prioridade de ação.

Título recomendado:

> **Fila de Destravamento — Top 20**

Ou:

> **Principais itens para ação gerencial**

Evitar:

> Top 20 dos piores

> Ranking dos atrasados

> Quem mais está travando

A ideia é mostrar onde agir primeiro.

---

## 14. Regra para textos de cabeçalho

O cabeçalho do portal deve reforçar o conceito de apoio à gestão.

Texto-base recomendado:

> Painel de apoio à gestão do Programa Conecta, com foco em visibilidade, priorização e destravamento das entregas.

Texto complementar recomendado:

> A visão consolida cenários, status, ocorrências e frentes para mostrar onde o projeto está avançando e onde precisa de ação conjunta.

Evitar textos com tom de brincadeira competitiva, corrida ou cobrança.

---

## 15. Critério de aprovação para mudanças futuras

Antes de qualquer alteração no portal, validar:

1. A mudança ajuda a destravar o projeto?
2. A mudança evita exposição individual?
3. A mudança apoia decisão da gestão?
4. A mudança mostra problema, risco ou impedimento?
5. A linguagem evita competição e cobrança?
6. A informação será útil em reunião executiva?
7. A mudança preserva a base técnica existente?

Se a resposta for "não" para a maioria dos itens, a alteração deve ser recusada ou redesenhada.

---

## 16. Regra de preservação da base

A base técnica do portal deve ser preservada sempre que possível.

Preservar:

- estrutura de arquivos;
- leitura dos CSVs;
- scripts existentes;
- seletor de visões;
- páginas atuais;
- layout principal;
- compatibilidade com GitHub Pages;
- caminhos da pasta `output/`;
- automação Python já existente.

Alterações devem ser cirúrgicas, evitando reescrever o portal sem necessidade.

---

## 17. Diretriz para o assistente

Sempre que for solicitada uma mudança futura neste projeto, o assistente deve verificar se a alteração está alinhada a este conceito.

Se o pedido contrariar o conceito, o assistente deve alertar e barrar a mudança, propondo uma alternativa alinhada ao Portal de Destravamento.

Exemplo:

> Essa alteração volta a dar aparência de ranking/competição. Recomendo não seguir por esse caminho. Posso adaptar para uma visão de apoio, priorização ou destravamento.

---

## 18. Frase oficial de posicionamento

> O portal não existe para apontar quem está atrasado. Ele existe para mostrar o que precisa ser destravado para o projeto avançar.

---

## 19. Resumo direto

O portal deve mostrar:

- saúde;
- risco;
- impedimento;
- dependência;
- ocorrência;
- prioridade;
- necessidade de apoio;
- ação gerencial.

O portal não deve mostrar:

- disputa;
- culpa;
- exposição;
- pressão;
- comparação negativa;
- pódio;
- placar.

---

## 20. Status desta diretriz

Esta diretriz passa a ser considerada a referência conceitual do projeto.

Qualquer evolução futura do portal deve respeitar este documento.
