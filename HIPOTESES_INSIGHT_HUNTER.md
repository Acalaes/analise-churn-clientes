# Hipóteses exploratórias de churn (insight-hunter)

Relatório do analista exploratório (instruções do `insight-hunter`), executado em modo somente leitura sobre
`data/clientes_pixpay_limpo.csv` (n = **10.000**, churn de abril/2026 = **13,53%**).

> Notas de origem:
> - O `insight-hunter` ainda não estava carregado nesta sessão, então a análise foi feita por um agente genérico
>   com as mesmas instruções, mais o pedido de rigor estatístico do `CLAUDE.md`.
> - A hipótese H1 (capital vs. interior) foi conferida de novo diretamente no CSV: **893/5.983** (**14,93%**) vs
>   **460/4.017** (**11,45%**). As demais vêm do relatório do agente e não foram refeitas.
> - **Todas as linhas são associação observada, não causalidade.**

## Método
- Cerca de **170 recortes/testes** (**121** da varredura categórica e ~**50** de cruzamentos).
- Diferença de taxas com z de duas proporções, IC 95% de Wilson e permutação (2.000 embaralhamentos) para heterogeneidade.
- Limiar de Bonferroni: α = 0,05/170 ≈ **2,9×10⁻⁴**.
- Já estabelecido nas análises anteriores e, por isso, não tratado como hipótese nova: chamado lento (>24h), poucas notificações (0–1),
  plano, transações, tempo de casa e a geografia fraca (CE e Floriano).

## Tabela principal

| Título | Hipótese | Evidência | Categoria | Acionabilidade |
|---|---|---|---|---|
| H1. Fora de capital churna mais | Clientes de cidades não capitais cancelam mais, independente de SLA e notificações. | Não capital **14,93%** (893/5.983; IC 14,05–15,85%) vs capital **11,45%** (460/4.017; IC 10,50–12,47%), p = **6,4×10⁻⁷**. Ajustado por estrato de chamado e notificação: **−3,39 p.p.** para capital (bootstrap IC 95%: −4,80 a −2,20). Composição de risco idêntica (7,9% vs 7,6% com chamado >24h), então não é efeito de mix de SLA. Consistente em todos os estratos: baixo risco **6,7% vs 5,4%**; notificações 0–1 **22,9% vs 16,1%**; chamado >24h **53,1% vs 46,2%**. | Geografia | Média. Priorizar resposta de chamados e ativação de notificações fora das capitais. Mecanismo desconhecido. |
| H2. Premium churna mais mesmo sem problema de serviço (contraintuitiva) | O plano de R$ 49,90 tem churn maior que o de R$ 19,90 de forma aditiva, não mediada por SLA ou notificações. | Premium é maior em todos os estratos. Baixo risco **6,78% vs 5,71%** (p = 0,08). Notificações 0–1 **23,0% vs 18,3%** (p = 0,002). Chamado >24h **53,8% vs 47,9%** (p = 0,10). Ajustado: **+2,69 p.p.** (IC 95%: +1,38 a +4,05). Exposição ao serviço ruim é igual nos dois planos: chamado >24h **8,17% vs 7,52%**; notificações 0–1 **30,7% vs 30,4%**. Premium também usa mais (**44,5 vs 21,7** transações), e uso não protege. | Plano / valor | Alta. Investigar percepção de valor do Premium (preço vs benefícios) com pesquisa de cancelamento por plano. |
| H3. Abrir chamado não é o risco, a demora é (contraintuitiva) | Quem abre chamado e é respondido em até 24h churna igual a quem nunca abriu. | Chamado ≤24h **10,08%** (n = 1.746) vs sem chamado **10,50%** (n = 7.476), p = **0,60**. Por faixa de resposta: ≤6h 8,8%; 6–12h 8,0%; 12–24h 11,6%; 24–36h **45,9%**; 36–48h **48,1%**; 48–72h **56,2%**; >72h **48,1%**. Degrau em 24h e quase nenhum gradiente depois. | Atendimento (refina achado já estabelecido) | Alta. Meta de SLA de 24h; não tratar "ter aberto chamado" como sinal de risco. |
| H4. Clientes sem transações não são mais arriscados (contraintuitiva) | Os 1.215 sem transações em 30d (ticket = R$ 0,00) não têm risco maior por inatividade. | **12,51%** (152/1.215; IC 10,77–14,49%) vs 13,67%, p = 0,27. Perfil igual: 25,2% abriram chamado (vs 25,2%), notificações médias **5,26 vs 5,04**, 41,1% Premium (vs 39,9%). Mesmo entre eles, chamado >24h dá **57,8%** (n = 90) e ≤24h **7,4%** (n = 216). | Engajamento | Média. Não usar "inatividade" como gatilho de retenção; churn segue SLA e notificações. |
| H5. Sem sazonalidade nem efeito de coorte | Churn não depende de quando o cliente entrou nem de quando cancelou. | Cancelamentos em abril/2026 (01/04/2026 a 30/04/2026) uniformes: χ² por dia = 27,5 (gl 29); por dia da semana ajustado pelo número de dias = 3,7 (gl 6). Heterogeneidade por permutação: trimestre de cadastro p = 0,106; mês de cadastro p = 0,113; dia da semana de cadastro p = 0,79. Coorte 1T2026 **15,68%** (n = 1.084; p = 0,028) não sobrevive à correção. | Temporal | Baixa. Descarta campanhas por data ou safra. 1T2026 só merece monitoramento. |
| H6. Ticket normal quase não discrimina; bolha Premium com ticket R$ 78–119 é provável ruído | Nenhuma faixa de ticket tem efeito monotônico. A faixa média do Premium parece pior, mas é achado pós-hoc. | Ticket < R$ 10.000,00, quintis: **12,87%**, 13,57%, 13,63%, **15,40%**, 12,87%, sem padrão monotônico. Premium com ticket R$ 78,23–118,87: **19,1%** (n = 774; p = 0,0008). Decis vizinhos oscilam 14–20%; nos Básicos a mesma faixa dá 12–13%. Os 677 extremos (≥ R$ 10.000,00) têm **11,67%** vs 13,67% (p ≈ 0,14, aproximação). | Transacional | Baixa. Não agir antes de validar com dados novos. |
| H7. Tempo de casa não muda o risco dentro dos segmentos | O efeito de SLA e notificações não se concentra em clientes novos ou antigos. | Tercis de tempo de casa: chamado >24h **50,9% / 51,5% / 48,5%**; sem chamado 10,8 / 9,7 / 11,0%; notificações 0–1 **27,9% / 23,0% / 25,1%** (não monotônico, p ≈ 0,01, não sobrevive à correção); fora desse segmento 8,1 / 8,6 / 8,3%. | Ciclo de vida | Baixa. Problema transversal; sem necessidade de plano de retenção por safra. |

