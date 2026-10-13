"""Gera reports/relatorio_executivo_pixpay.pdf (skill relatorio-executivo): 3 páginas fixas, reportlab.

Uso (a partir da raiz do projeto):  python scripts/gerar_relatorio_executivo.py
Os números são calculados a partir de data/clientes_pixpay_limpo.csv (somente leitura) e CONFERIDOS contra os documentos
DESCOBERTAS_ANALISE_CHURN.md e AUDITORIA_FINAL_DADOS_LIMPOS.md; os dados da auditoria bruta vêm de auditoria_pixpay.md.
Se algum número divergir dos documentos, o script para com erro.
Decisões de redação (documentadas porque são escolhas, não dados):
- "poucas notificações (0-1)" em vez de "onboarding": o dataset não tem dicionário, a janela de notificacoes_7d não está confirmada.
- "associado a" em vez de "causa": os dados mostram associação, não causalidade.
- Insight bônus usa o perfil que existe nos dados (Premium + 0-1 notificação + chamado > 24h).
"""
import math
import re
import sys
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph

sys.path.insert(0, str(Path(__file__).resolve().parent))
from investigar_transacoes import carregar_limpo  # noqa: E402
from grafico_demografia_churn import CAPITAIS  # noqa: E402  (mesma definição de capital do gráfico demográfico)

RAIZ = Path(__file__).resolve().parent.parent
SAIDA = RAIZ / "reports" / "relatorio_executivo_pixpay.pdf"  # skill: relatórios só dentro de reports/
AZUL, VERMELHO = colors.HexColor("#1F4E79"), colors.HexColor("#C5221F")
CINZA, CINZA_CLARO = colors.HexColor("#5F6368"), colors.HexColor("#EEF2F6")
ANALISTA, DATA_RELATORIO = "Alexandre Calaes", "13/10/2026"
W, H = A4
M = 40  # margem


def proximo_nome_livre(base=SAIDA):
    """Regra da skill: se o arquivo já existe, NÃO sobrescrever; usar sufixo incremental (_1, _2, ...)."""
    if not base.exists():
        return base
    i = 1
    while (base.parent / f"{base.stem}_{i}{base.suffix}").exists():
        i += 1
    return base.parent / f"{base.stem}_{i}{base.suffix}"


def br(v, casas=2):
    """1234.5 -> '1.234,50'"""
    return f"{v:,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def pct(v, casas=2):
    return br(v, casas) + "%"


def wilson(k, n, z=1.96):
    p = k / n
    den = 1 + z * z / n
    c = (p + z * z / 2 / n) / den
    h = z * math.sqrt(p * (1 - p) / n + z * z / 4 / n / n) / den
    return (c - h) * 100, (c + h) * 100


