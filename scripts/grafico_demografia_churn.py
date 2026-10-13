"""Gráfico de demografia x churn (plano, capital/interior e estado), no padrão da skill grafico-profissional.

Uso (a partir da raiz do projeto):  python scripts/grafico_demografia_churn.py
Lê data/clientes_pixpay_limpo.csv (somente leitura) e grava reports/graficosexecutados/grafico_demografia_churn.png.
"""
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

RAIZ = Path(__file__).resolve().parent.parent
AZUL, VERMELHO = "#1F4E79", "#C5221F"       # padrão PixPay: SÓ para Básico e Premium
BRANCO = dict(facecolor="white", edgecolor="none", pad=1.5)
CINZA, CINZA_ESCURO = "#9AA0A6", "#404040"  # categorias que não são plano (azul/vermelho já significam plano)
# Capitais presentes na base (23 das 27 UFs aparecem). Decisão: "Fortleza" (2) e "Belo Horizote" (1) são erros de
# digitação residuais de Fortaleza e Belo Horizonte (nenhum cancelou); contados como capital aqui sem alterar o CSV.
CAPITAIS = {"Aracaju", "Belo Horizonte", "Belo Horizote", "Belém", "Brasília", "Campo Grande", "Cuiabá", "Curitiba",
            "Florianópolis", "Fortaleza", "Fortleza", "Goiânia", "João Pessoa", "Maceió", "Manaus", "Natal", "Palmas",
            "Porto Alegre", "Recife", "Rio de Janeiro", "Salvador", "São Luís", "São Paulo", "Teresina", "Vitória"}


def pct_br(v):
    return f"{v:.2f}".replace(".", ",") + "%"


def int_br(v):
    return f"{int(v):,}".replace(",", ".")


def carregar(caminho=RAIZ / "data" / "clientes_pixpay_limpo.csv"):
    """Carrega o CSV limpo e valida tipos (churn_30d vem como texto)."""
    df = pd.read_csv(caminho, encoding="utf-8")
    df["churn_30d"] = df["churn_30d"].astype(str).str.lower().map({"true": True, "false": False})
    if df["churn_30d"].isna().any() or set(df["plano"].unique()) != {"Básico", "Premium"}:
        raise ValueError("Dados fora do esperado: confira churn_30d e plano.")
    df["local"] = df["cidade"].isin(CAPITAIS).map({True: "Capital", False: "Interior e demais"})
    return df


def tabela(df, coluna):
    """Clientes, cancelamentos e churn (%) por categoria de `coluna`."""
    g = df.groupby(coluna)["churn_30d"].agg(clientes="size", cancelaram="sum")
    g["churn_%"] = g["cancelaram"] / g["clientes"] * 100
    return g


def _limpar(ax):
    ax.grid(False)
    for lado in ("top", "right", "left", "bottom"):
        ax.spines[lado].set_visible(False)
    ax.set_facecolor("white")


def desenhar(df, destino=RAIZ / "reports" / "graficosexecutados" / "grafico_demografia_churn.png"):
    """Desenha os 3 painéis e salva; retorna o caminho."""
    media = df["churn_30d"].mean() * 100
    plano = tabela(df, "plano").loc[["Básico", "Premium"]]
    local = tabela(df, "local").loc[["Capital", "Interior e demais"]]
    uf = tabela(df, "estado").sort_values("churn_%")

    plt.rcParams["font.family"] = "sans-serif"
    plt.rcParams["font.sans-serif"] = ["Arial", "DejaVu Sans"]
    fig = plt.figure(figsize=(15, 9), facecolor="white")
    gs = fig.add_gridspec(2, 2, width_ratios=[1, 1.25], hspace=0.45, wspace=0.28)
    ax1, ax2, ax3 = fig.add_subplot(gs[0, 0]), fig.add_subplot(gs[1, 0]), fig.add_subplot(gs[:, 1])

    for ax, t, cores, titulo in ((ax1, plano, [AZUL, VERMELHO], "Por plano"),
                                 (ax2, local, [CINZA, CINZA_ESCURO], "Capital × interior")):
        barras = ax.bar(t.index, t["churn_%"], color=cores, width=0.55)
        for b, (_, r) in zip(barras, t.iterrows()):
            ax.text(b.get_x() + b.get_width() / 2, b.get_height() + 0.4, pct_br(r["churn_%"]), ha="center",
                    fontsize=12, fontweight="bold", bbox=BRANCO, zorder=5)
            ax.text(b.get_x() + b.get_width() / 2, b.get_height() / 2,
                    f"{int_br(r['cancelaram'])} de\n{int_br(r['clientes'])}", ha="center", va="center",
                    fontsize=12, color="white")
        ax.axhline(media, color="black", linestyle="--", linewidth=1)
        ax.set_ylim(0, 19)
        ax.set_yticks([])
        ax.tick_params(axis="x", labelsize=12)
        ax.set_title(titulo, fontsize=14, loc="left")
        _limpar(ax)

    cores_uf = [CINZA_ESCURO if e == "CE" else CINZA for e in uf.index]
    barras = ax3.barh(uf.index, uf["churn_%"], color=cores_uf, height=0.7)
    for b, (e, r) in zip(barras, uf.iterrows()):
        ax3.text(b.get_width() + 0.25, b.get_y() + b.get_height() / 2, f"{pct_br(r['churn_%'])}  (n = {int_br(r['clientes'])})",
                 va="center", fontsize=12, bbox=BRANCO, zorder=5)
    ax3.axvline(media, color="black", linestyle="--", linewidth=1)
    ax3.set_xlim(0, uf["churn_%"].max() * 1.35)
    ax3.set_xticks([])
    ax3.tick_params(axis="y", labelsize=12)
    ax3.set_title("Por estado (23 UFs com clientes)", fontsize=14, loc="left")
    _limpar(ax3)

    fig.suptitle("Churn de abril/2026 por perfil demográfico: plano, capital × interior e estado",
                 fontsize=14, x=0.05, ha="left")
    fig.text(0.05, 0.035, f"Linha tracejada = média geral ({pct_br(media)}). CE (cinza escuro) é o único estado que passa na "
             "correção de Bonferroni.", fontsize=12, ha="left")
    fig.text(0.05, 0.005, "Associação observada, não causa. n = 10.000 clientes, 1.353 cancelamentos.", fontsize=12, ha="left")
    destino.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(destino, dpi=130, facecolor="white", bbox_inches="tight")
    plt.close(fig)
    return destino


if __name__ == "__main__":
    dados = carregar()
    for col in ("plano", "local", "estado"):
        print(tabela(dados, col).round(2).to_string(), "\n")
    print("Gráfico salvo em:", desenhar(dados))
