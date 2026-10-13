"""Gráfico de churn por plano (Básico vs. Premium), no padrão da skill grafico-profissional.

Uso (a partir da raiz do projeto):  python scripts/grafico_churn_plano.py
Lê data/clientes_pixpay_limpo.csv (somente leitura) e grava reports/grafico_churn_plano.png.
"""
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

RAIZ = Path(__file__).resolve().parent.parent
CORES = {"Básico": "#1F4E79", "Premium": "#C5221F"}  # padrão visual PixPay (skill grafico-profissional)


def pct_br(valor):
    """12.39 -> '12,39%' (vírgula decimal)."""
    return f"{valor:.2f}".replace(".", ",") + "%"


def int_br(valor):
    """1353 -> '1.353' (ponto de milhar)."""
    return f"{valor:,}".replace(",", ".")


def churn_por_plano(caminho=RAIZ / "data" / "clientes_pixpay_limpo.csv"):
    """Churn de abril/2026 por plano. Retorna DataFrame (clientes, cancelaram, churn_%)."""
    df = pd.read_csv(caminho, encoding="utf-8")
    # Validação de tipos após carregar (CLAUDE.md): churn_30d precisa ser booleano, plano só Básico/Premium.
    df["churn_30d"] = df["churn_30d"].astype(str).str.lower().map({"true": True, "false": False})
    if df["churn_30d"].isna().any() or set(df["plano"].unique()) != {"Básico", "Premium"}:
        raise ValueError("Dados fora do esperado: confira churn_30d e plano.")
    g = df.groupby("plano")["churn_30d"].agg(clientes="size", cancelaram="sum").loc[["Básico", "Premium"]]
    g["churn_%"] = g["cancelaram"] / g["clientes"] * 100
    return g


def desenhar(g, destino=RAIZ / "reports" / "grafico_churn_plano.png"):
    """Desenha e salva o gráfico; retorna o caminho gravado."""
    plt.rcParams["font.family"] = "sans-serif"
    plt.rcParams["font.sans-serif"] = ["Arial", "DejaVu Sans"]
    fig, ax = plt.subplots(figsize=(7, 5.5), facecolor="white")
    ax.set_facecolor("white")
    barras = ax.bar(g.index, g["churn_%"], color=[CORES[p] for p in g.index], width=0.55)
    for barra, (plano, linha) in zip(barras, g.iterrows()):
        ax.text(barra.get_x() + barra.get_width() / 2, barra.get_height() + 0.4, pct_br(linha["churn_%"]),
                ha="center", va="bottom", fontsize=12, fontweight="bold")
        ax.text(barra.get_x() + barra.get_width() / 2, barra.get_height() / 2,
                f"{int_br(int(linha['cancelaram']))} de\n{int_br(int(linha['clientes']))}\nclientes",
                ha="center", va="center", fontsize=12, color="white")
    ax.set_ylim(0, g["churn_%"].max() * 1.2)
    ax.set_ylabel("Churn em abril/2026 (%)", fontsize=12)
    ax.tick_params(axis="x", labelsize=12)
    ax.set_yticks([])  # valores já estão nas barras
    ax.grid(False)
    for lado in ("top", "right", "left", "bottom"):
        ax.spines[lado].set_visible(False)
    ax.set_title("Churn de abril/2026 por plano: Premium cancela mais que Básico", fontsize=14, pad=14)
    fig.tight_layout()
    destino.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(destino, dpi=150, facecolor="white")
    plt.close(fig)
    return destino


if __name__ == "__main__":
    tabela = churn_por_plano()
    print(tabela.to_string())
    print("Gráfico salvo em:", desenhar(tabela))