def calcular():
    """Retorna dict com todos os números do relatório."""
    d = carregar_limpo()
    c = d["churn_30d"]
    lento = d["tempo_resposta_chamado_h"] > 24
    baixo = d["notificacoes_7d"] <= 1
    prem = d["plano"] == "Premium"
    n = len(d)
    r = {"n": n, "canc": int(c.sum()), "churn": c.mean() * 100}
    r["ic"] = wilson(r["canc"], n)
    ate24 = d["abriu_chamado"] & ~lento
    r["lento_n"], r["lento_c"] = int(lento.sum()), int(c[lento].sum())
    r["lento_pct"], r["ate24_pct"] = c[lento].mean() * 100, c[ate24].mean() * 100
    r["baixo_n"], r["baixo_c"] = int(baixo.sum()), int(c[baixo].sum())
    r["baixo_pct"], r["alto_pct"] = c[baixo].mean() * 100, c[~baixo].mean() * 100
    r["prem_n"], r["prem_c"] = int(prem.sum()), int(c[prem].sum())
    r["prem_pct"], r["bas_pct"] = c[prem].mean() * 100, c[~prem].mean() * 100
    dois = baixo & lento
    r["dois_n"], r["dois_pct"] = int(dois.sum()), c[dois].mean() * 100
    r["canc_8"] = int(0.08 * n)  # cancelamentos que dariam exatamente 8%
    tri = prem & baixo & lento
    r["tri_n"], r["tri_c"] = int(tri.sum()), int(c[tri].sum())
    r["tri_pct"] = c[tri].mean() * 100
    r["tri_ativos"] = r["tri_n"] - r["tri_c"]
    r["mens_perdida"] = float(c[prem].sum() * 49.9 + c[~prem].sum() * 19.9)
    r["mens_prem"] = float(c[prem].sum() * 49.9)
    r["mens_prem_pct"] = r["mens_prem"] / r["mens_perdida"] * 100
    algum = baixo | lento
    r["algum_n"], r["algum_c"] = int(algum.sum()), int(c[algum].sum())
    # excesso de cancelamentos em relação ao churn de quem não tem nenhum sinal (associação, não evitável comprovado)
    r["excesso"] = round(c[algum].sum() - algum.sum() * c[~algum].mean())
    cap = d["cidade"].isin(CAPITAIS)
    r["cap_n"], r["cap_c"], r["cap_pct"] = int(cap.sum()), int(c[cap].sum()), c[cap].mean() * 100
    r["int_n"], r["int_c"], r["int_pct"] = int((~cap).sum()), int(c[~cap].sum()), c[~cap].mean() * 100
    semtr = d["transacoes_30d"].isna()
    r["semtr_n"], r["semtr_c"] = int(semtr.sum()), int(c[semtr].sum())
    r["semtr_pct"], r["comtr_pct"] = c[semtr].mean() * 100, c[~semtr].mean() * 100
    r["aus_cancel"], r["aus_resp"] = int(d["data_cancelamento"].isna().sum()), int(d["tempo_resposta_chamado_h"].isna().sum())
    r["tickets_extremos"] = int((d["ticket_medio_30d"] >= 10000).sum())
    r["ufs"] = int(d["estado"].nunique())
    return conferir_e_ler_documentos(r)


def _ler(nome):
    return (RAIZ / nome).read_text(encoding="utf-8")


def conferir_e_ler_documentos(r):
    """Lê os .md, confere os números calculados contra eles e acrescenta a r os dados da auditoria."""
    desc = _ler("DESCOBERTAS_ANALISE_CHURN.md")
    final = _ler("AUDITORIA_FINAL_DADOS_LIMPOS.md")
    bruta = _ler("auditoria_pixpay.md")
    esperados = {"churn": pct(r["churn"]), "lento": pct(r["lento_pct"]), "ate24": pct(r["ate24_pct"]),
                 "baixo": pct(r["baixo_pct"]), "alto": pct(r["alto_pct"]), "prem": pct(r["prem_pct"]),
                 "bas": pct(r["bas_pct"]), "dois": pct(r["dois_pct"]), "tri": pct(r["tri_pct"]),
                 "mens_total": "R$ " + br(r["mens_perdida"]), "mens_prem": "R$ " + br(r["mens_prem"]),
                 "mens_prem_pct": pct(r["mens_prem_pct"], 1), "excesso": br(r["excesso"], 0)}
    faltando = {k: v for k, v in esperados.items() if v not in desc}
    if faltando:
        raise ValueError(f"Números do CSV não aparecem em DESCOBERTAS_ANALISE_CHURN.md: {faltando}")
    if "10.000 × 15" not in final:
        raise ValueError("AUDITORIA_FINAL_DADOS_LIMPOS.md não confirma 10.000 × 15")

    def valor(texto, rotulo):
        m = re.search(re.escape(rotulo) + r" \| (\d+)", texto)
        if not m:
            raise ValueError(f"Linha '{rotulo}' não encontrada em auditoria_pixpay.md")
        return int(m.group(1))

    hip = _ler("HIPOTESES_INSIGHT_HUNTER.md")
    esperados_h = {"capital": pct(r["cap_pct"]), "interior": pct(r["int_pct"]), "sem transações": pct(r["semtr_pct"]),
                   "ausentes cancel.": br(r["aus_cancel"], 0), "ausentes resp.": br(r["aus_resp"], 0),
                   "tickets extremos": str(r["tickets_extremos"])}
    for k, v in esperados_h.items():
        if v not in hip and v not in final:
            raise ValueError(f"Número ({k}: {v}) não aparece nos documentos dos subagentes")
    m = re.search(r"Ajustado: \*\*\+([\d,]+) p\.p\.\*\* \(IC 95%: \+([\d,]+) a \+([\d,]+)\)", hip)
    c1 = re.search(r"\*\*−([\d,]+) p\.p\.\*\* para capital \(bootstrap IC 95%: −([\d,]+) a −([\d,]+)\)", hip)
    if not (m and c1):
        raise ValueError("Ajustes (+2,69 p.p. e −3,39 p.p.) não encontrados em HIPOTESES_INSIGHT_HUNTER.md")
    r["prem_aj"], r["prem_aj_ic"] = m.group(1), (m.group(2), m.group(3))
    r["cap_aj"], r["cap_aj_ic"] = c1.group(1), (c1.group(2), c1.group(3))
    r["linhas_brutas"] = valor(bruta, "Linhas no CSV")
    r["duplicadas"] = valor(bruta, "Linhas excedentes por cliente_id")
    r["com_problema"] = valor(bruta, "Linhas com pelo menos 1 problema")
    return r


