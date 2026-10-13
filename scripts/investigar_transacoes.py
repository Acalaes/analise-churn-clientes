"""Investigação dos valores ausentes de transacoes_30d no dataset LIMPO.

Pergunta: a ausência é ao acaso (MCAR), explicada por outras variáveis (MAR) ou depende do próprio
valor não observado (MNAR, ex.: ausente = 0 transações)? Só (MCAR) permitiria descartar/imputar sem viés.

Uso (a partir da raiz do projeto):  python scripts/investigar_transacoes.py
Somente leitura: não altera nenhum arquivo.

Decisão: testes de associação por PERMUTAÇÃO (numpy), em vez de scipy, para não introduzir biblioteca
nova (CLAUDE.md). A estatística é o qui-quadrado entre o indicador de ausência e cada variável; o p-valor
é a fração de permutações aleatórias do indicador com qui-quadrado >= ao observado.
"""
from pathlib import Path

import numpy as np
import pandas as pd

RAIZ = Path(__file__).resolve().parent.parent
CSV_LIMPO = RAIZ / "data" / "clientes_pixpay_limpo.csv"


def carregar_limpo(caminho=CSV_LIMPO):
    df = pd.read_csv(caminho, encoding="utf-8", dtype={"cpf": str}, parse_dates=["data_cadastro", "data_cancelamento"])
    assert df.shape == (10000, 15), df.shape
    df["ausente"] = df["transacoes_30d"].isna()
    return df


def derivar_variaveis(df):
    """Variáveis candidatas a explicar a ausência (todas categóricas, p/ o teste qui-quadrado).
    Numéricas viram faixas; ticket é separado em 3 regimes porque a auditoria achou valores em outra escala."""
    v = pd.DataFrame(index=df.index)
    v["plano"] = df["plano"]
    v["estado"] = df["estado"]
    v["cidade"] = df["cidade"]
    v["abriu_chamado"] = df["abriu_chamado"].astype(str)
    v["churn_30d"] = df["churn_30d"].astype(str)
    v["notificacoes_7d"] = df["notificacoes_7d"].astype(str)
    v["mes_cadastro"] = df["data_cadastro"].dt.strftime("%Y-%m")
    v["dia_da_semana_cadastro"] = df["data_cadastro"].dt.dayofweek.astype(str)
    v["dia_cancelamento"] = df["data_cancelamento"].dt.strftime("%d").fillna("(não cancelou)")
    v["ticket_regime"] = np.select([df["ticket_medio_30d"] == 0, df["ticket_medio_30d"] >= 10000],
                                   ["zero", "extremo (>=10.000)"], default="normal")
    v["tempo_resposta_faixa"] = pd.qcut(df["tempo_resposta_chamado_h"], 4, duplicates="drop").astype(str).replace("nan", "(sem chamado)")
    # posição no arquivo: se a ausência vier em blocos, decis da ordem das linhas denunciam
    v["posicao_no_arquivo_decil"] = pd.qcut(np.arange(len(df)), 10, labels=False).astype(str)
    v["cliente_id_decil"] = pd.qcut(df["cliente_id"].str[3:].astype(int), 10, labels=False).astype(str)
    return v


def _qui2(codigos, ausente, n_niveis):
    """Qui-quadrado 2 x k entre ausente (bool) e a variável codificada 0..k-1."""
    obs_aus = np.bincount(codigos[ausente], minlength=n_niveis)
    tot = np.bincount(codigos, minlength=n_niveis)
    esp_aus = tot * ausente.mean()
    esp_pres = tot * (1 - ausente.mean())
    obs_pres = tot - obs_aus
    return float((((obs_aus - esp_aus) ** 2 / esp_aus) + ((obs_pres - esp_pres) ** 2 / esp_pres)).sum())


def teste_permutacao(serie, ausente, n_perm=2000, semente=0):
    """qui-quadrado observado e p-valor por permutação, para uma variável categórica."""
    codigos, niveis = pd.factorize(serie)
    k = len(niveis)
    aus = ausente.to_numpy()
    obs = _qui2(codigos, aus, k)
    rng = np.random.default_rng(semente)
    maiores = sum(_qui2(codigos, rng.permutation(aus), k) >= obs for _ in range(n_perm))
    return {"qui2": round(obs, 2), "niveis": k, "p_permutacao": (maiores + 1) / (n_perm + 1)}


