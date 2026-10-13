# PixPay — O que descobrimos sobre o churn

Análise de 12/10/2026 sobre `data/clientes_pixpay_limpo.csv` (10.000 clientes).
Todos os números abaixo vêm do código em `scripts/` e podem ser reproduzidos (veja a seção 10).

---

## Resumo em 1 minuto

1. **O churn de abril/2026 é de 13,53%, e não de 8%.** Foram 1.353 cancelamentos em 10.000 clientes.
2. **Dois sinais concentram o problema:**
   - **chamado de suporte respondido em mais de 24 h** → 50,39% de churn (contra 10,08% quando respondido em até 24 h);
   - **0 ou 1 notificação** → 25,32% de churn (contra 8,36% com 2 ou mais).
3. **Com os dois sinais juntos, o churn chega a 86,81%.** São 235 clientes (2,4% da base) e 204 cancelamentos.
4. **O plano pesa pouco em quantidade de clientes** (Premium 15,23% contra Básico 12,39%), mas **pesa muito em dinheiro**: o Premium é 67,3% da mensalidade perdida.
5. **Transações e tempo de casa não explicam o churn.**
6. **Tudo aqui é associação, não prova de causa.** Faltam respostas da PixPay (seção 8).

---

## Recomendações

Todas dependem de confirmar que os sinais são causa e não consequência do cancelamento (seções 8 e 9).

1. **Atender chamados em até 24 h.** Acima disso o churn vai de **10,08%** para **47% a 56%**. Antes de investir, confirmar se o chamado lento veio antes da decisão de cancelar (seção 8, item 3).
2. **Garantir pelo menos 2 notificações.** **3.049 clientes (30,5% da base)** estão abaixo disso, com churn de **25,32%** contra **8,36%**. Antes, descobrir o que `notificacoes_7d` mede e se a regra de 2 é de sistema (seção 8, itens 2 e 4).
3. **Ação de resgate para os 89 clientes Premium com os dois sinais.** O churn deles é de **89,89%** e só **9 ainda estão ativos**. A mensalidade já perdida é de R$ 3.992,00, então o valor está em transformar o caso em alerta para novos clientes.
4. **Monitorar o grupo com os dois sinais (235 clientes).** Churn de **86,81%** e **204 cancelamentos (15,1% do total)**. É o alerta de maior precisão que os dados permitem.
5. **Priorizar o Premium pelo valor, não pelo risco.** O plano pesa pouco no churn (15,23% contra 12,39%), mas o Premium responde por **67,3% da mensalidade perdida** (R$ 30.439,00 de R$ 45.224,70).
6. **Pedir à PixPay os dados que faltam:** meses anteriores a abril, para validar a subida de 3% para 8%, e a definição usada no cálculo dos 8% (o dataset mostra 13,53%).

---

## 1. Qualidade dos dados

O arquivo original tinha 10.016 linhas e 15 colunas. Depois da limpeza ficaram **10.000 linhas**, que é o número esperado de clientes.

| Problema encontrado | Quantas linhas | O que foi feito |
|---|---|---|
| Clientes duplicados (mesmo `cliente_id`) | 16 | Mantida 1 linha por cliente. Só 1 par era idêntico; os outros 15 diferiam em formato, caixa ou espaço |
| Nome com espaço sobrando ou caixa errada | 500 | Padronizado (Title Case) |
| Plano com 14 grafias (ex.: `premim`, `basic`) | 500 | Reduzido a 2: `Básico` e `Premium` |
| Estado escrito por extenso | 27 | Trocado pela sigla |
| Mesma cidade escrita de formas diferentes | 28 | Unificada (72 grafias viraram 60 cidades) |
| `abriu_chamado` como `sim`/`não` | 1.001 | Padronizado em `True`/`False` |
| Datas em 3 formatos | 6.996 + 804 | Padronizadas em `AAAA-MM-DD` |
| CPF sem máscara | 3.004 | Padronizado em `000.000.000-00` |
| Mensalidade em 3 formatos (`R$ 19,90`, `19,90`, `19.90`) | 6.924 | Convertida em número |

O arquivo bruto em `data/clientes_pixpay.csv` **não foi alterado**.

### Coisas estranhas que não foram corrigidas

