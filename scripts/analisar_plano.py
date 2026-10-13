"""Aprofundamento: churn por plano (Básico vs. Premium).

1. Taxa de churn por plano, diferença, risco relativo e teste de permutação.
2. O efeito do plano se mantém dentro de cada segmento de risco (nenhum sinal / só notificações / só chamado / ambos)?
3. Os planos são comparáveis? (prevalência dos sinais de risco, tempo de casa, geografia)
4. Quanto o churn de cada plano custa em mensalidade?

Uso (a partir da raiz do projeto):  python scripts/analisar_plano.py
Somente leitura. Funções retornam DataFrame/dict; só o __main__ imprime.
"""
import numpy as np
import pandas as pd

from analisar_drivers import (INICIO_JANELA, _agrupar_pequenos, rr_mantel_haenszel, risco_relativo_com_ic, sinais_de_risco,
                              tabela_por_grupo, teste_permutacao)
from analisar_notificacoes import teste_media_perm
from investigar_transacoes import carregar_limpo


def brl(valor):
    """Formata em reais no padrão do projeto: R$ 1.234,56."""
    return "R$ " + f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def churn_por_plano(df):
    """Churn por plano (IC 95% de Wilson), RR Premium/Básico e p-valor por permutação (diferença de proporções)."""
    t = tabela_por_grupo(df["plano"], df["churn_30d"], ordem=["Básico", "Premium"])
    prem = (df["plano"] == "Premium").to_numpy()
    diff, p = teste_media_perm(df["churn_30d"].astype(float).to_numpy(), prem)
    rr = risco_relativo_com_ic(int(t.loc["Premium", "cancelaram"]), int(t.loc["Premium", "clientes"]),
                               int(t.loc["Básico", "cancelaram"]), int(t.loc["Básico", "clientes"]))
    return {"tabela": t, "contraste": rr, "p_permutacao": round(p, 4)}


def plano_por_segmento(df):
    """Churn de Básico e Premium dentro de cada segmento de risco, com RR (Premium/Básico) e IC 95%."""
    baixo, lento = sinais_de_risco(df)
    seg = pd.Series(np.select([~baixo & ~lento, baixo & ~lento, ~baixo & lento], ["nenhum sinal", "só notificações 0-1", "só chamado > 24 h"],
                              default="os dois sinais"), index=df.index)
    c = df["churn_30d"]
    linhas = []
    for nome in ["nenhum sinal", "só notificações 0-1", "só chamado > 24 h", "os dois sinais"]:
        m = seg == nome
        p, b = m & (df["plano"] == "Premium"), m & (df["plano"] == "Básico")
        rr = risco_relativo_com_ic(int(c[p].sum()), int(p.sum()), int(c[b].sum()), int(b.sum()))
        linhas.append({"segmento": nome, "n_basico": int(b.sum()), "n_premium": int(p.sum()),
                       "churn_basico_%": rr["churn_referencia_%"], "churn_premium_%": rr["churn_exposto_%"],
                       "dif_pp": rr["dif_pp"], "rr_premium_basico": rr["risco_relativo"], "rr_ic95": rr["rr_ic95"]})
    ajustado = rr_mantel_haenszel(df["plano"] == "Premium", c, seg)
    return pd.DataFrame(linhas), ajustado


