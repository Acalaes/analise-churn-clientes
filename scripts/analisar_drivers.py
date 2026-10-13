"""Análise de drivers de churn da PixPay, sobre data/clientes_pixpay_limpo.csv (somente leitura).

Passo 1 — validar a premissa do briefing (churn real vs. 8%).
Passo 2 — analisar drivers por categoria (contextual, comportamental, demográfica).
Passo 3 — ranking dos drivers por magnitude do efeito (Cramér's V, risco relativo, excesso de cancelamentos).
Passo 4 — combinação dos top drivers (cruzamento, interação aditiva/multiplicativa, efeito ajustado).

Uso (a partir da raiz do projeto):  python scripts/analisar_drivers.py
Funções retornam DataFrame/dict; só o bloco __main__ imprime.
"""
from pathlib import Path
from statistics import NormalDist  # biblioteca padrão: inversa da normal p/ IC com Bonferroni, sem scipy

import numpy as np
import pandas as pd

from investigar_transacoes import carregar_limpo, teste_permutacao  # carga validada (10.000 x 15) e teste por permutação

RAIZ = Path(__file__).resolve().parent.parent
BRIEFING_CHURN = 0.08  # churn mensal que a diretoria reportou (CLAUDE.md)
INICIO_JANELA = pd.Timestamp("2026-04-01")


def wilson(k, n, z=1.96):
    """Intervalo de confiança de Wilson (95%) para uma proporção k/n. Retorna (inferior, superior)."""
    p = k / n
    centro = (p + z ** 2 / (2 * n)) / (1 + z ** 2 / n)
    meia = z * np.sqrt(p * (1 - p) / n + z ** 2 / (4 * n ** 2)) / (1 + z ** 2 / n)
    return centro - meia, centro + meia


def churn_por_denominador(df):
    """Churn de abril/2026 sob cada denominador plausível, com IC 95% e distância até os 8% do briefing.

    Decisão: como NENHUM cancelamento ocorre antes de 01/04/2026, 'cadastrados antes de abril' e
    'ativos no início do mês' são o mesmo conjunto; ambos aparecem para deixar isso explícito.
    """
    cancelou = df["churn_30d"]
    antes_abril = df["data_cadastro"] < INICIO_JANELA
    ativo_inicio = antes_abril & (df["data_cancelamento"].isna() | (df["data_cancelamento"] >= INICIO_JANELA))
    cenarios = {
        "Base total (todas as linhas)": pd.Series(True, index=df.index),
        "Cadastrados antes de 01/04/2026": antes_abril,
        "Ativos em 01/04/2026 (início do mês)": ativo_inicio,
    }
    linhas = []
    for nome, mascara in cenarios.items():
        n, k = int(mascara.sum()), int(cancelou[mascara].sum())
        lo, hi = wilson(k, n)
        linhas.append({"denominador": nome, "clientes": n, "cancelaram": k, "churn_%": round(k / n * 100, 2),
                       "ic95_inferior_%": round(lo * 100, 2), "ic95_superior_%": round(hi * 100, 2),
                       "diferenca_vs_8%_pp": round(k / n * 100 - BRIEFING_CHURN * 100, 2)})
    return pd.DataFrame(linhas)


def cobertura_temporal(df):
    """O que o dataset consegue (ou não) dizer sobre tendência: janela de cadastro e de cancelamento."""
    canc = df["data_cancelamento"].dropna()
    return {
        "cadastro_min": df["data_cadastro"].min().strftime("%d/%m/%Y"),
        "cadastro_max": df["data_cadastro"].max().strftime("%d/%m/%Y"),
        "cancelamento_min": canc.min().strftime("%d/%m/%Y"),
        "cancelamento_max": canc.max().strftime("%d/%m/%Y"),
        "meses_distintos_com_cancelamento": int(canc.dt.to_period("M").nunique()),
        "cancelamentos_total": int(len(canc)),
        "cancelamentos_antes_de_01/04/2026": int((canc < INICIO_JANELA).sum()),
        "cadastros_em_ou_apos_01/04/2026": int((df["data_cadastro"] >= INICIO_JANELA).sum()),
        "cancelaram_e_cadastrados_em_ou_apos_01/04": int(((df["data_cadastro"] >= INICIO_JANELA) & df["churn_30d"]).sum()),
    }


def cancelamentos_por_dia(df):
    """Cancelamentos por dia de abril, acumulado e % acumulado sobre a base total."""
    d = df["data_cancelamento"].dropna().value_counts().sort_index().rename("cancelamentos").to_frame()
    d["acumulado"] = d["cancelamentos"].cumsum()
    d["churn_acumulado_%"] = (d["acumulado"] / len(df) * 100).round(2)
    d.index = d.index.strftime("%d/%m/%Y")
    return d.rename_axis("data")


def engenharia_reversa_8pct(df):
    """Que número faria o churn ser 8%? Útil para perguntar à diretoria como o 8% foi calculado."""
    n = len(df)
    cancel = int(df["churn_30d"].sum())
    por_dia = df["data_cancelamento"].dropna().value_counts().sort_index().cumsum()
    meta = BRIEFING_CHURN * n
    dia_800 = por_dia[por_dia >= meta].index[0]
    return {
        "cancelamentos_necessarios_para_8%_da_base": int(round(meta)),
        "cancelamentos_observados": cancel,
        "excesso_vs_8%": cancel - int(round(meta)),
        "base_necessaria_para_8%_com_1353_cancelamentos": int(round(cancel / BRIEFING_CHURN)),
        "dia_de_abril_em_que_o_acumulado_chega_a_8%": dia_800.strftime("%d/%m/%Y"),
    }