def para(cv, texto, x, y_topo, largura, tam=10, cor=colors.black, negrito=False, leading=None):
    """Desenha parágrafo com quebra de linha; retorna a altura usada."""
    st = ParagraphStyle("p", fontName="Helvetica-Bold" if negrito else "Helvetica", fontSize=tam, textColor=cor,
                        leading=leading or tam * 1.3, alignment=TA_LEFT)
    p = Paragraph(texto, st)
    _, h = p.wrap(largura, 1000)
    p.drawOn(cv, x, y_topo - h)
    return h


def cabecalho(cv, titulo, pagina):
    cv.setFillColor(AZUL)
    cv.rect(0, H - 52, W, 52, stroke=0, fill=1)
    cv.setFillColor(colors.white)
    cv.setFont("Helvetica-Bold", 15)
    cv.drawString(M, H - 33, titulo)
    cv.setFont("Helvetica", 10)
    cv.drawRightString(W - M, H - 33, f"PixPay | Análise de churn | pág. {pagina}/3")


def rodape(cv, texto):
    cv.setStrokeColor(colors.lightgrey)
    cv.line(M, 62, W - M, 62)
    para(cv, texto, M, 58, W - 2 * M, tam=7.5, cor=CINZA, leading=9.5)


def barras(cv, x, y, largura, itens, maximo):
    """Barras horizontais: itens = [(rótulo, valor %, cor)]."""
    for i, (rot, v, cor) in enumerate(itens):
        yy = y - i * 34
        cv.setFillColor(CINZA)
        cv.setFont("Helvetica", 9)
        cv.drawString(x, yy + 18, rot)
        cv.setFillColor(cor)
        cv.rect(x, yy, largura * v / maximo, 14, stroke=0, fill=1)
        cv.setFillColor(colors.black)
        cv.setFont("Helvetica-Bold", 10)
        cv.drawString(x + largura * v / maximo + 5, yy + 2, pct(v))


def qualidade_sub(r):
    """Resumo da auditoria final (AUDITORIA_FINAL_DADOS_LIMPOS.md)."""
    return (f"• Auditoria final do arquivo limpo: <b>{br(r['n'], 0)} × 15</b>, <b>0</b> linhas duplicadas, <b>0</b> violações em "
            "6 checagens de coerência (plano x mensalidade, cidade x UF, datas, chamado x tempo de resposta, churn x cancelamento).<br/>"
            f"• Ausentes esperados e consistentes: <b>{br(r['aus_cancel'], 0)}</b> sem data de cancelamento e <b>{br(r['aus_resp'], 0)}</b> "
            "sem tempo de resposta (quem não cancelou / não abriu chamado). "
            f"Cobertura de <b>{r['ufs']}</b> das 27 UFs.<br/>"
            f"• Pendências abertas: <b>{br(r['semtr_n'], 0)}</b> clientes sem transações informadas, <b>{br(r['tickets_extremos'], 0)}</b> tickets "
            "acima de R$ 10.000,00, 3 registros com cidade digitada errado e 99% dos CPFs com dígito inválido (dados provavelmente sintéticos). "
            "Nenhuma altera as conclusões; as duas primeiras ainda aguardam decisão.")