| Achado | Detalhe |
|---|---|
| **CPFs quase todos inválidos** | 9.930 de 10.016 (99,14%) falham no dígito verificador. Isso é o esperado para números aleatórios (cerca de 0,97% passam por acaso). Provavelmente é um dataset **sintético ou anonimizado**. Os CPFs foram mantidos |
| **`ticket_medio_30d` com duas populações** | Os valores normais vão até R$ 417,99 (mediana R$ 75,33). Há **677 valores entre R$ 99.077,75 e R$ 999.842,62** e nenhum entre os dois grupos. Parece erro de escala ou de registro. **Não foram alterados** |
| **`transacoes_30d` ausente em 1.215 clientes** | Todos eles têm ticket médio igual a 0. Entre os que têm valor, ticket 0 só acontece quando transações é 0. Provavelmente **ausente significa "zero transações"**, mas falta a confirmação da PixPay. **Não foram preenchidos** |
| `data_cancelamento` e `tempo_resposta_chamado_h` vazios | Vazio é esperado: só cancelou quem tem data, e só abriu chamado quem tem tempo de resposta. Bate 100% |

---

## 2. O churn real contra os 8% do briefing

| Medida | Resultado |
|---|---|
| Churn de abril/2026 | **13,53%** (1.353 de 10.000) |
| Intervalo de confiança 95% | 12,87% a 14,21% |
| Diferença para os 8% | **+5,53 pontos percentuais** |
| Cancelamentos necessários para dar 8% | 800 (há 1.353) |
| Base necessária para dar 8% com 1.353 cancelamentos | 16.912 clientes |
| Data em que o acumulado do mês passa de 8% | 18/04/2026 |

- Os 8% ficam **fora** do intervalo de confiança, e o resultado é o mesmo com qualquer denominador testado.
- **O dataset só tem cancelamentos de abril** (01/04/2026 a 30/04/2026). Por isso **a subida de 3% para 8% em 6 meses não pode ser verificada**.
- O ritmo é constante: cerca de 45 cancelamentos por dia, sem pico.

---

## 3. O que explica o churn (do mais forte ao mais fraco)

Força da associação medida pelo Cramér's V (0 = nenhuma, 1 = total):

| # | Variável | Força | Resultado |
|---|---|---|---|
| 1 | **Tempo de resposta do chamado** | **forte (0,45)** | Degrau em 24 h |
| 2 | **Notificações** | **média (0,23)** | Degrau em 2 notificações |
| 3 | Abrir chamado | média (0,15) | Só reflete os chamados lentos |
| 4 | Cidade | pequena (0,08) | Poucas cidades se destacam |
| 5 | Estado | pequena (0,06) | CE se destaca |
| 6 | Plano | desprezível (0,04) | Premium um pouco pior |
| 7 | Transações em 30 dias | nenhuma | Sem efeito |
| 8 | Tempo de casa | nenhuma | Sem efeito |

### 3.1 Tempo de resposta do chamado (só quem abriu chamado: 2.524 clientes)

| Espera | Clientes | Churn |
|---|---|---|
| Até 24 h | 1.746 | **10,08%** |
| 24 a 48 h | 289 | **47,06%** |
| 48 a 72 h | 256 | **56,25%** |
| Mais de 72 h | 233 | **48,07%** |

- Acima de 24 h o churn é **5 vezes** o de quem foi atendido em até 24 h (risco relativo 5,00).
- O efeito é um **degrau em 24 h**, e não uma piora gradual.
- **Abrir chamado, em si, não aumenta o churn.** Quem teve o chamado resolvido em até 24 h tem 10,08%, igual aos 10,50% de quem nem abriu.

### 3.2 Notificações

| Notificações | Clientes | Churn |
|---|---|---|
| 0 ou 1 | 3.049 | **25,32%** |
| 2 ou mais | 6.951 | **8,36%** |

- Risco relativo de **3,03**.
- 0 e 1 notificação são equivalentes (25,82% e 24,82%). Entre 2 e 12 **não há gradiente**: é um degrau em 2.
- **Quem recebe poucas notificações não se comporta de forma diferente em nada que o dataset mede**: transações (30,72 contra 30,80), ticket, chamados, plano, tempo de casa e geografia são iguais nos dois grupos. A única diferença é o churn.
- Por isso, **não é correto chamar isso de "baixo engajamento"**. Quem recebe poucas notificações usa o app tanto quanto os outros.