def grafico_churn_acumulado(df):
    """Churn acumulado ao longo de abril/2026 vs. a linha de 8% do briefing. Retorna a figura (não salva)."""
    import matplotlib.pyplot as plt  # import local: só quem pede o gráfico paga o custo

    d = df["data_cancelamento"].dropna().value_counts().sort_index().cumsum() / len(df) * 100
    fig, ax = plt.subplots(figsize=(9, 4.2))
    ax.plot(d.index, d.values, color="#c0392b", linewidth=2.5, label="Churn acumulado observado")
    ax.axhline(BRIEFING_CHURN * 100, color="#555555", linestyle="--", linewidth=1.5, label="8% reportado no briefing")
    ax.annotate(f"{d.iloc[-1]:.2f}%", (d.index[-1], d.iloc[-1]), textcoords="offset points", xytext=(-8, 8),
                ha="right", fontweight="bold", color="#c0392b")
    dia8 = d[d >= BRIEFING_CHURN * 100].index[0]
    ax.annotate(f"passa de 8% em {dia8:%d/%m/%Y}", (dia8, BRIEFING_CHURN * 100), textcoords="offset points",
                xytext=(10, -22), color="#555555")
    ax.set_title("Churn acumulado em abril/2026 (sobre 10.000 clientes)")
    ax.set_ylabel("% da base que cancelou")
    ax.set_xlabel("")
    ax.set_ylim(0, 15)
    ax.xaxis.set_major_formatter(plt.matplotlib.dates.DateFormatter("%d/%m"))
    ax.grid(axis="y", alpha=0.3)
    ax.legend(loc="upper left", frameon=False)
    fig.tight_layout()
    return fig


def validar_premissa(df):
    """Reúne todas as evidências do Passo 1."""
    return {
        "denominadores": churn_por_denominador(df),
        "cobertura": cobertura_temporal(df),
        "por_dia": cancelamentos_por_dia(df),
        "reversa": engenharia_reversa_8pct(df),
    }


# ============================================================== PASSO 2 — drivers por categoria
N_MIN_GRUPO = 50          # grupos menores são agrupados (não descartados): IC largo e qui-quadrado instável
N_PERMUTACOES = 5000
SEMENTE = 0
ROTULO_AGRUPADO = "(grupos pequenos agrupados)"


def _rotular_quartis(s, inteiro):
    """Quartis com rótulo legível. Inteiro: 'Q1 (1–18)'; decimal: 'Q1 (0.5–9.0 h)'. Retorna (Series de rótulos, lista na ordem)."""
    _, bordas = pd.qcut(s, 4, retbins=True, duplicates="drop")
    rotulos = []
    for i in range(len(bordas) - 1):
        lo, hi = bordas[i], bordas[i + 1]
        if inteiro:
            lo = int(lo) if i == 0 else int(lo) + 1  # intervalos são (a, b]: o piso real é a+1
            rotulos.append(f"Q{i + 1} ({lo}–{int(hi)})")
        else:
            rotulos.append(f"Q{i + 1} ({lo:.1f}–{hi:.1f} h)")
    return pd.Series(pd.qcut(s, 4, labels=rotulos, duplicates="drop"), index=s.index).astype(str), rotulos


def definir_variaveis(df, referencia=INICIO_JANELA):
    """Variáveis do Passo 2: dict nome -> {categoria, grupo (Series por cliente, só a população analisada), ordem, nota}.

    Decisões:
    - tempo_resposta: só entre quem abriu chamado (n = 2.524); para os demais ele não existe.
    - transacoes_30d: 'ausente' e '0' ficam SEPARADOS (decisão sobre o preenchimento ainda em aberto; nada é alterado).
    - tempo de casa: dias entre o cadastro e 01/04/2026 (início da janela), igual para todos. Usar a data de
      cancelamento como fim vazaria o desfecho para a variável.
    """
    v = {}
    v["abriu_chamado"] = {"categoria": "Contextual", "grupo": df["abriu_chamado"].map({True: "abriu chamado", False: "não abriu"}),
                          "ordem": ["não abriu", "abriu chamado"], "nota": "população: 10.000"}
    chamados = df[df["abriu_chamado"]]
    q, ordem_q = _rotular_quartis(chamados["tempo_resposta_chamado_h"], inteiro=False)
    v["tempo_resposta_quartis"] = {"categoria": "Contextual", "grupo": q, "ordem": ordem_q,
                                   "nota": "população: só quem abriu chamado (n = 2.524)"}
    faixas = ["até 24 h", "24–48 h", "48–72 h", "mais de 72 h"]
    sla = pd.cut(chamados["tempo_resposta_chamado_h"], [0, 24, 48, 72, np.inf], labels=faixas, right=True).astype(str)
    v["tempo_resposta_faixa_sla"] = {"categoria": "Contextual", "grupo": sla, "ordem": faixas,
                                     "nota": "população: só quem abriu chamado; faixas de SLA em horas"}
    v["notificacoes_7d"] = {"categoria": "Comportamental", "grupo": df["notificacoes_7d"].astype(int).map(lambda x: f"{x:02d}"),
                            "ordem": [f"{i:02d}" for i in range(13)], "nota": "população: 10.000"}
    tr = df["transacoes_30d"]
    pos, ordem_t = _rotular_quartis(tr[tr > 0], inteiro=True)
    grupo_t = pd.Series("ausente (em branco)", index=df.index)
    grupo_t[tr == 0] = "0 transações"
    grupo_t.loc[pos.index] = pos
    v["transacoes_30d"] = {"categoria": "Comportamental", "grupo": grupo_t,
                           "ordem": ["ausente (em branco)", "0 transações"] + ordem_t,
                           "nota": "população: 10.000; ausente e 0 separados"}
    v["plano"] = {"categoria": "Demográfica", "grupo": df["plano"], "ordem": ["Básico", "Premium"], "nota": "população: 10.000"}
    v["estado"] = {"categoria": "Demográfica", "grupo": df["estado"], "ordem": None, "nota": "população: 10.000; 23 UFs"}
    v["cidade"] = {"categoria": "Demográfica", "grupo": df["cidade"], "ordem": None, "nota": "população: 10.000; 60 cidades"}
    dias = (referencia - df["data_cadastro"]).dt.days
    tc, ordem_tc = _rotular_quartis(dias, inteiro=True)
    v["tempo_de_casa_dias"] = {"categoria": "Controle", "grupo": tc, "ordem": ordem_tc,
                               "nota": "dias de cadastro até 01/04/2026"}
    return v