def pagina1(cv, r):
    cabecalho(cv, "Diagnóstico: churn real vs. briefing", 1)
    y = H - 80
    cv.setFillColor(colors.black)
    cv.setFont("Helvetica", 10)
    cv.drawString(M, y, f"Relatório executivo para o CEO | Analista: {ANALISTA} | {DATA_RELATORIO}")
    # número em destaque
    y -= 28
    cv.setFillColor(VERMELHO)
    cv.setFont("Helvetica-Bold", 64)
    cv.drawString(M, y - 40, pct(r["churn"]))
    cv.setFillColor(colors.black)
    para(cv, f"<b>churn real de abril/2026</b><br/>{br(r['canc'], 0)} cancelamentos em {br(r['n'], 0)} clientes<br/>"
             f"intervalo de confiança de 95%: {pct(r['ic'][0])} a {pct(r['ic'][1])}", 290, y - 5, W - M - 290, tam=12, leading=16)
    # briefing vs dados
    y -= 80
    cv.setFont("Helvetica-Bold", 13)
    cv.setFillColor(AZUL)
    cv.drawString(M, y, "Briefing versus dados")
    y -= 16
    linhas = [("", "Briefing", "Dados"),
              ("Churn mensal", "8,00%", pct(r["churn"])),
              ("Diferença", "", f"+{br(r['churn'] - 8)} p.p. ({br((r['churn'] / 8 - 1) * 100, 0)}% acima do briefing)"),
              ("Cancelamentos em abril", f"{br(r['canc_8'], 0)} (equivalem a 8%)", f"{br(r['canc'], 0)} ({br(r['canc'] - r['canc_8'], 0)} a mais que o briefing)"),
              ("Evolução 3% para 8% em 6 meses", "informada", "não verificável (só há abril)")]
    cols = [M, M + 190, M + 330]
    for i, lin in enumerate(linhas):
        cv.setFillColor(AZUL if i == 0 else (CINZA_CLARO if i % 2 == 0 else colors.white))
        cv.rect(M, y - 6, W - 2 * M, 20, stroke=0, fill=1)
        cv.setFillColor(colors.white if i == 0 else colors.black)
        cv.setFont("Helvetica-Bold" if i == 0 else "Helvetica", 10)
        for x, t in zip(cols, lin):
            cv.drawString(x + 4, y, t)
        y -= 20
    y -= 8
    hc = para(cv, "O arquivo traz um único mês de cancelamentos (01/04/2026 a 30/04/2026). Por isso é possível medir o churn de abril, "
             "mas não confirmar se ele subiu de 3% para 8% nos seis meses anteriores.", M, y, W - 2 * M, tam=10, cor=CINZA)
    if r["completo"]:
        # confiança nos dados (auditoria)
        qy = y - hc - 30
        cv.setFont("Helvetica-Bold", 13)
        cv.setFillColor(AZUL)
        cv.drawString(M, qy, "Confiança nos dados (auditoria final)" if r["sub"] else "Confiança nos dados (auditoria)")
        para(cv, qualidade_sub(r) if r["sub"] else f"• O arquivo bruto tinha <b>{br(r['linhas_brutas'], 0)}</b> linhas; <b>{br(r['com_problema'], 0)}</b> "
                 f"({pct(r['com_problema'] / r['linhas_brutas'] * 100, 1)}) tinham pelo menos 1 problema de formato (plano, datas, CPF, mensalidade). "
                 f"Após a limpeza: <b>{br(r['n'], 0)}</b> clientes, com <b>{br(r['duplicadas'], 0)}</b> duplicatas removidas.<br/>"
                 "• Auditoria final: sem inconsistências de datas, plano x mensalidade, chamado x tempo de resposta e churn x cancelamento.<br/>"
                 "• Pendências abertas, que não alteram as conclusões acima: <b>1.215</b> clientes sem transações informadas, "
                 "<b>677</b> tickets acima de R$ 10.000,00 e 99% dos CPFs com dígito inválido (dados provavelmente sintéticos).",
             M, qy - 8, W - 2 * M, tam=9.5, leading=12.5)
    # caixa de recomendação
    caixa_y, caixa_h = (110 if r["sub"] else (120 if r["completo"] else 230)), (190 if r["sub"] else 200)
    cv.setFillColor(CINZA_CLARO)
    cv.setStrokeColor(VERMELHO)
    cv.setLineWidth(2.5)
    cv.roundRect(M, caixa_y, W - 2 * M, caixa_h, 8, stroke=1, fill=1)
    cv.setFillColor(VERMELHO)
    cv.setFont("Helvetica-Bold", 14)
    cv.drawString(M + 16, caixa_y + caixa_h - 26, "RECOMENDAÇÃO PRINCIPAL")
    cv.setFillColor(AZUL)
    cv.setFont("Helvetica-Bold", 20)
    cv.drawString(M + 16, caixa_y + caixa_h - 56, "Adotar já um SLA de suporte de 24 horas")
    para(cv, f"Entre os <b>{br(r['lento_n'], 0)} clientes</b> cujo chamado levou mais de 24 horas, o churn foi de "
             f"<b>{pct(r['lento_pct'])}</b>. Com resposta em até 24 horas foi de <b>{pct(r['ate24_pct'])}</b>, "
             f"praticamente igual ao de quem nunca abriu chamado. É o fator mais fortemente associado ao cancelamento "
             f"e o mais direto de agir.", M + 16, caixa_y + caixa_h - 72, W - 2 * M - 32, tam=11, leading=15)
    para(cv, "Cuidado de leitura: os dados mostram associação, não causa. O chamado lento pode ter ocorrido depois de o "
             "cliente já ter decidido sair. Por isso a recomendação é implantar o SLA e medir o resultado.",
         M + 16, caixa_y + 62, W - 2 * M - 32, tam=9.5, cor=CINZA, leading=12.5)
    rodape(cv, f"Fonte: data/clientes_pixpay_limpo.csv ({br(r['n'], 0)} clientes, após limpeza). Análise: {ANALISTA}. "
               "Churn = cancelamento entre 01/04/2026 e 30/04/2026 sobre a base inteira.")