### 3.3 Geografia

- Só **CE (19,02%)** e a cidade de **Floriano (23,17%)** continuam acima da média depois da correção para múltiplos testes.
- Os menores valores aparecem em capitais (Maceió 7,56%, João Pessoa 8,52%). Entre os maiores há cidades do interior. É uma hipótese, não uma conclusão.

---

## 4. Os dois sinais juntos

| Segmento | Clientes | Cancelaram | Churn |
|---|---|---|---|
| Nenhum sinal | 6.408 (64,1%) | 393 | **6,13%** |
| Só 0–1 notificação | 2.814 (28,1%) | 568 | **20,18%** |
| Só chamado acima de 24 h | 543 (5,4%) | 188 | **34,62%** |
| **Os dois sinais** | **235 (2,4%)** | **204** | **86,81%** |

- Se os efeitos apenas se somassem, o esperado seria 48,67%. O observado é **86,81%**: os sinais **se reforçam** (+38,13 p.p., IC 95%: 31,97 a 44,28).
- Os dois sinais são **independentes**: o efeito de cada um continua igual quando se controla pelo outro.
- Clientes com **algum** sinal: 3.592 (35,9% da base), com **960 cancelamentos (71,0% do total)**.
- Se esses clientes tivessem o churn de quem não tem sinal (6,13%), haveria cerca de **740 cancelamentos a menos** (54,7% do total). Isso é uma associação: só seria evitável se os sinais forem a causa.

---

## 5. Plano Básico contra Premium

| Plano | Clientes | Cancelaram | Churn | Mensalidade | Mensalidade perdida |
|---|---|---|---|---|---|
| Básico | 5.996 | 743 | **12,39%** | R$ 19,90 | **R$ 14.785,70** |
| Premium | 4.004 | 610 | **15,23%** | R$ 49,90 | **R$ 30.439,00** |
| **Total** | 10.000 | 1.353 | 13,53% | | **R$ 45.224,70** |

- Diferença de **2,84 p.p.** (risco relativo 1,23). É real, mas pequena. Continua igual (1,22) depois de controlar pelos dois sinais de risco.
- A mensalidade total da base é **R$ 319.120,00**. A perda de abril equivale a **14,17%** dela.
- O Premium tem 40,0% dos clientes e 45,1% dos cancelamentos, mas **67,3% da mensalidade perdida**.
- O Premium transaciona o dobro do Básico (média de 44,47 contra 21,68 transações). Essa receita **não está** na conta, então a perda real do Premium provavelmente é maior.

### Perfil específico pedido: Premium + menos de 2 notificações + chamado acima de 24 h

| Medida | Resultado |
|---|---|
| Clientes | **89** (0,89% da base) |
| Cancelaram | **80** |
| Churn | **89,89%** (IC 95%: 81,89% a 94,59%) |
| Mensalidade perdida | R$ 3.992,00 |
| Ainda ativos | 9 |

No Básico, o mesmo perfil tem 84,93% (146 clientes). A diferença não é estatisticamente significativa.

---

## 6. O que NÃO influencia o churn

| Variável | Churn mínimo a máximo entre grupos | Conclusão |
|---|---|---|
| Transações em 30 dias | 12,24% a 14,88% | Sem efeito (p = 0,194) |
| Tempo de casa (dias desde o cadastro) | 12,86% a 14,05% | Sem efeito (p = 0,530) |

---

## 7. Como os sinais se relacionam com outras características

- **Chamado lento** e **poucas notificações** são independentes entre si.
- **Plano** e **geografia** têm efeito próprio pequeno, que persiste depois de controlar pelos dois sinais.
- Os grupos com poucas notificações e com muitas são iguais em plano, tempo de casa, transações, ticket, chamados e geografia.

---

## 8. Perguntas que a PixPay precisa responder

Estas respostas podem **mudar as conclusões**:

