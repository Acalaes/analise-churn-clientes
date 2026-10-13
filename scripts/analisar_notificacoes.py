"""Aprofundamento: clientes com poucas notificações (0-1 em notificacoes_7d) se comportam de forma diferente?

Perguntas:
1. A janela de 7 dias é mesmo "os 7 primeiros dias após o cadastro"? (os dados dão pistas, não prova)
2. O grupo 0-1 difere do grupo 2+ em outras variáveis (transações, ticket, chamados, plano, tempo de casa, geografia)?
3. 0 e 1 notificação se comportam igual? Existe gradiente entre 2 e 12?
4. O efeito sobre o churn é parecido em subgrupos (plano, tempo de casa, situação do chamado)?

Uso (a partir da raiz do projeto):  python scripts/analisar_notificacoes.py
Somente leitura. Funções retornam DataFrame/dict; só o __main__ imprime.
"""
import numpy as np
import pandas as pd

from analisar_drivers import (INICIO_JANELA, N_PERMUTACOES, SEMENTE, _agrupar_pequenos, _rotular_quartis,
                              risco_relativo_com_ic, situacao_chamado, teste_permutacao, wilson)
from investigar_transacoes import carregar_limpo

TICKET_EXTREMO = 10000  # valores >= 10.000 são a 2ª população achada na auditoria (ver notas do projeto)


def checar_janela(df):
    """Pistas sobre o que 'notificacoes_7d' mede. Se a janela fosse 'primeiros 7 dias após o cadastro', quem
    cancelou antes de completar 7 dias de casa teria contagem truncada (menor) e a coluna não deveria depender
    de quando o cliente se cadastrou. Nenhuma checagem aqui PROVA a definição; só contradiz ou não."""
    ch = df[df["churn_30d"]].copy()
    ch["dias_ate_cancelar"] = (ch["data_cancelamento"] - ch["data_cadastro"]).dt.days
    curto = ch["dias_ate_cancelar"] < 7
    dias_cadastro = (df["data_cadastro"] - df["data_cadastro"].min()).dt.days
    rho = pd.concat([df["notificacoes_7d"], dias_cadastro], axis=1).corr(method="spearman").iloc[0, 1]
    recentes = df["data_cadastro"] >= INICIO_JANELA - pd.Timedelta(days=7)
    return {
        "churners_total": len(ch),
        "churners_que_cancelaram_antes_de_7_dias_de_casa": int(curto.sum()),
        "notificacoes_media_desses": round(ch.loc[curto, "notificacoes_7d"].mean(), 2) if curto.any() else None,
        "notificacoes_media_dos_demais_churners": round(ch.loc[~curto, "notificacoes_7d"].mean(), 2),
        "spearman_notificacoes_vs_data_de_cadastro": round(float(rho), 3),
        "clientes_cadastrados_nos_ultimos_7_dias_da_base": int(recentes.sum()),
        "notificacoes_media_dos_cadastrados_nos_ultimos_7_dias": round(df.loc[recentes, "notificacoes_7d"].mean(), 2),
        "notificacoes_media_dos_demais": round(df.loc[~recentes, "notificacoes_7d"].mean(), 2),
    }


def teste_media_perm(x, g, n_perm=N_PERMUTACOES, semente=SEMENTE):
    """Diferença de médias (g=True menos g=False) e p-valor por permutação. Ignora NaN em x."""
    x = np.asarray(x, dtype=float)
    g = np.asarray(g, dtype=bool)
    ok = ~np.isnan(x)
    x, g = x[ok], g[ok]
    obs = x[g].mean() - x[~g].mean()
    rng = np.random.default_rng(semente)
    mais = sum(abs(x[gp].mean() - x[~gp].mean()) >= abs(obs) for gp in (rng.permutation(g) for _ in range(n_perm)))
    return obs, (mais + 1) / (n_perm + 1)


