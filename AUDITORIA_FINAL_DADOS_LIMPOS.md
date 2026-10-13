# Auditoria final: `data/clientes_pixpay_limpo.csv`

Relatório do auditor de qualidade de dados (instruções do `data-auditor`), executado em modo somente leitura.
Nenhum arquivo do projeto foi alterado. Leitura com `pd.read_csv(..., encoding="utf-8")`.
Os caracteres "�" que aparecem no terminal são só de exibição: **0** valores contêm U+FFFD.

> Nota: o `data-auditor` ainda não estava carregado nesta sessão, então a auditoria foi feita por um agente
> genérico com as mesmas instruções. Os achados das seções 5 (cidades) e 3 (ausentes) foram conferidos de novo
> diretamente no CSV.

## Código usado (resumido)

```python
import pandas as pd
df = pd.read_csv(r"C:\Users\acala\Downloads\projeto-pixpay\data\clientes_pixpay_limpo.csv", encoding="utf-8")
df.shape; df.dtypes; n = df.isna().sum(); (n/len(df)*100).round(2)
for c in df.columns: df[c].nunique(), df[c].duplicated().sum()
# Formato: strip, espaço duplo, caixa, regex de id/CPF/data
s != s.str.strip(); s.str.contains('  '); s == s.str.upper(); s == s.str.lower()
df.cliente_id.str.fullmatch(r'CLI\d{6}'); df.cpf.str.fullmatch(r'\d{3}\.\d{3}\.\d{3}-\d{2}')
df.cpf.str.replace(r'\D','',regex=True).duplicated()
dc = pd.to_datetime(df.data_cadastro); dx = pd.to_datetime(df.data_cancelamento)
(dx < dc).sum(); (dx == dc).sum()
pd.crosstab(df.plano, df.valor_mensalidade)
df.groupby('cidade').estado.nunique()                      # cidade em mais de 1 UF
pd.crosstab(df.abriu_chamado, df.tempo_resposta_chamado_h.notna())
pd.crosstab(df.churn_30d, df.data_cancelamento.notna())
(df.ticket_medio_30d >= 10000).sum(); df.duplicated().sum()
```

## 1. Shape
- Linhas × colunas: **10.000 × 15**, igual ao esperado.
- Linhas totalmente duplicadas: **0**.
- Linhas duplicadas ignorando `cliente_id`: **0**.
- O sufixo numérico de `cliente_id` vai de **1** a **10.000**.

## 2. Tipos de cada coluna

| Coluna | Tipo pandas | Observação |
|---|---|---|
| cliente_id | object | Todos no formato `CLIxxxxxx`: **0** fora do padrão |
| nome | object | |
| cpf | object | **0** fora da máscara `000.000.000-00` |
| data_cadastro | object (texto) | **0** fora de AAAA-MM-DD. Não é datetime |
| data_cancelamento | object (texto) | **0** fora de AAAA-MM-DD. Não é datetime |
| cidade | object | |
| estado | object | |
| plano | object | |
| valor_mensalidade | float64 | |
| notificacoes_7d | int64 | Sem nulos; o CSV puro não guarda o tipo `Int64` |
| transacoes_30d | float64 | Tem NaN; todos os valores não nulos são inteiros (**0** com parte decimal) |
| ticket_medio_30d | float64 | |
| abriu_chamado | bool | |
| tempo_resposta_chamado_h | float64 | |
| churn_30d | bool | |

Tipos mistos dentro de coluna: **0** detectados.

## 3. Valores ausentes por coluna

| Coluna | Ausentes | % |
|---|---|---|
| data_cancelamento | **8.647** | **86,47%** |
| tempo_resposta_chamado_h | **7.476** | **74,76%** |
| transacoes_30d | **1.215** | **12,15%** |
| Demais 12 colunas | **0** | **0,00%** |

As contagens do arquivo bruto (10.016 linhas) eram **8.663** e **7.489**. A diferença (**16** e **13**) vem das
**16** duplicatas de `cliente_id` removidas na limpeza.

## 4. Duplicatas por coluna-chave
- `cliente_id`: **0** duplicados (**10.000** únicos).
- `cpf` (com máscara): **0** duplicados. `cpf` (só dígitos): **0** duplicados.
- CPFs com todos os dígitos iguais: **0**.
- `nome`: **1.617** nomes distintos em 10.000 linhas. Repetição esperada em nomes; CPF e id são únicos.