def _agrupar_pequenos(grupo, n_min=N_MIN_GRUPO):
    """Reúne grupos com n < n_min em ROTULO_AGRUPADO (nenhum cliente é descartado)."""
    return grupo.where(grupo.map(grupo.value_counts()) >= n_min, ROTULO_AGRUPADO)


def tabela_por_grupo(grupo, churn, ordem=None):
    """Churn por grupo com IC 95% de Wilson e diferença para a média da POPULAÇÃO analisada."""
    g = _agrupar_pequenos(grupo)
    t = churn.groupby(g).agg(clientes="size", cancelaram="sum")
    media = churn.mean() * 100
    t["churn_%"] = (t["cancelaram"] / t["clientes"] * 100).round(2)
    ic = [wilson(k, n) for k, n in zip(t["cancelaram"], t["clientes"])]
    t["ic95_inf_%"] = [round(a * 100, 2) for a, _ in ic]
    t["ic95_sup_%"] = [round(b * 100, 2) for _, b in ic]
    t["dif_vs_media_pp"] = (t["churn_%"] - media).round(2)
    t["ic_exclui_a_media"] = (t["ic95_inf_%"] > media) | (t["ic95_sup_%"] < media)
    assert t["clientes"].sum() == len(grupo) and t["cancelaram"].sum() == churn.sum(), "reconciliação falhou"
    if ordem:
        t = t.reindex([o for o in ordem if o in t.index] + [i for i in t.index if i not in ordem])
    else:
        t = t.sort_values("churn_%", ascending=False)
    return t.rename_axis("grupo")


def analisar_variavel(df, v, n_perm=N_PERMUTACOES):
    """Tabela por grupo + teste de permutação global (qui-quadrado de churn x grupos) para uma variável."""
    churn = df.loc[v["grupo"].index, "churn_30d"]
    tabela = tabela_por_grupo(v["grupo"], churn, ordem=v["ordem"])
    teste = teste_permutacao(_agrupar_pequenos(v["grupo"]), churn, n_perm=n_perm, semente=SEMENTE)
    return {"tabela": tabela, "teste": teste, "churn_populacao_%": round(churn.mean() * 100, 2), "n": len(churn)}


def analisar_drivers(df):
    """Executa o Passo 2 inteiro. Retorna dict com 'resumo', 'variaveis', 'definicoes' e 'limite_bonferroni'."""
    defs = definir_variaveis(df)
    res = {nome: analisar_variavel(df, v) for nome, v in defs.items()}
    linhas = []
    for nome, r in res.items():
        t = r["tabela"]
        ok = t[t.index != ROTULO_AGRUPADO]
        linhas.append({"categoria": defs[nome]["categoria"], "variavel": nome, "n": r["n"],
                       "churn_pop_%": r["churn_populacao_%"], "grupos": len(ok),
                       "churn_min_%": ok["churn_%"].min(), "churn_max_%": ok["churn_%"].max(),
                       "amplitude_pp": round(ok["churn_%"].max() - ok["churn_%"].min(), 2),
                       "qui2": r["teste"]["qui2"], "p_permutacao": round(r["teste"]["p_permutacao"], 4)})
    resumo = pd.DataFrame(linhas)
    limite = 0.05 / len(resumo)
    resumo["significativo_bonferroni"] = resumo["p_permutacao"] < limite
    return {"resumo": resumo, "variaveis": res, "definicoes": defs, "limite_bonferroni": round(limite, 4)}