1. **Como o 8% foi calculado?** Outra janela, outro mês, outra definição de churn? O dataset mostra 13,53%.
2. **O que é `notificacoes_7d`?** São notificações enviadas, recebidas ou abertas? A janela de 7 dias é a dos primeiros 7 dias após o cadastro ou a dos últimos 7 dias antes da extração? Se for a primeira, o sinal vem meses antes do cancelamento. Se for a segunda, pode ser consequência da decisão de sair.
3. **O chamado lento veio antes ou depois da decisão de cancelar?** Se foi depois, melhorar o suporte não evita o cancelamento.
4. **Existe uma regra de sistema em 24 h** (escalonamento, fechamento automático) **e em 2 notificações?** Os degraus são nítidos demais para comportamento humano comum.
5. **Transação ausente significa zero transações?**
6. **De onde vêm os 677 tickets de R$ 99.077,75 a R$ 999.842,62?**
7. **Os dados são reais ou sintéticos?** Os CPFs inválidos sugerem sintéticos.

---

## 9. Cuidados com a leitura

- **Associação não é causa.** Nenhum teste aqui prova que mudar um sinal muda o cancelamento.
- **Só abril.** Não dá para ver tendência nem sazonalidade.
- **Os limiares de 24 h e de 2 notificações foram escolhidos depois de ver os dados.** O efeito real tende a ser um pouco menor que o estimado.
- **Perfis pequenos têm intervalo largo.** O de Premium com os dois sinais tem só 89 clientes.
- **Sem regressão logística.** Ela exigiria uma biblioteca fora da stack do projeto (statsmodels ou scikit-learn).
- **O dataset parece sintético.** Se for, os resultados valem como exercício, não como diagnóstico do negócio real.

---

## 10. Documentos produzidos

### Para ler

| Arquivo | O que é |
|---|---|
| `DESCOBERTAS_ANALISE_CHURN.md` | Este documento |
| `auditoria_pixpay.md` | Auditoria do dataset **bruto**: duplicatas lado a lado, grafias sujas, formatos misturados. Abre no VS Code |
| `reports/graficosexecutados/passo1_churn_acumulado_abril.png` | Churn acumulado em abril contra a linha de 8% |
| `reports/graficosexecutados/passo2_churn_por_variavel.png` | Churn por grupo em cada variável |
| `reports/graficosexecutados/passo2_churn_geografia.png` | Churn por estado e cidade |
| `reports/graficosexecutados/passo3_ranking_drivers.png` | Ranking dos drivers e dos grupos de maior efeito |
| `reports/graficosexecutados/passo4_combinacao_drivers.png` | Combinação chamado lento × notificações |

### Dados

| Arquivo | O que é |
|---|---|
| `data/clientes_pixpay.csv` | Dataset **bruto** (10.016 linhas), intocado |
| `data/clientes_pixpay_limpo.csv` | Dataset **limpo** (10.000 linhas), base de toda a análise |
| `auditoria_pixpay.xlsx` | Lista completa das 10.016 linhas brutas com uma coluna por tipo de sujeira. Precisa do Excel |

### Notebooks

| Arquivo | O que é |
|---|---|
| `notebooks/auditoria_dados.ipynb` | Auditoria de qualidade (ausentes, duplicatas, formatos, CPF) |
| `notebooks/analise_drivers.ipynb` | Passos 1 a 4, notificações, com código e saídas |
| `notebooks/analise_drivers.pdf` | PDF do notebook de análise. Está na pasta, mas **não foi gerado por mim nesta sessão** |

### Código (`scripts/`)

| Arquivo | O que faz |
|---|---|
| `limpar_dados.py` | Limpeza, com cada decisão comentada |
| `investigar_transacoes.py` | Investigação dos ausentes de `transacoes_30d` |
| `analisar_drivers.py` | Passos 1 a 4 da análise de drivers |
| `analisar_notificacoes.py` | Aprofundamento em notificações |
| `analisar_plano.py` | Aprofundamento em plano e impacto em mensalidade |
| `gerar_excel_auditoria.py` | Gera `auditoria_pixpay.xlsx` e `auditoria_pixpay.md` |

### Para reproduzir

Na raiz do projeto, em qualquer ordem depois da limpeza:

```
python scripts/limpar_dados.py
python scripts/investigar_transacoes.py
python scripts/analisar_drivers.py
python scripts/analisar_notificacoes.py
python scripts/analisar_plano.py
python scripts/gerar_excel_auditoria.py
```

---

## 11. Próximo passo sugerido

Montar o **relatório executivo em PDF para o CEO** com as conclusões das seções 2 a 5 e as perguntas da seção 8 como ressalvas explícitas.