## 5. Variações de formato em colunas categóricas
- **Espaços** nas pontas: **0** em cliente_id, nome, cpf, cidade, estado e plano. **0** espaços duplos.
- **Plano:** só 2 valores, Básico (**5.996**) e Premium (**4.004**).
- **Estado:** **23** UFs, todas válidas, em maiúsculas. Não aparecem AC, AP, RO e RR.
  - SP 1.579, MG 1.019, RJ 892, CE 631, PR 552, PA 549, SE 530, PB 515, PI 498, RS 497, PE 343, SC 336, RN 312,
    ES 196, MT 191, TO 190, DF 178, MS 176, BA 173, AL 172, MA 163, GO 157, AM 151.
- **Cidade:** **60** grafias distintas, das quais **2** são erros de digitação residuais (**3** registros):
  - "Fortleza": **2** registros (CE; `CLI001524` e `CLI005430`), contra **142** de "Fortaleza".
  - "Belo Horizote": **1** registro (MG; `CLI001428`), contra **192** de "Belo Horizonte".
  - Os três têm `churn_30d` = falso. Os outros **58** valores não apresentam variação visível.
- Cidade × estado: **0** cidades em mais de uma UF.

## 6. Valores suspeitos e coerência

Coerências com **0** violações:
- **Plano × mensalidade:** Básico = R$ 19,90 (**5.996**), Premium = R$ 49,90 (**4.004**), sem cruzamento.
- **Cadastro:** de 01/01/2024 a 01/04/2026, **0** nulos, **0** inválidas.
- **Cancelamento:** de 01/04/2026 a 30/04/2026 (**30** datas distintas), **1.353** preenchidas.
- **Cancelamento × cadastro:** cancelamento antes do cadastro em **0** casos; no mesmo dia em **0**.
- **Tempo de resposta × chamado:** quem abriu chamado tem **2.524** tempos e **0** vazios; quem não abriu tem **7.476** vazios e **0** preenchidos.
- **Churn × data de cancelamento:** churn verdadeiro, **1.353** com data e **0** sem; falso, **8.647** sem data e **0** com.

Valores numéricos que merecem registro:
- **ticket_medio_30d ≥ R$ 10.000,00:** **677** registros, de R$ 99.077,75 a R$ 999.842,62.
  Não há valores entre R$ 1.000,00 e R$ 9.999,99; o maior valor abaixo disso é R$ 417,99 (distribuição bimodal).
  Média **R$ 37.073,95** contra mediana **R$ 69,18**.
- **ticket_medio_30d = 0:** **1.452** registros: **237** com `transacoes_30d` = 0 e **1.215** com `transacoes_30d` ausente.
  Não há ticket 0 com transações > 0 (**0**), nem ticket > 0 com transações = 0 (**0**).
- **transacoes_30d:** de **0** a **103**, **0** negativos, **1.215** nulos.
- **notificacoes_7d:** inteiros de **0** a **12**; os níveis 0 e 1 têm ~**1.520** clientes cada, e 2 a 12 entre **580** e **674**.
- **tempo_resposta_chamado_h:** mínimo **0,5**, mediana **17,5**, média **26,39**, máximo **95,9**.
- **valor_mensalidade:** 2 valores distintos (R$ 19,90 e R$ 49,90).

## 7. Resumo executivo: o que precisa de atenção antes da análise

1. **ticket_medio_30d:** **677** valores ≥ R$ 10.000,00 distorcem média e desvio; **1.452** zeros. Decisão pendente.
2. **transacoes_30d:** **1.215** ausentes (**12,15%**), todos com ticket 0, e **237** zeros explícitos também com ticket 0.
   A coluna não distingue "sem transações" de "dado ausente". Decisão pendente.
3. **Cidades com grafia residual:** "Fortleza" (**2**) e "Belo Horizote" (**1**), **3** registros.
4. **Tipos ao reler o CSV:** `notificacoes_7d` e `transacoes_30d` voltam como int64 e float64, e as datas como texto.
   O carregamento do projeto (`carregar_limpo`) converte essas colunas.
5. **Cobertura geográfica:** **23** das 27 UFs; faltam AC, AP, RO e RR.
6. **Sem achados em:** unicidade de `cliente_id` e CPF, máscara de CPF, plano × mensalidade, cidade × UF,
   cancelamento ≥ cadastro, coerência de chamado e de churn, espaços e caixa.