def graficos_passo2(resultado):
    """Duas figuras: variáveis ordinais/binárias (grade) e geografia (estado e cidade).
    Vermelho = IC95% acima da média, azul = abaixo, cinza = contém a média. Tracejado = churn médio da população."""
    import matplotlib.pyplot as plt

    def cor(row, media):
        return "#c0392b" if row["ic95_inf_%"] > media else ("#2e6da4" if row["ic95_sup_%"] < media else "#9a9a9a")

    def barras(ax, nome, horizontal=False):
        r = resultado["variaveis"][nome]
        t, media = r["tabela"], r["churn_populacao_%"]
        t = t[t.index != ROTULO_AGRUPADO]  # só no gráfico: 3 clientes dão IC enorme e achatam o eixo; a tabela os mantém
        cores = [cor(row, media) for _, row in t.iterrows()]
        err = [t["churn_%"] - t["ic95_inf_%"], t["ic95_sup_%"] - t["churn_%"]]
        pos = np.arange(len(t))
        if horizontal:
            ax.barh(pos, t["churn_%"], xerr=err, color=cores, capsize=2, error_kw={"linewidth": 0.8})
            ax.set_yticks(pos, t.index, fontsize=7)
            ax.invert_yaxis()
            ax.axvline(media, color="#333333", linestyle="--", linewidth=1)
            ax.set_xlabel("churn %")
        else:
            ax.bar(pos, t["churn_%"], yerr=err, color=cores, capsize=3, error_kw={"linewidth": 0.8})
            ax.set_xticks(pos, t.index, rotation=30, ha="right", fontsize=8)
            ax.axhline(media, color="#333333", linestyle="--", linewidth=1)
            ax.set_ylabel("churn %")
            for x, val in zip(pos, t["churn_%"]):
                ax.text(x, val + 0.2, f"{val:.1f}", ha="center", fontsize=7, fontweight="bold")
        p = r["teste"]["p_permutacao"]
        ptxt = "p < 0.001" if p < 0.001 else f"p = {p:.3f}"
        ax.set_title(f"{nome}\n(média {media:.2f}% | {ptxt})", fontsize=9)

    nomes = ["abriu_chamado", "tempo_resposta_quartis", "tempo_resposta_faixa_sla", "notificacoes_7d",
             "transacoes_30d", "plano", "tempo_de_casa_dias"]
    fig1, eixos = plt.subplots(3, 3, figsize=(15, 11))
    for ax, nome in zip(eixos.ravel(), nomes):
        barras(ax, nome)
    for ax in eixos.ravel()[len(nomes):]:
        ax.axis("off")
    eixos.ravel()[-1].text(0.0, 0.5, "vermelho = IC95% acima da média\nazul = IC95% abaixo da média\ncinza = IC contém a média\n"
                           "linha tracejada = churn médio da população\n(descritivo, sem correção de múltiplos testes)",
                           fontsize=9, va="center")
    fig1.suptitle("Passo 2 — churn por grupo, com IC 95%", fontsize=13)
    fig1.tight_layout()

    fig2, (a, b) = plt.subplots(1, 2, figsize=(13, 11))
    barras(a, "estado", horizontal=True)
    barras(b, "cidade", horizontal=True)
    fig2.suptitle("Passo 2 — churn por estado e cidade, com IC 95%", fontsize=13)
    fig2.tight_layout()
    return fig1, fig2


# ============================================================== PASSO 3 — ranking por magnitude do efeito
def cramers_v(qui2, n, k):
    """Cramér's V para tabela 2 x k (churn x grupos): bruto e com correção de viés (Bergsma).

    O V bruto cresce artificialmente com o número de grupos (cidade tem 59); o corrigido desconta isso."""
    phi2 = qui2 / n
    phi2_corr = max(0.0, phi2 - (k - 1) / (n - 1))
    k_til = k - (k - 1) ** 2 / (n - 1)
    r_til = 2 - 1 / (n - 1)
    return float(np.sqrt(phi2)), float(np.sqrt(phi2_corr / min(k_til - 1, r_til - 1)))


def ranking_variaveis(p2):
    """Ordena as variáveis pelo Cramér's V corrigido. Retorna DataFrame.

    Atenção: tempo_resposta_* usa só quem abriu chamado (n = 2.524); V é uma medida de associação dentro da
    população analisada, então variáveis de populações diferentes são comparáveis só de forma aproximada."""
    linhas = []
    for _, r in p2["resumo"].iterrows():
        k = len(p2["variaveis"][r["variavel"]]["tabela"])
        v_bruto, v_corr = cramers_v(r["qui2"], r["n"], k)
        forca = "forte" if v_corr >= 0.30 else "média" if v_corr >= 0.15 else "pequena" if v_corr >= 0.05 else "desprezível"
        linhas.append({"variavel": r["variavel"], "categoria": r["categoria"], "n": int(r["n"]), "grupos": k,
                       "cramers_v_bruto": round(v_bruto, 3), "cramers_v_corrigido": round(v_corr, 3),
                       "efeito": forca, "p_permutacao": r["p_permutacao"],
                       "significativo_bonferroni": bool(r["significativo_bonferroni"])})
    return pd.DataFrame(linhas).sort_values("cramers_v_corrigido", ascending=False).reset_index(drop=True)


