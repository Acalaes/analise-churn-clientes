---
name: relatorio-executivo
description: Gera o PDF executivo de churn da PixPay em 3 páginas fixas (diagnóstico, drivers, plano de ação) com reportlab. Use ao montar ou atualizar o relatório para o CEO.
---

# Skill: relatorio-executivo

PDF executivo de churn em 3 páginas fixas.
Estrutura não negociável — sempre 3 páginas nessa ordem.

## Estrutura do PDF

Pág 1 — Diagnóstico: churn real em destaque, briefing vs dados,
recomendação principal em caixa de destaque.

Pág 2 — Drivers: 3 blocos visuais + insight bônus.

Pág 3 — Plano de ação por driver com prazos + rodapé.

## Regras

- Usar reportlab | Paleta: azul #1F4E79, vermelho #C5221F
- Números em formato brasileiro
- Salvar em reports/relatorio_executivo_pixpay.pdf
- Não construa nenhum relatório fora da pastaa reports
- Caso o aqrquivos já exista, não sobrescrever e criar um novo sufixo incremental (ex: relatorio_executivo_pixpay_1.pdf)