def balanco_dos_planos(df):
    """Os dois planos têm perfis parecidos nas demais variáveis? (se não, a diferença de churn pode ser confusão)"""
    prem = (df["plano"] == "Premium").to_numpy()
    baixo, lento = sinais_de_risco(df)
    cham = df["abriu_chamado"]
    itens = {
        "notificações 0-1 (%)": baixo.astype(float) * 100,
        "abriu chamado (%)": cham.astype(float) * 100,
        "chamado lento > 24 h (% de quem abriu)": (df["tempo_resposta_chamado_h"] > 24).astype(float).where(cham) * 100,
        "tempo de resposta (média h, só quem abriu)": df["tempo_resposta_chamado_h"],
        "transações 30d (média, onde informado)": df["transacoes_30d"],
        "tempo de casa (média, dias)": (INICIO_JANELA - df["data_cadastro"]).dt.days.astype(float),
    }
    linhas = []
    for nome, x in itens.items():
        d, p = teste_media_perm(x.to_numpy(dtype=float), prem)
        linhas.append({"caracteristica": nome, "basico": round(x[~prem].mean(), 2), "premium": round(x[prem].mean(), 2),
                       "diferenca": round(d, 2), "p_permutacao": round(p, 4)})
    for col in ("estado", "cidade"):
        t = teste_permutacao(_agrupar_pequenos(df[col]), pd.Series(prem, index=df.index))
        linhas.append({"caracteristica": f"{col} (distribuição, teste global)", "basico": np.nan, "premium": np.nan,
                       "diferenca": np.nan, "p_permutacao": round(t["p_permutacao"], 4)})
    return pd.DataFrame(linhas)


def impacto_financeiro(df):
    """Mensalidade perdida por cancelamento em abril, por plano. Considera SÓ a mensalidade (valor_mensalidade);
    não inclui receita de transações/interchange, que o dataset não traz."""
    g = df.groupby("plano").agg(clientes=("cliente_id", "size"), cancelaram=("churn_30d", "sum"), mensalidade=("valor_mensalidade", "first"))
    g["receita_mensal_da_base"] = g["clientes"] * g["mensalidade"]
    g["receita_mensal_perdida"] = g["cancelaram"] * g["mensalidade"]
    g["%_da_receita_do_plano_perdida"] = (g["receita_mensal_perdida"] / g["receita_mensal_da_base"] * 100).round(2)
    total = g[["clientes", "cancelaram", "receita_mensal_da_base", "receita_mensal_perdida"]].sum()
    g["%_dos_clientes"] = (g["clientes"] / total["clientes"] * 100).round(1)
    g["%_dos_cancelamentos"] = (g["cancelaram"] / total["cancelaram"] * 100).round(1)
    g["%_da_receita_perdida_total"] = (g["receita_mensal_perdida"] / total["receita_mensal_perdida"] * 100).round(1)
    return g, {"receita_mensal_da_base": total["receita_mensal_da_base"], "receita_mensal_perdida": total["receita_mensal_perdida"],
               "%_da_receita_total_perdida": round(total["receita_mensal_perdida"] / total["receita_mensal_da_base"] * 100, 2),
               "%_dos_clientes_perdidos": round(total["cancelaram"] / total["clientes"] * 100, 2)}


if __name__ == "__main__":
    dados = carregar_limpo()
    r = churn_por_plano(dados)
    print("1) CHURN POR PLANO\n", r["tabela"].to_string(), "\n", r["contraste"], "\n p (permutação):", r["p_permutacao"])
    seg, aj = plano_por_segmento(dados)
    print("\n2) PLANO DENTRO DE CADA SEGMENTO DE RISCO\n", seg.to_string(index=False), "\n RR ajustado (Mantel-Haenszel):", aj)
    print("\n3) PLANOS SÃO COMPARÁVEIS?\n", balanco_dos_planos(dados).to_string(index=False))
    fin, tot = impacto_financeiro(dados)
    print("\n4) IMPACTO EM MENSALIDADE (valores numéricos)\n", fin.to_string())
    print("\n   Receita mensal da base:", brl(tot["receita_mensal_da_base"]), "| perdida:", brl(tot["receita_mensal_perdida"]),
          f"| {tot['%_da_receita_total_perdida']}% da receita vs {tot['%_dos_clientes_perdidos']}% dos clientes")
    for plano, row in fin.iterrows():
        print(f"   {plano}: mensalidade {brl(row['mensalidade'])} | perdida {brl(row['receita_mensal_perdida'])} | base {brl(row['receita_mensal_da_base'])}")