def ranking_grupos(df, p2):
    """Todos os grupos das variáveis significativas, ordenados por |diferença| vs. a média da BASE INTEIRA.

    Decisão: linha de base única (churn da base toda) para que grupos de variáveis diferentes sejam comparáveis.
    'robusto' = IC de Wilson, com z corrigido por Bonferroni para o nº total de grupos, exclui a média da base.
    excesso = cancelamentos observados - clientes x churn médio (tamanho do efeito em cancelamentos; NÃO é aditivo
    entre variáveis, pois os mesmos clientes aparecem em vários grupos)."""
    base = df["churn_30d"].mean()
    rel = [v for v, ok in zip(p2["resumo"]["variavel"], p2["resumo"]["significativo_bonferroni"]) if ok]
    partes = []
    for nome in rel:
        t = p2["variaveis"][nome]["tabela"]
        t = t[t.index != ROTULO_AGRUPADO].reset_index()
        t.insert(0, "variavel", nome)
        partes.append(t[["variavel", "grupo", "clientes", "cancelaram"]])
    g = pd.concat(partes, ignore_index=True)
    z = NormalDist().inv_cdf(1 - 0.05 / len(g) / 2)
    g["churn_%"] = (g["cancelaram"] / g["clientes"] * 100).round(2)
    ic = [wilson(k, n, z) for k, n in zip(g["cancelaram"], g["clientes"])]
    g["ic_inf_%"] = [round(a * 100, 2) for a, _ in ic]
    g["ic_sup_%"] = [round(b * 100, 2) for _, b in ic]
    g["dif_vs_base_pp"] = (g["churn_%"] - base * 100).round(2)
    g["risco_relativo"] = ((g["cancelaram"] / g["clientes"]) / base).round(2)
    g["excesso_cancelamentos"] = (g["cancelaram"] - g["clientes"] * base).round(0).astype(int)
    g["robusto"] = (g["ic_inf_%"] > base * 100) | (g["ic_sup_%"] < base * 100)
    g.attrs["z_bonferroni"] = round(z, 2)
    g.attrs["n_comparacoes"] = len(g)
    g.attrs["base_%"] = round(base * 100, 2)
    return g.reindex(g["dif_vs_base_pp"].abs().sort_values(ascending=False).index).reset_index(drop=True)


def risco_relativo_com_ic(a, n1, b, n0, z=1.96):
    """RR = (a/n1)/(b/n0) com IC 95% (método do log) e diferença de risco em p.p. (Wald)."""
    p1, p0 = a / n1, b / n0
    rr = p1 / p0
    ep = np.sqrt(1 / a - 1 / n1 + 1 / b - 1 / n0)
    dp = np.sqrt(p1 * (1 - p1) / n1 + p0 * (1 - p0) / n0)
    return {"churn_exposto_%": round(p1 * 100, 2), "churn_referencia_%": round(p0 * 100, 2),
            "risco_relativo": round(rr, 2), "rr_ic95": f"{np.exp(np.log(rr) - z * ep):.2f} a {np.exp(np.log(rr) + z * ep):.2f}",
            "dif_pp": round((p1 - p0) * 100, 2), "dif_ic95_pp": f"{(p1 - p0 - z * dp) * 100:.2f} a {(p1 - p0 + z * dp) * 100:.2f}"}


def contrastes_binarios(df):
    """Contrastes de 2 grupos, cada um com RR e diferença de risco com IC 95%.

    Os limiares (24 h de SLA; 0-1 notificação) foram escolhidos olhando o Passo 2: o de 24 h coincide com um SLA
    típico de suporte; o de notificações é o ponto em que a curva dá o degrau. O IC não desconta essa escolha,
    então o efeito real tende a ser um pouco menor que o estimado."""
    c = df["churn_30d"]
    cham = df["abriu_chamado"]
    lento = cham & (df["tempo_resposta_chamado_h"] > 24)
    rapido = cham & (df["tempo_resposta_chamado_h"] <= 24)
    baixo = df["notificacoes_7d"] <= 1
    casos = [
        ("Chamado > 24 h vs. chamado <= 24 h (só quem abriu)", lento, rapido),
        ("Chamado > 24 h vs. resto da base", lento, ~lento),
        ("Notificações 0-1 vs. 2 ou mais", baixo, ~baixo),
        ("Abriu chamado vs. não abriu", cham, ~cham),
        ("Chamado <= 24 h vs. não abriu chamado", rapido, ~cham),
        ("Premium vs. Básico", df["plano"] == "Premium", df["plano"] == "Básico"),
    ]
    linhas = []
    for nome, exp, ref in casos:
        r = risco_relativo_com_ic(int(c[exp].sum()), int(exp.sum()), int(c[ref].sum()), int(ref.sum()))
        linhas.append({"contraste": nome, "n_exposto": int(exp.sum()), "n_referencia": int(ref.sum()), **r})
    return pd.DataFrame(linhas)


def grafico_passo3(rank_var, rank_grp, n_top=15):
    """Esquerda: Cramér's V corrigido por variável. Direita: os n_top grupos robustos de maior efeito (IC corrigido)."""
    import matplotlib.pyplot as plt

    fig, (a, b) = plt.subplots(1, 2, figsize=(15, 6.5), gridspec_kw={"width_ratios": [1, 1.3]})
    rv = rank_var.iloc[::-1]
    cores = ["#c0392b" if s else "#9a9a9a" for s in rv["significativo_bonferroni"]]
    a.barh(rv["variavel"], rv["cramers_v_corrigido"], color=cores)
    for y, (v, vb) in enumerate(zip(rv["cramers_v_corrigido"], rv["cramers_v_bruto"])):
        a.text(max(v, vb) + 0.008, y, f"{v:.3f}", va="center", fontsize=8, fontweight="bold")
        a.plot(vb, y, "|", color="#333333", markersize=12)
    a.set_xlabel("Cramér's V corrigido (traço preto = V bruto)")
    a.set_title("Força da associação com o churn, por variável\n(cinza = não significativo após Bonferroni)", fontsize=10)

    top = rank_grp[rank_grp["robusto"]].head(n_top).iloc[::-1]
    base = rank_grp.attrs["base_%"]
    rotulo = [f"{v} = {g}" for v, g in zip(top["variavel"], top["grupo"])]
    cor = ["#c0392b" if d > 0 else "#2e6da4" for d in top["dif_vs_base_pp"]]
    err = [top["churn_%"] - top["ic_inf_%"], top["ic_sup_%"] - top["churn_%"]]
    b.barh(rotulo, top["churn_%"], xerr=err, color=cor, capsize=2, error_kw={"linewidth": 0.8})
    b.axvline(base, color="#333333", linestyle="--", linewidth=1)
    for y, (c_, hi_, n_) in enumerate(zip(top["churn_%"], top["ic_sup_%"], top["clientes"])):
        b.text(hi_ + 1, y, f"{c_:.1f}%  (n={n_})", va="center", fontsize=7)  # depois do IC, para não sobrepor
    b.set_xlim(0, top["ic_sup_%"].max() + 14)
    b.set_xlabel(f"churn %   (tracejado = média da base, {base:.2f}%)")
    b.set_title(f"Os {n_top} grupos de maior efeito (IC 95% com Bonferroni, z = {rank_grp.attrs['z_bonferroni']})", fontsize=10)
    fig.tight_layout()
    return fig