def bloco(cv, y_topo, altura, titulo, grande, legenda, itens, maximo, texto):
    cv.setFillColor(CINZA_CLARO)
    cv.roundRect(M, y_topo - altura, W - 2 * M, altura, 6, stroke=0, fill=1)
    cv.setFillColor(AZUL)
    cv.setFont("Helvetica-Bold", 12.5)
    cv.drawString(M + 12, y_topo - 20, titulo)
    cv.setFillColor(VERMELHO)
    cv.setFont("Helvetica-Bold", 34)
    cv.drawString(M + 12, y_topo - 62, grande)
    para(cv, legenda, M + 12, y_topo - 68, 145, tam=9, cor=CINZA)
    barras(cv, M + 170, y_topo - 56, 110, itens, maximo)
    para(cv, texto, M + 345, y_topo - 14, W - 2 * M - 345 - 10, tam=9, leading=11.5)


def pagina2(cv, r):
    cabecalho(cv, "Drivers: o que está associado ao cancelamento", 2)
    top, alt, gap = H - 70, (138 if r["sub"] else 150), 10
    bloco(cv, top, alt, "1. Suporte demorado (chamado > 24 h)", f"{br(r['lento_pct'] / r['ate24_pct'], 1)}x".replace(",0x", "x"),
          f"mais churn que com resposta em até 24 h<br/>({br(r['lento_n'], 0)} clientes)",
          [("Resposta > 24 h", r["lento_pct"], VERMELHO), ("Resposta até 24 h", r["ate24_pct"], AZUL)], 60,
          f"<b>{br(r['lento_c'], 0)} de {br(r['lento_n'], 0)}</b> clientes com chamado lento cancelaram. "
          "Há um degrau claro em 24 h; depois dele o churn fica perto de 50% e não piora de forma contínua.")
    bloco(cv, top - alt - gap, alt, "2. Poucas notificações (0 ou 1 em 7 dias)",
          f"{br(r['baixo_pct'] / r['alto_pct'], 1)}x".replace(",0x", "x"),
          f"mais churn; {pct(r['baixo_n'] / r['n'] * 100, 1)} da base está exposta<br/>({br(r['baixo_n'], 0)} clientes)",
          [("0 ou 1 notificação", r["baixo_pct"], VERMELHO), ("2 ou mais", r["alto_pct"], AZUL)], 30,
          f"<b>{br(r['baixo_c'], 0)} de {br(r['baixo_n'], 0)}</b> cancelaram. Não há gradiente entre 2 e 12 notificações, "
          "e o dataset não define o que a coluna mede. "
          + ("Os dois grupos são iguais em transações, plano e geografia, então não é &quot;baixo engajamento&quot; "
             "nem &quot;onboarding&quot; (não confirmado)." if r["completo"] else
             "Rótulo de &quot;onboarding&quot; ainda não confirmado."))
    bloco(cv, top - 2 * (alt + gap), alt, "3. Plano Premium",
          f"+{br((r['prem_pct'] / r['bas_pct'] - 1) * 100, 1)}%",
          f"de churn relativo ao Básico<br/>(+{br(r['prem_pct'] - r['bas_pct'])} p.p.)",
          [("Premium", r["prem_pct"], VERMELHO), ("Básico", r["bas_pct"], AZUL)], 20,
          f"Premium: <b>{br(r['prem_c'], 0)} de {br(r['prem_n'], 0)}</b>. Diferença pequena perto dos dois primeiros drivers, "
          + (f"mas estável. Em dinheiro pesa mais: o Premium responde por <b>{pct(r['mens_prem_pct'], 1)}</b> da mensalidade perdida "
             f"(R$ {br(r['mens_prem'])} de R$ {br(r['mens_perdida'])})." if r["completo"] else
             "mas estável: aparece com a mesma direção dentro de todos os perfis de risco.")
          + (f" Ajustado por chamado e notificações: <b>+{r['prem_aj']} p.p.</b> (IC 95%: +{r['prem_aj_ic'][0]} a +{r['prem_aj_ic'][1]})."
             if r["sub"] else ""))
    # insight bônus
    yb = top - 3 * (alt + gap)
    cv.setFillColor(AZUL)
    cv.roundRect(M, yb - 125, W - 2 * M, 125, 6, stroke=0, fill=1)
    cv.setFillColor(colors.white)
    cv.setFont("Helvetica-Bold", 12.5)
    cv.drawString(M + 12, yb - 20, "Insight bônus: os três fatores juntos")
    cv.setFont("Helvetica-Bold", 34)
    cv.drawString(M + 12, yb - 62, pct(r["tri_pct"], 1))
    para(cv, f"Clientes <b>Premium</b> com <b>0 ou 1 notificação</b> e <b>chamado lento</b>: <b>{br(r['tri_n'], 0)} clientes</b>, "
             f"<b>{br(r['tri_c'], 0)} cancelaram</b> e {br(r['tri_ativos'], 0)} ainda estão ativos. Só {pct(r['tri_n'] / r['n'] * 100)} da base, "
             f"mas prioridade natural para uma fila de atendimento. Só os dois primeiros fatores já levam o churn a "
             f"{pct(r['dois_pct'])} ({br(r['dois_n'], 0)} clientes); o plano pouco acrescenta.",
         M + 190, yb - 30, W - 2 * M - 202, tam=9.5, leading=12.5, cor=colors.white)
    cv.setFillColor(colors.white)
    cv.setFont("Helvetica", 9)
    cv.drawString(M + 12, yb - 82, f"{br(r['tri_c'], 0)} de {br(r['tri_n'], 0)} cancelaram")
    if r["sub"]:
        ys = yb - 125 - 10
        cv.setFillColor(CINZA_CLARO)
        cv.roundRect(M, ys - 118, W - 2 * M, 118, 6, stroke=0, fill=1)
        cv.setFillColor(AZUL)
        cv.setFont("Helvetica-Bold", 12)
        cv.drawString(M + 12, ys - 18, "Também encontrado na análise exploratória")
        para(cv, f"• <b>Fora de capital churna mais:</b> <b>{pct(r['int_pct'])}</b> ({br(r['int_c'], 0)}/{br(r['int_n'], 0)}) contra "
                 f"<b>{pct(r['cap_pct'])}</b> ({br(r['cap_c'], 0)}/{br(r['cap_n'], 0)}); ajustado, as capitais têm <b>-{r['cap_aj']} p.p.</b> "
                 f"(IC 95%: -{r['cap_aj_ic'][0]} a -{r['cap_aj_ic'][1]}). Passa na correção de Bonferroni; mecanismo desconhecido.<br/>"
                 f"• <b>Não são drivers:</b> clientes sem transações ({pct(r['semtr_pct'])} contra {pct(r['comtr_pct'])}) e data de cadastro ou de "
                 "cancelamento (sem sazonalidade nem efeito de safra).<br/>"
                 "• <b>Provável ruído:</b> a faixa de ticket de R$ 78,23 a R$ 118,87 no Premium (19,1%; p = 0,0008 não passa no limiar de "
                 "0,00029 (Bonferroni para ~170 testes).",
             M + 12, ys - 26, W - 2 * M - 24, tam=9, leading=11.5)
    rodape(cv, "Associações observadas em um único mês; limiares de 24 h e de 2 notificações escolhidos depois de ver os dados "
               "(o intervalo de confiança não desconta isso). Teste de permutação com correção de Bonferroni nos rankings.")