## Robusta ou exploratória

| Hipótese | Classificação | Motivo |
|---|---|---|
| H1 | Robusta como associação | Teste único definido antes (lista de 23 capitais), sobrevive à Bonferroni (p = **6,4×10⁻⁷**), consistente nos estratos, IC ajustado exclui zero. Mecanismo em aberto. Há heterogeneidade real entre as 60 cidades (permutação p = 0,0005), mas "não capital" é grosseiro: Guarulhos, Osasco e Campinas entram nele. |
| H2 | Robusta, efeito pequeno | Básico vs Premium sobrevive à Bonferroni (p = **4,6×10⁻⁵**) e o IC ajustado exclui zero. Os p-valores por estrato isolados não sobrevivem (só a direção é consistente). Pode ser seleção (quem escolhe o Premium) ou preço. |
| H3 | Robusta | Nulo bem estimado, n grande; derivada do achado já estabelecido. |
| H4 | Robusta como resultado nulo | IC estreito. O subgrupo chamado >24h entre os sem transações (n = 90) é exploratório. |
| H5 | Nulo robusto para dia e dia da semana | Mês e trimestre de cadastro foram ~12 recortes; nenhum sobrevive à correção. |
| H6 | Exploratória, provável falso positivo | Limiares vieram de quintis e decis depois de ver os dados; p = 0,0008 não passa em 2,9×10⁻⁴. |
| H7 | Exploratória | Nulo em todos os segmentos, exceto uma oscilação isolada sem tendência. |

Na varredura categórica, só CE (p = 3,1×10⁻⁵) e Floriano (p = 2,7×10⁻⁴, no limite) ficam abaixo de 2,9×10⁻⁴.
Caicó (7,7×10⁻⁴), Quixadá (1,3×10⁻³) e Pirapora (7,7×10⁻⁴) não passam.

## Atenção aos dados
- Restam 3 linhas com cidade digitada errado no arquivo limpo ("Belo Horizote", "Fortleza"); o agente as classificou como capitais.
- O console mostrava caracteres corrompidos em cidade e plano (só exibição; as comparações usaram chaves normalizadas).
- Não foram validados CPF nem e-mail. Uma checagem pós-hoc de nomes repetidos (61 clientes, 8,2% de churn, p ≈ 0,1) foi descartada.

## Código usado (núcleo)

Scripts completos ficaram na pasta temporária da sessão (`h.py`, `h2.py`, `h3.py`, `h4.py`); nenhum arquivo do projeto foi alterado.

```python
d=pd.read_csv(r'...\data\clientes_pixpay_limpo.csv',encoding='utf-8')
for c in ['data_cadastro','data_cancelamento']: d[c]=pd.to_datetime(d[c])
d['y']=d.churn_30d.astype(int)
d['sla']=np.where(d.abriu_chamado&(d.tempo_resposta_chamado_h>24),'chamado>24h',
         np.where(d.abriu_chamado,'chamado<=24h','sem'))
d['notif_baixa']=d.notificacoes_7d<=1
d['prem']=d.plano.str.startswith('Prem')
d['semtrans']=d.transacoes_30d.isna()
d['normal']=d.ticket_medio_30d<10000

def z(a,n1,b,n2):                      # z de duas proporções, p bicaudal
    p=(a+b)/(n1+n2); se=math.sqrt(p*(1-p)*(1/n1+1/n2))
    return math.erfc(abs((a/n1-b/n2)/se)/math.sqrt(2))
def wil(k,n):                          # IC 95% de Wilson
    p=k/n; zc=1.96; den=1+zc*zc/n; c=(p+zc*zc/2/n)/den
    h=zc*math.sqrt(p*(1-p)/n+zc*zc/4/n/n)/den; return c-h,c+h

def adj(col,pos):                      # diferença ajustada (peso Mantel-Haenszel)
    num=den=0
    for k,g in d.groupby(['sla','notif_baixa']):
        x=g[g[col]==pos]; y0=g[g[col]!=pos]
        w=len(x)*len(y0)/len(g); num+=w*(x.y.mean()-y0.y.mean()); den+=w
    return num/den*100                 # IC por bootstrap (300 reamostragens)

def chi(y,codes,k):                    # heterogeneidade; p por permutação de y (2.000x)
    n=np.bincount(codes,minlength=k); s=np.bincount(codes,weights=y,minlength=k)
    p=y.mean(); e=n*p; return (((s-e)**2)/(e*(1-p))).sum()
```

Capital = cidade normalizada (sem acento) pertencente às 23 capitais presentes nos dados, mais os 3 registros com erro de digitação.