# ============================================================== PASSO 4 — combinação dos top drivers
N_BOOTSTRAP = 5000


def sinais_de_risco(df):
    """Os dois sinais de maior efeito no Passo 3. Retorna (baixo_engajamento, chamado_lento), ambos bool.

    baixo_engajamento: 0 ou 1 notificação nos últimos 7 dias.
    chamado_lento: abriu chamado e o tempo de resposta passou de 24 h (limiar escolhido no Passo 3)."""
    baixo = df["notificacoes_7d"] <= 1
    lento = df["abriu_chamado"] & (df["tempo_resposta_chamado_h"] > 24)
    return baixo, lento


def situacao_chamado(df):
    """Três estados: não abriu / resolvido em até 24 h / acima de 24 h. (NaN em tempo_resposta só ocorre em 'não abriu'.)"""
    return pd.Series(np.select([~df["abriu_chamado"], df["tempo_resposta_chamado_h"] <= 24],
                               ["não abriu chamado", "chamado ≤ 24 h"], default="chamado > 24 h"), index=df.index)


def tabela_cruzada(df, linha, coluna):
    """Churn por célula (linha x coluna) em formato longo, com IC 95% de Wilson e participação na base e nos cancelamentos."""
    c = df["churn_30d"]
    t = c.groupby([linha.rename("linha"), coluna.rename("coluna")]).agg(clientes="size", cancelaram="sum").reset_index()
    t["churn_%"] = (t["cancelaram"] / t["clientes"] * 100).round(2)
    ic = [wilson(k, n) for k, n in zip(t["cancelaram"], t["clientes"])]
    t["ic95_inf_%"] = [round(a * 100, 2) for a, _ in ic]
    t["ic95_sup_%"] = [round(b * 100, 2) for _, b in ic]
    t["%_da_base"] = (t["clientes"] / len(df) * 100).round(1)
    t["%_dos_cancelamentos"] = (t["cancelaram"] / c.sum() * 100).round(1)
    t["n_suficiente"] = t["clientes"] >= N_MIN_GRUPO
    return t


def segmentos_risco(df):
    """Quatro segmentos pelos dois sinais: nenhum, só baixo engajamento, só chamado lento, os dois."""
    baixo, lento = sinais_de_risco(df)
    rot = np.select([~baixo & ~lento, baixo & ~lento, ~baixo & lento], ["nenhum sinal", "só notificações 0-1", "só chamado > 24 h"],
                    default="os dois sinais")
    seg = pd.Series(rot, index=df.index)
    t = tabela_cruzada(df, seg, pd.Series("todos", index=df.index)).drop(columns="coluna").rename(columns={"linha": "segmento"})
    ordem = ["nenhum sinal", "só notificações 0-1", "só chamado > 24 h", "os dois sinais"]
    return t.set_index("segmento").loc[ordem].reset_index()


def interacao(df, n_boot=N_BOOTSTRAP, semente=SEMENTE):
    """Os dois sinais se somam, se multiplicam ou se reforçam?

    Referência = 'nenhum sinal' (p00). Esperado se independentes:
      aditivo        = p_A + p_B - p00           (diferenças de risco se somam)
      multiplicativo = p_A * p_B / p00           (riscos relativos se multiplicam)
    Interação aditiva = observado(ambos) - esperado aditivo (p.p.). Razão multiplicativa = observado / esperado.
    IC 95% por bootstrap (reamostra clientes com reposição; semente fixa)."""
    baixo, lento = sinais_de_risco(df)
    cel = (baixo.astype(int) + 2 * lento.astype(int)).to_numpy()  # 0 nenhum, 1 só baixo, 2 só lento, 3 ambos
    y = df["churn_30d"].to_numpy().astype(float)

    def estatisticas(idx):
        n = np.bincount(cel[idx], minlength=4).astype(float)
        k = np.bincount(cel[idx], weights=y[idx], minlength=4)
        p = k / n
        add = p[3] - (p[1] + p[2] - p[0])
        mult = p[3] / (p[1] * p[2] / p[0])
        return p, add, mult

    p, add, mult = estatisticas(np.arange(len(df)))
    rng = np.random.default_rng(semente)
    boot = [estatisticas(rng.integers(0, len(df), len(df)))[1:] for _ in range(n_boot)]
    add_b, mult_b = np.array(boot).T
    return {
        "churn_nenhum_%": round(p[0] * 100, 2), "churn_so_baixo_%": round(p[1] * 100, 2),
        "churn_so_lento_%": round(p[2] * 100, 2), "churn_ambos_observado_%": round(p[3] * 100, 2),
        "esperado_aditivo_%": round((p[1] + p[2] - p[0]) * 100, 2),
        "esperado_multiplicativo_%": round(p[1] * p[2] / p[0] * 100, 2),
        "interacao_aditiva_pp": round(add * 100, 2),
        "interacao_aditiva_ic95_pp": f"{np.percentile(add_b, 2.5) * 100:.2f} a {np.percentile(add_b, 97.5) * 100:.2f}",
        "razao_multiplicativa": round(mult, 3),
        "razao_multiplicativa_ic95": f"{np.percentile(mult_b, 2.5):.3f} a {np.percentile(mult_b, 97.5):.3f}",
    }