def varrer_associacoes(df, n_perm=2000):
    """Testa cada variável candidata contra a ausência de transacoes_30d. Retorna DataFrame ordenado por p."""
    v = derivar_variaveis(df)
    linhas = []
    for col in v.columns:
        r = teste_permutacao(v[col], df["ausente"], n_perm)
        taxas = df["ausente"].groupby(v[col]).agg(["mean", "size"])
        taxas = taxas[taxas["size"] >= 30]  # ignora níveis minúsculos ao reportar min/max
        linhas.append({"variavel": col, **r, "taxa_min_%": round(taxas["mean"].min() * 100, 1),
                       "taxa_max_%": round(taxas["mean"].max() * 100, 1)})
    out = pd.DataFrame(linhas).sort_values("p_permutacao").reset_index(drop=True)
    out["significativo_bonferroni"] = out["p_permutacao"] < 0.05 / len(out)
    return out


def taxa_por(df, coluna_derivada):
    v = derivar_variaveis(df)
    t = df["ausente"].groupby(v[coluna_derivada]).agg(linhas="size", ausentes="sum")
    t["taxa_ausente_%"] = (t["ausentes"] / t["linhas"] * 100).round(2)
    return t


def relacao_com_ticket(df):
    """Ausente se parece com 'zero transações'? Compara ticket e churn entre ausente, zero e positivo."""
    grupo = np.select([df["ausente"], df["transacoes_30d"] == 0], ["ausente", "transacoes = 0"], default="transacoes > 0")
    d = df.assign(grupo=grupo)
    return d.groupby("grupo").agg(
        linhas=("cliente_id", "size"),
        ticket_zero_pct=("ticket_medio_30d", lambda s: round((s == 0).mean() * 100, 1)),
        ticket_extremo_pct=("ticket_medio_30d", lambda s: round((s >= 10000).mean() * 100, 1)),
        ticket_mediana_normais=("ticket_medio_30d", lambda s: round(s[(s > 0) & (s < 10000)].median(), 2)),
        notificacoes_media=("notificacoes_7d", lambda s: round(s.mean(), 2)),
        churn_pct=("churn_30d", lambda s: round(s.mean() * 100, 2)),
        chamado_pct=("abriu_chamado", lambda s: round(s.mean() * 100, 2)),
    )


def ticket_vs_transacoes_observadas(df):
    """Nas linhas com transacoes_30d observado: ticket = 0 acontece só quando transacoes = 0?"""
    obs = df[~df["ausente"]]
    return pd.crosstab(obs["transacoes_30d"].eq(0).rename("transacoes_igual_0"),
                       obs["ticket_medio_30d"].eq(0).rename("ticket_igual_0"))


def distribuicao_transacoes(df):
    """Forma da distribuição observada (para ver se há 'buraco' de zeros que explique os ausentes)."""
    s = df["transacoes_30d"].dropna()
    return pd.DataFrame({"linhas_com_valor": [len(s)], "zeros": [int((s == 0).sum())], "zeros_%": [round((s == 0).mean() * 100, 2)],
                         "min": [s.min()], "mediana": [s.median()], "media": [round(s.mean(), 2)], "max": [s.max()]})


def blocos_consecutivos(df):
    """Os ausentes aparecem agrupados no arquivo? Compara nº de 'corridas' observado com o esperado ao acaso."""
    a = df["ausente"].to_numpy()
    corridas = 1 + int((a[1:] != a[:-1]).sum())
    n1, n0 = int(a.sum()), int((~a).sum())
    esperado = 1 + 2 * n1 * n0 / (n1 + n0)
    var = 2 * n1 * n0 * (2 * n1 * n0 - n1 - n0) / ((n1 + n0) ** 2 * (n1 + n0 - 1))
    z = (corridas - esperado) / np.sqrt(var)
    return {"corridas_observadas": corridas, "corridas_esperadas_ao_acaso": round(esperado, 1), "z_wald_wolfowitz": round(float(z), 2)}


if __name__ == "__main__":
    dados = carregar_limpo()
    print("AUSENTES:", int(dados["ausente"].sum()), f"({dados['ausente'].mean() * 100:.2f}%)\n")
    print("1) Distribuição observada\n", distribuicao_transacoes(dados).to_string(index=False), "\n")
    print("2) Associação com cada variável (permutação, 2000 reps)\n", varrer_associacoes(dados).to_string(index=False), "\n")
    print("3) Perfil: ausente vs zero vs positivo\n", relacao_com_ticket(dados).to_string(), "\n")
    print("4) Ticket=0 x transacoes=0 (só linhas observadas)\n", ticket_vs_transacoes_observadas(dados).to_string(), "\n")
    print("5) Blocos consecutivos\n", blocos_consecutivos(dados))
    print("\n6) Taxa por regime de ticket\n", taxa_por(dados, "ticket_regime").to_string())
    print("\n7) Taxa por mês de cadastro\n", taxa_por(dados, "mes_cadastro").to_string())