def pagina3(cv, r):
    cabecalho(cv, "Plano de ação por driver", 3)
    y = H - 78
    if r["completo"]:
        premium_itens = [
            "Fazer pesquisa de cancelamento por plano para entender percepção de valor e preço (R$ 49,90 contra R$ 19,90).",
            f"Priorizar pelo valor, não pelo risco: o Premium é {pct(r['prem_n'] / r['n'] * 100, 0)} dos clientes e "
            f"{pct(r['mens_prem_pct'], 1)} da mensalidade perdida (R$ {br(r['mens_prem'])} de R$ {br(r['mens_perdida'])}).",
            "Revisar benefícios do Premium e a oferta de retenção; incluir a receita de transações na conta (não está nos dados)."]
        bonus_itens = [f"Resgate dos {br(r['tri_n'], 0)} clientes Premium com os três fatores ({pct(r['tri_pct'], 1)} de churn; "
                       f"só {br(r['tri_ativos'], 0)} ainda ativos) e alerta permanente para os {br(r['dois_n'], 0)} clientes com chamado lento "
                       f"e 0 ou 1 notificação ({pct(r['dois_pct'])} de churn)."]
    else:
        premium_itens = [
            "Fazer pesquisa de cancelamento por plano para entender percepção de valor e preço (R$ 49,90 contra R$ 19,90).",
            "Revisar benefícios do Premium e a oferta de retenção para esse público.",
            "Avaliar o efeito em receita: o Premium concentra a maior parte da mensalidade perdida."]
        bonus_itens = [f"Marcar os clientes Premium com 0 ou 1 notificação e chamado lento como prioridade máxima no atendimento "
                       f"({br(r['tri_n'], 0)} clientes, {pct(r['tri_pct'], 1)} de churn)."]
    if r["sub"]:
        premium_itens = premium_itens[:1] + [
            f"Premium é {pct(r['prem_n'] / r['n'] * 100, 0)} dos clientes e {pct(r['mens_prem_pct'], 1)} da mensalidade perdida "
            f"(R$ {br(r['mens_prem'])} de R$ {br(r['mens_perdida'])}); o efeito do plano persiste após ajuste (+{r['prem_aj']} p.p.).",
            "Revisar benefícios e oferta de retenção do Premium; incluir a receita de transações na conta (não está nos dados)."]
    acoes = [
        ("1. Suporte demorado", "IMEDIATO (início em até 7 dias)",
         ["Implantar o SLA de 24 horas para todo chamado e medir o cumprimento por semana.",
          "Criar fila prioritária para chamados que passam de 12 horas sem resposta.",
          "Meta: reduzir o número de chamados acima de 24 h e acompanhar o churn de quem abre chamado."]),
        ("2. Poucas notificações", "30 dias",
         ["Confirmar com a PixPay o que a coluna notificacoes_7d mede e em qual janela de tempo.",
          "Se a medida for confirmada, testar ativar clientes com 0 ou 1 notificação, com grupo de controle.",
          "Medir se o churn cai em quem recebe o contato, antes de ampliar."]),
        ("3. Plano Premium", "60 dias", premium_itens),
        ("Insight bônus: " + ("os sinais juntos" if r["completo"] else "três fatores juntos"), "IMEDIATO, junto ao SLA", bonus_itens),
    ]
    if r["sub"]:
        acoes += [("4. Localização: fora das capitais", "60 dias",
                   [f"Priorizar resposta de chamados e ativação de notificações nas cidades fora das capitais ({pct(r['int_pct'])} contra "
                    f"{pct(r['cap_pct'])} de churn). Investigar o mecanismo antes de agir (fora de capital é um recorte grosseiro)."]),
                  ("5. Dados e qualidade", "15 dias",
                   ["Pedir à PixPay os meses anteriores a abril e a definição do 8%.",
                    f"Decidir o tratamento de {br(r['semtr_n'], 0)} transações ausentes e {br(r['tickets_extremos'], 0)} tickets extremos; "
                    "corrigir 3 cidades digitadas errado (Fortleza, Belo Horizote)."])]
    elif r["completo"]:
        acoes.append(("4. Dados que faltam", "15 dias",
                      ["Pedir à PixPay os meses anteriores a abril, para validar a subida de 3% para 8%, e a definição usada no cálculo dos 8%.",
                       f"Clientes com algum dos dois sinais: {br(r['algum_n'], 0)} ({pct(r['algum_n'] / r['n'] * 100, 1)} da base) e "
                       f"{br(r['algum_c'], 0)} cancelamentos; cerca de {br(r['excesso'], 0)} acima do esperado sem sinal. Isso é associação, "
                       "não evitável comprovado."]))
    for tit, prazo, itens in acoes:
        estilo = ParagraphStyle("m", fontName="Helvetica", fontSize=10.5, leading=13.5)
        alturas = [Paragraph("• " + it, estilo).wrap(W - 2 * M - 28, 1000)[1] + 3 for it in itens]
        h = 36 + sum(alturas) + 8
        cv.setFillColor(CINZA_CLARO)
        cv.roundRect(M, y - h, W - 2 * M, h, 6, stroke=0, fill=1)
        cv.setFillColor(AZUL)
        cv.setFont("Helvetica-Bold", 12)
        cv.drawString(M + 12, y - 20, tit)
        cv.setFillColor(VERMELHO)
        cv.setFont("Helvetica-Bold", 10)
        cv.drawRightString(W - M - 12, y - 20, "Prazo: " + prazo)
        yy = y - 32
        for it, hh in zip(itens, alturas):
            para(cv, "• " + it, M + 14, yy, W - 2 * M - 28, tam=10.5, leading=13.5)
            yy -= hh
        y -= h + 12
    y -= 8
    # perguntas em aberto
    para(cv, "<b>Perguntas em aberto para a PixPay (podem mudar as conclusões):</b> como o 8% foi calculado; o que "
             "notificacoes_7d mede e em qual janela; se o chamado lento ocorreu antes ou depois da decisão de cancelar; "
             "se as regras de 24 h e de 2 notificações existem no sistema; se transação ausente significa zero; origem de "
             "677 tickets acima de R$ 10.000,00; se os dados são reais (99% dos CPFs falham no dígito verificador).",
         M, y, W - 2 * M, tam=9.5, cor=colors.black, leading=12.5)
    rodape(cv, f"Prazos são proposta do analista, não dado. Associação não é causa; apenas abril/2026 foi observado. "
               f"Mensalidade perdida em abril: R$ {br(r['mens_perdida'])} (só mensalidade, sem receita de transações). "
               f"Analista: {ANALISTA} | {DATA_RELATORIO} | Fonte: data/clientes_pixpay_limpo.csv.")


