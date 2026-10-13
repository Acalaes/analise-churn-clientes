# Análise de churn de clientes

Projeto de análise de dados estruturado, de ponta a ponta: auditoria de qualidade, limpeza documentada, análise dos drivers de cancelamento e relatório executivo. Os dados são **sintéticos** e simulam a base de uma fintech de cartão e Pix com 10.000 clientes.

## Principais resultados

| Medida | Resultado |
|---|---|
| Churn de abril/2026 | **13,53%** (1.353 de 10.000), contra 8% informado |
| Chamado respondido em mais de 24 h | **50,39%** de churn (contra 10,08% até 24 h) |
| Menos de 2 notificações | **25,32%** de churn (contra 8,36% com 2 ou mais) |
| Os dois sinais juntos | **86,81%** de churn (235 clientes) |

Tudo é **associação, não prova de causa**. As limitações e as perguntas em aberto estão em [DESCOBERTAS_ANALISE_CHURN.md](DESCOBERTAS_ANALISE_CHURN.md).

## Estrutura

| Pasta | Conteúdo |
|---|---|
| `data/` | Dados brutos, somente leitura (não versionados, veja abaixo) |
| `notebooks/` | Auditoria de qualidade e análise dos drivers |
| `scripts/` | Código reutilizável: limpeza, análises, gráficos e relatório |
| `reports/` | Gráficos (PNG) e relatório executivo |
| `.claude/agents/` | Subagents: auditor de dados (cético) e caçador de insights (curioso) |
| `.claude/skills/` | Skills: gráfico padronizado e relatório executivo de 3 páginas |
| `CLAUDE.md` | Contexto, padrões de código e workflow do projeto |

## Como reproduzir

1. Instale as dependências (Python 3.9 ou superior):

   ```
   pip install -r requirements.txt
   ```

2. Coloque o CSV bruto em `data/clientes_pixpay.csv` (10.016 linhas, 15 colunas). A pasta `data/` não é versionada porque contém CPFs e nomes, mesmo que sintéticos.

3. Na raiz do projeto, rode:

   ```
   python scripts/limpar_dados.py
   python scripts/investigar_transacoes.py
   python scripts/analisar_drivers.py
   python scripts/analisar_notificacoes.py
   python scripts/analisar_plano.py
   python scripts/gerar_excel_auditoria.py
   ```

## Bibliotecas

| Biblioteca | Para que serve | Onde é usada |
|---|---|---|
| pandas | Tabelas de dados | Carga, validação de tipos, limpeza e análises |
| numpy | Cálculo numérico e sorteios | Testes de permutação com semente fixa, contagens e faixas |
| matplotlib | Gráficos | Gráficos salvos em `reports/` |
| seaborn | Gráficos estatísticos | Tema e gráficos da auditoria |
| reportlab | Geração de PDF | Relatório executivo |
| openpyxl | Leitura e escrita de Excel | Planilha de auditoria |
| jupyter | Notebooks | Auditoria e análise dos drivers |

Também usa módulos da biblioteca padrão do Python: `re`, `unicodedata`, `pathlib` e `statistics`.

## Princípio de trabalho

Validar pelo número, nunca pela frase. Cada conclusão sai de um número reproduzível pelo código em `scripts/`.

## Licença

[MIT](LICENSE)