def rr_mantel_haenszel(exposto, churn, estratos):
    """Risco relativo ajustado por estratos (Mantel-Haenszel) com IC 95% (Greenland-Robins), e o RR bruto para comparar."""
    d = pd.DataFrame({"e": exposto.astype(bool), "y": churn.astype(bool), "s": estratos})
    R = S = P = 0.0
    for _, g in d.groupby("s"):
        n1, n0 = int(g["e"].sum()), int((~g["e"]).sum())
        a1, a0 = int((g["e"] & g["y"]).sum()), int((~g["e"] & g["y"]).sum())
        N = n1 + n0
        if n1 == 0 or n0 == 0:
            continue
        R += a1 * n0 / N
        S += a0 * n1 / N
        P += (n1 * n0 * (a1 + a0) - a1 * a0 * N) / N ** 2
    rr = R / S
    ep = np.sqrt(P / (R * S))
    n1, n0 = int(d["e"].sum()), int((~d["e"]).sum())
    bruto = (d.loc[d["e"], "y"].mean()) / (d.loc[~d["e"], "y"].mean())
    return {"clientes_expostos": n1, "rr_bruto": round(bruto, 2), "rr_ajustado": round(rr, 2),
            "rr_ajustado_ic95": f"{np.exp(np.log(rr) - 1.96 * ep):.2f} a {np.exp(np.log(rr) + 1.96 * ep):.2f}"}


def efeito_ajustado(df):
    """Cada driver, com e sem ajuste pelo(s) outro(s). Se o RR ajustado ~ RR bruto, o efeito é próprio; se cai a ~1, era reflexo.

    Nos dois sinais principais, o ajuste é um pelo outro. Para plano e geografia, o ajuste é pelos 4 segmentos de risco."""
    baixo, lento = sinais_de_risco(df)
    c = df["churn_30d"]
    seg4 = baixo.astype(int) + 2 * lento.astype(int)
    casos = [
        ("Chamado > 24 h (ajustado por notificações 0-1)", lento, baixo),
        ("Notificações 0-1 (ajustado por chamado > 24 h)", baixo, lento),
        ("Premium (ajustado pelos 2 sinais)", df["plano"] == "Premium", seg4),
        ("Estado = CE (ajustado pelos 2 sinais)", df["estado"] == "CE", seg4),
        ("Cidade = Floriano (ajustado pelos 2 sinais)", df["cidade"] == "Floriano", seg4),
    ]
    return pd.DataFrame([{"driver": nome, **rr_mantel_haenszel(exp, c, est)} for nome, exp, est in casos])


def geografia_sem_sinais(df, n_perm=N_PERMUTACOES):
    """Plano, estado e cidade DENTRO do segmento 'nenhum sinal': sobrevivem quando os dois sinais principais estão ausentes?"""
    baixo, lento = sinais_de_risco(df)
    base = df[~baixo & ~lento]
    linhas = []
    for col in ("plano", "estado", "cidade"):
        t = teste_permutacao(_agrupar_pequenos(base[col]), base["churn_30d"], n_perm=n_perm, semente=SEMENTE)
        linhas.append({"variavel": col, "clientes_no_segmento": len(base), "churn_segmento_%": round(base["churn_30d"].mean() * 100, 2),
                       "qui2": t["qui2"], "p_permutacao": round(t["p_permutacao"], 4)})
    return pd.DataFrame(linhas)


def excesso_atribuivel(df):
    """Quantos cancelamentos há ACIMA do que ocorreria se todos tivessem o churn do segmento 'nenhum sinal'.

    É um cálculo de associação: só vira 'cancelamentos evitáveis' se os sinais forem causa (não sabemos)."""
    baixo, lento = sinais_de_risco(df)
    com_sinal = baixo | lento
    p00 = df.loc[~com_sinal, "churn_30d"].mean()
    canc_com_sinal = int(df.loc[com_sinal, "churn_30d"].sum())
    esperado = com_sinal.sum() * p00
    total = int(df["churn_30d"].sum())
    return {"clientes_com_algum_sinal": int(com_sinal.sum()), "%_da_base": round(com_sinal.mean() * 100, 1),
            "cancelamentos_com_algum_sinal": canc_com_sinal, "%_dos_cancelamentos": round(canc_com_sinal / total * 100, 1),
            "churn_sem_sinais_%": round(p00 * 100, 2), "cancelamentos_esperados_se_sem_sinais": round(esperado, 0),
            "excesso_de_cancelamentos": round(canc_com_sinal - esperado, 0),
            "excesso_%_do_total": round((canc_com_sinal - esperado) / total * 100, 1),
            "churn_da_base_se_todos_fossem_sem_sinais_%": round(p00 * 100, 2)}