def gerar(destino=None, completo=False, subagentes=False):
    """Gera o PDF e retorna o dict de números usado.
    completo=False: versão com os dados informados no pedido (relatório original).
    completo=True: acrescenta seções extraídas de DESCOBERTAS_ANALISE_CHURN.md e dos documentos de auditoria."""
    r = calcular()
    destino = destino or proximo_nome_livre()
    r["completo"] = completo or subagentes
    r["sub"] = subagentes
    destino.parent.mkdir(parents=True, exist_ok=True)
    cv = canvas.Canvas(str(destino), pagesize=A4)
    cv.setTitle("Relatório executivo PixPay - Análise de churn")
    cv.setAuthor(ANALISTA)
    for fn in (pagina1, pagina2, pagina3):
        fn(cv, r)
        cv.showPage()
    cv.save()
    return r, destino


if __name__ == "__main__":
    # Uso: python scripts/gerar_relatorio_executivo.py [auditoria|subagentes]   (padrão: subagentes)
    # Nunca sobrescreve: se o arquivo existir, grava com sufixo incremental (relatorio_executivo_pixpay_1.pdf, _2, ...).
    versao = sys.argv[1] if len(sys.argv) > 1 else "subagentes"
    numeros, caminho = gerar(completo=(versao == "auditoria"), subagentes=(versao == "subagentes"))
    print({k: (round(v, 2) if isinstance(v, float) else v) for k, v in numeros.items() if k not in ("ic", "prem_aj_ic", "cap_aj_ic")})
    print("PDF salvo em:", caminho)