def perfil_por_grupo(df):
    """Compara o grupo 0-1 notificação com o grupo 2+ em 12 características. p por permutação.
    Limite de Bonferroni para 12 testes: 0,0042."""
    baixo = (df["notificacoes_7d"] <= 1).to_numpy()
    tr = df["transacoes_30d"]
    tk = df["ticket_medio_30d"]
    tempo_casa = (INICIO_JANELA - df["data_cadastro"]).dt.days
    cham = df["abriu_chamado"]
    numericas = {
        "transacoes_30d (média, onde informado)": tr,
        "transacoes_30d zero ou ausente (%)": ((tr == 0) | tr.isna()).astype(float) * 100,
        "ticket médio (média, só valores normais)": tk.where((tk > 0) & (tk < TICKET_EXTREMO)),
        "ticket = 0 (%)": (tk == 0).astype(float) * 100,
        "ticket extremo >= 10.000 (%)": (tk >= TICKET_EXTREMO).astype(float) * 100,
        "abriu chamado (%)": cham.astype(float) * 100,
        "tempo de resposta (média h, só quem abriu)": df["tempo_resposta_chamado_h"],
        "chamado lento > 24 h (% de quem abriu)": (df["tempo_resposta_chamado_h"] > 24).astype(float).where(cham) * 100,
        "plano Premium (%)": (df["plano"] == "Premium").astype(float) * 100,
        "tempo de casa (média, dias)": tempo_casa.astype(float),
    }
    linhas = []
    for nome, x in numericas.items():
        diff, p = teste_media_perm(x.to_numpy(), baixo)
        linhas.append({"caracteristica": nome, "grupo_0-1": round(x[baixo].mean(), 2), "grupo_2+": round(x[~baixo].mean(), 2),
                       "diferenca": round(diff, 2), "p_permutacao": round(p, 4)})
    for col in ("estado", "cidade"):
        t = teste_permutacao(_agrupar_pequenos(df[col]), pd.Series(baixo, index=df.index))
        linhas.append({"caracteristica": f"{col} (distribuição, teste global)", "grupo_0-1": np.nan, "grupo_2+": np.nan,
                       "diferenca": np.nan, "p_permutacao": round(t["p_permutacao"], 4)})
    out = pd.DataFrame(linhas)
    out["significativo_bonferroni"] = out["p_permutacao"] < 0.05 / len(out)
    return out


def zero_vs_um_e_gradiente(df):
    """(a) 0 e 1 notificação têm o mesmo churn? (b) entre 2 e 12 há tendência? Retorna dict."""
    c = df["churn_30d"]
    n = df["notificacoes_7d"]
    zero, um = n == 0, n == 1
    rr = risco_relativo_com_ic(int(c[zero].sum()), int(zero.sum()), int(c[um].sum()), int(um.sum()))
    alto = n >= 2
    lv, y = n[alto].to_numpy(), c[alto].to_numpy().astype(float)
    rho = float(pd.Series(lv).corr(pd.Series(y), method="spearman"))
    rng = np.random.default_rng(SEMENTE)
    perm = [abs(pd.Series(lv).corr(pd.Series(rng.permutation(y)), method="spearman")) for _ in range(2000)]
    p = (sum(v >= abs(rho) for v in perm) + 1) / 2001
    return {"zero_vs_um": {"churn_zero_%": rr["churn_exposto_%"], "churn_um_%": rr["churn_referencia_%"], "RR": rr["risco_relativo"],
                           "RR_ic95": rr["rr_ic95"]},
            "tendencia_2_a_12": {"spearman_nivel_vs_churn": round(rho, 4), "p_permutacao": round(p, 4),
                                 "churn_2_a_12_%": round(c[alto].mean() * 100, 2)}}


def efeito_por_estrato(df):
    """Churn (0-1 vs 2+) dentro de cada subgrupo, com RR e IC 95%. Mostra se o efeito é parecido em todo lugar."""
    baixo = df["notificacoes_7d"] <= 1
    c = df["churn_30d"]
    tc, _ = _rotular_quartis((INICIO_JANELA - df["data_cadastro"]).dt.days, inteiro=True)
    estratos = {"plano": df["plano"], "tempo de casa (quartis, dias)": tc, "situação do chamado": situacao_chamado(df)}
    linhas = []
    for nome, serie in estratos.items():
        for nivel in sorted(serie.unique()):
            m = serie == nivel
            e, r = m & baixo, m & ~baixo
            rr = risco_relativo_com_ic(int(c[e].sum()), int(e.sum()), int(c[r].sum()), int(r.sum()))
            linhas.append({"estrato": nome, "grupo": nivel, "n_0-1": int(e.sum()), "n_2+": int(r.sum()), **{k: rr[k] for k in
                           ("churn_exposto_%", "churn_referencia_%", "risco_relativo", "rr_ic95")}})
    return pd.DataFrame(linhas).rename(columns={"churn_exposto_%": "churn_0-1_%", "churn_referencia_%": "churn_2+_%"})


if __name__ == "__main__":
    dados = carregar_limpo()
    print("1) PISTAS SOBRE A JANELA DE 7 DIAS")
    for k, v in checar_janela(dados).items():
        print(f"   {k}: {v}")
    print("\n2) 0-1 notificação vs 2+, em outras características\n", perfil_por_grupo(dados).to_string(index=False))
    print("\n3) 0 vs 1 e gradiente entre 2 e 12")
    for k, v in zero_vs_um_e_gradiente(dados).items():
        print(f"   {k}: {v}")
    print("\n4) Efeito (0-1 vs 2+) por subgrupo\n", efeito_por_estrato(dados).to_string(index=False))