def grafico_passo4(df, seg, inter):
    """Esquerda: mapa de calor chamado x notificações (churn % e n). Direita: 4 segmentos vs. esperado se independentes."""
    import matplotlib.pyplot as plt

    baixo, _ = sinais_de_risco(df)
    cruz = tabela_cruzada(df, situacao_chamado(df), baixo.map({True: "notificações 0–1", False: "notificações 2+"}))
    linhas = ["não abriu chamado", "chamado ≤ 24 h", "chamado > 24 h"]
    colunas = ["notificações 2+", "notificações 0–1"]
    mat = np.array([[cruz[(cruz["linha"] == r) & (cruz["coluna"] == c)]["churn_%"].iloc[0] for c in colunas] for r in linhas])
    ns = np.array([[cruz[(cruz["linha"] == r) & (cruz["coluna"] == c)]["clientes"].iloc[0] for c in colunas] for r in linhas])
    fig, (a, b) = plt.subplots(1, 2, figsize=(14, 5.2), gridspec_kw={"width_ratios": [1, 1.2]})
    im = a.imshow(mat, cmap="Reds", vmin=0, vmax=70)
    a.set_xticks(range(2), colunas)
    a.set_yticks(range(3), linhas)
    for i in range(3):
        for j in range(2):
            a.text(j, i, f"{mat[i, j]:.1f}%\nn = {ns[i, j]}", ha="center", va="center", fontsize=11, fontweight="bold",
                   color="white" if mat[i, j] > 40 else "black")
    a.set_title("Churn por situação do chamado × notificações")
    fig.colorbar(im, ax=a, fraction=0.04, label="churn %")

    cores = ["#9a9a9a", "#e08e3c", "#e08e3c", "#c0392b"]
    err = [seg["churn_%"] - seg["ic95_inf_%"], seg["ic95_sup_%"] - seg["churn_%"]]
    b.bar(seg["segmento"], seg["churn_%"], yerr=err, color=cores, capsize=4, error_kw={"linewidth": 1})
    for x, (v, n) in enumerate(zip(seg["churn_%"], seg["clientes"])):
        b.text(x, v + 4, f"{v:.1f}%\nn = {n}", ha="center", fontsize=9, fontweight="bold")
    x3 = 3
    b.plot([x3 - 0.4, x3 + 0.4], [inter["esperado_aditivo_%"]] * 2, color="#1f3a5f", linestyle="--", linewidth=2, label=f"esperado se somasse: {inter['esperado_aditivo_%']:.1f}%")
    b.plot([x3 - 0.4, x3 + 0.4], [inter["esperado_multiplicativo_%"]] * 2, color="#2e8b57", linestyle=":", linewidth=2.5, label=f"esperado se multiplicasse: {inter['esperado_multiplicativo_%']:.1f}%")
    b.set_ylabel("churn %")
    b.axhline(100, color="#999999", linewidth=0.8)
    b.text(-0.45, 101.5, "teto: 100%", fontsize=8, color="#777777")
    b.set_ylim(0, 125)  # o esperado multiplicativo passa de 100%: impossível, e é isso que o gráfico precisa mostrar
    b.set_title("Os dois sinais juntos: observado vs. esperado se fossem independentes")
    b.legend(loc="upper left", frameon=False, fontsize=9)
    plt.setp(b.get_xticklabels(), rotation=12, ha="right")
    fig.tight_layout()
    return fig


if __name__ == "__main__":
    dados = carregar_limpo()
    r = validar_premissa(dados)
    print(r["denominadores"].to_string(index=False), "\n")
    for k, v in r["cobertura"].items():
        print(f"{k}: {v}")
    print()
    for k, v in r["reversa"].items():
        print(f"{k}: {v}")
    print("\n", r["por_dia"].to_string())

    print("\n\n================ PASSO 2 ================")
    p2 = analisar_drivers(dados)
    print(p2["resumo"].to_string(index=False))
    print(f"\nLimite de Bonferroni ({len(p2['resumo'])} testes): p < {p2['limite_bonferroni']}\n")
    for nome, r in p2["variaveis"].items():
        if nome in ("estado", "cidade"):
            continue
        print(f"--- {nome}  [{p2['definicoes'][nome]['nota']}]\n{r['tabela'].to_string()}\n")

    print("\n\n================ PASSO 3 ================")
    rv = ranking_variaveis(p2)
    print(rv.to_string(index=False))
    rg = ranking_grupos(dados, p2)
    print(f"\nBase: {rg.attrs['base_%']}% | comparações: {rg.attrs['n_comparacoes']} | z Bonferroni: {rg.attrs['z_bonferroni']}")
    print(f"Grupos robustos: {int(rg['robusto'].sum())} de {len(rg)}\n")
    print(rg[rg["robusto"]].head(25).to_string(index=False))
    print("\n", contrastes_binarios(dados).to_string(index=False))

    print("\n\n================ PASSO 4 ================")
    seg = segmentos_risco(dados)
    print(seg.to_string(index=False))
    baixo_, _ = sinais_de_risco(dados)
    print("\n", tabela_cruzada(dados, situacao_chamado(dados), baixo_.map({True: "notif 0-1", False: "notif 2+"})).to_string(index=False))
    print("\nINTERAÇÃO")
    for k, v in interacao(dados).items():
        print(f"{k}: {v}")
    print("\n", efeito_ajustado(dados).to_string(index=False))
    print("\nDENTRO DE 'nenhum sinal'\n", geografia_sem_sinais(dados).to_string(index=False))
