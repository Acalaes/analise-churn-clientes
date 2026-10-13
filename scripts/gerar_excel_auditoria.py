"""Gera auditoria_pixpay.xlsx na raiz do projeto, para inspeção manual da sujeira dos dados.

Somente diagnóstico: o CSV em data/ NÃO é alterado e nenhuma linha é descartada.
Uso (a partir da raiz do projeto):  python scripts/gerar_excel_auditoria.py

Dependência: openpyxl, usado apenas como motor do pandas.to_excel (escrita de .xlsx).
Já vem instalado no ambiente; não consta no requirements.txt.
"""
import re
import unicodedata
from pathlib import Path

import pandas as pd
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter

RAIZ = Path(__file__).resolve().parent.parent
CAMINHO_CSV = RAIZ / "data" / "clientes_pixpay.csv"
CAMINHO_XLSX = RAIZ / "auditoria_pixpay.xlsx"

# Decisão: formatos "padrão" adotados como referência (CLAUDE.md: R$ 1.234,56 e DD/MM/AAAA).
# São só a régua para sinalizar desvios; nada é reescrito.
PADRAO_DATA = "99/99/9999"
PADRAO_MENSALIDADE = "A$ 99,99"
PLANO_CANONICO = {"basico": "Básico", "basic": "Básico", "premium": "Premium", "premim": "Premium", "premiun": "Premium"}
UF_POR_NOME = {
    "acre": "AC", "alagoas": "AL", "amapa": "AP", "amazonas": "AM", "bahia": "BA", "ceara": "CE",
    "distrito federal": "DF", "espirito santo": "ES", "goias": "GO", "maranhao": "MA",
    "mato grosso": "MT", "mato grosso do sul": "MS", "minas gerais": "MG", "para": "PA",
    "paraiba": "PB", "parana": "PR", "pernambuco": "PE", "piaui": "PI", "rio de janeiro": "RJ",
    "rio grande do norte": "RN", "rio grande do sul": "RS", "rondonia": "RO", "roraima": "RR",
    "santa catarina": "SC", "sao paulo": "SP", "sergipe": "SE", "tocantins": "TO",
}
UFS_VALIDAS = set(UF_POR_NOME.values())
BOOL_MAPA = {"true": True, "false": False, "sim": True, "nao": False}


def sem_acento(texto):
    return unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")


def chave(texto):
    return sem_acento(texto).strip().casefold()


def padrao(valor):
    """Reduz o valor a um molde: 9 = dígito, A = letra."""
    v = re.sub(r"[^\W\d_]", "A", valor.strip())
    return re.sub(r"\d", "9", v)


def carregar_csv(caminho):
    # dtype=str + keep_default_na=False: nada é convertido nem escondido pelo pandas
    df = pd.read_csv(caminho, dtype=str, keep_default_na=False, encoding="utf-8")
    assert df.shape[1] == 15, f"esperava 15 colunas, vieram {df.shape[1]}"
    return df


def cpf_dv_valido(c):
    if len(c) != 11 or not c.isdigit() or len(set(c)) == 1:
        return False
    for t in (9, 10):
        soma = sum(int(d) * p for d, p in zip(c[:t], range(t + 1, 1, -1)))
        if (soma * 10 % 11) % 10 != int(c[t]):
            return False
    return True


def tabela_variacoes(serie, mapa=None):
    """grafia (entre aspas, para ver espaços) | linhas | valor proposto."""
    t = serie.value_counts().rename_axis("grafia_original").reset_index(name="linhas")
    t["grafia_entre_aspas"] = t["grafia_original"].map(repr)
    if mapa is not None:
        t["valor_proposto"] = t["grafia_original"].map(lambda v: mapa.get(chave(v), "(sem mapeamento)"))
    return t.drop(columns="grafia_original")


def montar_flags(df):
    """Uma coluna booleana por tipo de sujeira + n_problemas, por linha."""
    f = pd.DataFrame(index=df.index)
    f["id_duplicado"] = df["cliente_id"].duplicated(keep=False)
    f["plano_fora_do_padrao"] = ~df["plano"].isin(["Básico", "Premium"])
    f["estado_nao_e_sigla"] = ~df["estado"].isin(UFS_VALIDAS)
    f["abriu_chamado_sim_nao"] = df["abriu_chamado"].isin(["sim", "não"])
    mais_comum = df.groupby(df["cidade"].map(chave))["cidade"].agg(lambda s: s.value_counts().index[0])
    f["cidade_grafia_variante"] = df["cidade"] != df["cidade"].map(chave).map(mais_comum)
    f["espaco_nas_pontas"] = (df[["nome", "cidade", "plano"]] != df[["nome", "cidade", "plano"]].apply(lambda s: s.str.strip())).any(axis=1)
    f["data_cadastro_formato_diferente"] = df["data_cadastro"].map(padrao) != PADRAO_DATA
    f["data_cancelamento_formato_diferente"] = df["data_cancelamento"].str.strip().ne("") & (df["data_cancelamento"].map(padrao) != PADRAO_DATA)
    f["cpf_sem_mascara"] = ~df["cpf"].str.fullmatch(r"\d{3}\.\d{3}\.\d{3}-\d{2}")
    f["mensalidade_formato_diferente"] = df["valor_mensalidade"].map(padrao) != PADRAO_MENSALIDADE
    f["transacoes_30d_ausente"] = df["transacoes_30d"].str.strip().eq("")
    f["n_problemas"] = f.sum(axis=1)
    return f


def montar_duplicatas(df):
    """Todas as linhas de cliente_id repetido, lado a lado, com a lista de colunas que divergem."""
    d = df[df["cliente_id"].duplicated(keep=False)].copy()
    d["posicao_original_csv"] = d.index + 2  # +1 cabeçalho, +1 base 1: número da linha no arquivo
    d = d.sort_values(["cliente_id", "posicao_original_csv"])
    cols = [c for c in df.columns if c != "cliente_id"]
    diverge = d.groupby("cliente_id")[cols].agg(lambda s: s.nunique() > 1)
    d["colunas_que_diferem"] = d["cliente_id"].map(diverge.apply(lambda r: ", ".join(r.index[r]) or "(cópia exata)", axis=1))
    mascara = diverge.loc[d["cliente_id"]]  # mesma ordem das linhas de d
    return d.reset_index(drop=True), mascara.reset_index(drop=True)


def montar_auditoria(df):
    """Retorna dict {nome_da_aba: DataFrame} + máscara de destaque das duplicatas."""
    flags = montar_flags(df)
    dup, mascara_dup = montar_duplicatas(df)
    digitos = df["cpf"].str.replace(r"\D", "", regex=True)
    dv_ok = digitos.map(cpf_dv_valido)

    ausentes = pd.DataFrame({"vazios": (df.apply(lambda s: s.str.strip()) == "").sum()})
    ausentes["pct"] = (ausentes["vazios"] / len(df) * 100).round(2)
    ausentes = ausentes.sort_values("vazios", ascending=False).rename_axis("coluna").reset_index()

    fmt = []
    for col in ["data_cadastro", "data_cancelamento", "cpf", "valor_mensalidade"]:
        s = df.loc[df[col].str.strip().ne(""), col]
        p = s.map(padrao)
        t = p.value_counts().rename_axis("molde (9=dígito, A=letra)").reset_index(name="linhas")
        t["exemplo"] = t["molde (9=dígito, A=letra)"].map(lambda m: s[p == m].iloc[0])
        t.insert(0, "coluna", col)
        fmt.append(t)

    bool_t = pd.concat([
        tabela_variacoes(df[c], BOOL_MAPA).assign(coluna=c)[["coluna", "grafia_entre_aspas", "linhas", "valor_proposto"]]
        for c in ["abriu_chamado", "churn_30d"]
    ], ignore_index=True)

    cid = df["cidade"].to_frame()
    cid["chave"] = cid["cidade"].map(chave)
    var_cidade = (cid.groupby(["chave", "cidade"]).size().rename("linhas").reset_index()
                  .assign(grafia_entre_aspas=lambda t: t["cidade"].map(repr)))
    var_cidade["n_grafias_da_cidade"] = var_cidade.groupby("chave")["cidade"].transform("nunique")
    var_cidade = var_cidade.sort_values(["n_grafias_da_cidade", "chave"], ascending=[False, True])[
        ["chave", "grafia_entre_aspas", "linhas", "n_grafias_da_cidade"]]

    resumo = pd.DataFrame([
        ("Linhas no CSV", len(df), ""),
        ("cliente_id únicos", df["cliente_id"].nunique(), "esperado: 10.000 clientes ativos"),
        ("Linhas excedentes por cliente_id", int(df["cliente_id"].duplicated().sum()), "ver aba Duplicatas_cliente_id"),
        ("Dessas, idênticas em todas as colunas", int(df.duplicated().sum()), "as outras diferem só no formato"),
        ("Grafias distintas de 'plano'", df["plano"].nunique(), "valores reais: 2 (Básico, Premium)"),
        ("Grafias distintas de 'estado'", df["estado"].nunique(), "valores reais: 23 UFs presentes"),
        ("Linhas com estado por extenso", int(flags["estado_nao_e_sigla"].sum()), ""),
        ("Linhas com abriu_chamado = sim/não", int(flags["abriu_chamado_sim_nao"].sum()), "o padrão é True/False"),
        ("Grafias distintas de 'cidade'", df["cidade"].nunique(), f"após normalizar: {df['cidade'].map(chave).nunique()}"),
        ("Linhas com data_cadastro fora de DD/MM/AAAA", int(flags["data_cadastro_formato_diferente"].sum()), ""),
        ("Linhas com CPF sem máscara", int(flags["cpf_sem_mascara"].sum()), ""),
        ("Linhas com mensalidade fora de 'R$ 99,99'", int(flags["mensalidade_formato_diferente"].sum()), ""),
        ("Linhas com transacoes_30d ausente", int(flags["transacoes_30d_ausente"].sum()), "ausência sem explicação estrutural"),
        ("CPF com dígito verificador inválido", int((~dv_ok).sum()), "~0,97% passaria por acaso: indica dado sintético"),
        ("Linhas com pelo menos 1 problema", int((flags["n_problemas"] > 0).sum()), "ver aba Linhas_com_flags"),
    ], columns=["achado", "valor", "observacao"])

    leia_me = pd.DataFrame([
        ("Resumo", "Números principais da auditoria."),
        ("Ausentes", "Valores vazios por coluna. data_cancelamento e tempo_resposta são ausências esperadas."),
        ("Duplicatas_cliente_id", "As 32 linhas (16 ids x 2). Células AMARELAS = valor diferente entre as cópias. posicao_original_csv = linha no arquivo CSV."),
        ("Var_plano / Var_estado", "Todas as grafias existentes, quantas linhas cada uma tem e o valor padrão proposto."),
        ("Var_booleanos", "Grafias de abriu_chamado e churn_30d."),
        ("Var_cidade", "Cada grafia de cidade; n_grafias_da_cidade > 1 = a mesma cidade escrita de formas diferentes."),
        ("Formatos", "Moldes de data, CPF e mensalidade (9 = dígito, A = letra) com exemplo real."),
        ("Linhas_com_flags", "Os 10.016 registros originais + uma coluna VERDADEIRO/FALSO por tipo de sujeira. Use o filtro."),
        ("Aviso", "Nada foi corrigido ou removido. Os valores 'propostos' são sugestões para você aprovar."),
    ], columns=["aba", "o_que_mostra"])

    abas = {
        "Leia-me": leia_me,
        "Resumo": resumo,
        "Ausentes": ausentes,
        "Duplicatas_cliente_id": dup,
        "Var_plano": tabela_variacoes(df["plano"], PLANO_CANONICO),
        "Var_estado": tabela_variacoes(df["estado"], {**UF_POR_NOME, **{u.casefold(): u for u in UFS_VALIDAS}}),
        "Var_booleanos": bool_t,
        "Var_cidade": var_cidade,
        "Formatos": pd.concat(fmt, ignore_index=True),
        "Linhas_com_flags": pd.concat([df, flags], axis=1),
    }
    return abas, mascara_dup


def salvar_excel(abas, mascara_dup, caminho):
    amarelo = PatternFill("solid", fgColor="FFF2CC")
    cabecalho = PatternFill("solid", fgColor="D9E1F2")
    with pd.ExcelWriter(caminho, engine="openpyxl") as xw:
        for nome, tabela in abas.items():
            tabela.to_excel(xw, sheet_name=nome, index=False)
            ws = xw.sheets[nome]
            ws.freeze_panes = "A2"
            ws.auto_filter.ref = ws.dimensions
            for cel in ws[1]:
                cel.font = Font(bold=True)
                cel.fill = cabecalho
            for i, col in enumerate(tabela.columns, start=1):
                largura = max([len(str(col))] + [len(str(v)) for v in tabela[col].head(500)]) + 2
                ws.column_dimensions[get_column_letter(i)].width = min(largura, 48)
        # destaca em amarelo as células que divergem entre cópias do mesmo cliente_id
        ws = xw.sheets["Duplicatas_cliente_id"]
        colunas = list(abas["Duplicatas_cliente_id"].columns)
        for r in range(len(mascara_dup)):
            for col in mascara_dup.columns:
                if mascara_dup.at[r, col]:
                    ws.cell(row=r + 2, column=colunas.index(col) + 1).fill = amarelo
    return caminho


CAMINHO_MD = RAIZ / "auditoria_pixpay.md"


def md_tabela(tabela):
    """DataFrame -> tabela Markdown (sem depender de tabulate). Escapa '|' dentro das células."""
    def cel(v):
        return "" if pd.isna(v) else str(v).replace("|", "\\|").replace("\n", " ")
    linhas = ["| " + " | ".join(map(str, tabela.columns)) + " |",
              "|" + "|".join("---" for _ in tabela.columns) + "|"]
    linhas += ["| " + " | ".join(cel(v) for v in r) + " |" for r in tabela.itertuples(index=False)]
    return "\n".join(linhas)


def gerar_markdown(df, abas):
    """Versão legível no VS Code da auditoria. Valores crus aparecem entre crases e aspas (repr) para expor espaços e caixa."""
    cru = lambda v: f"`{v!r}`"
    flags = abas["Linhas_com_flags"]
    partes = ["# Auditoria de dados — PixPay",
              "> Somente diagnóstico. Nada foi corrigido ou removido; `data/clientes_pixpay.csv` está intacto.  \n"
              "> Valores entre crases e aspas (`'Básico '`) mostram espaços e caixa exatamente como estão no CSV.\n",
              "## 1. Resumo", md_tabela(abas["Resumo"].assign(observacao=abas["Resumo"]["observacao"]
                .str.replace("ver aba Duplicatas_cliente_id", "ver seção 3").str.replace("ver aba Linhas_com_flags", "ver seções 6 e 7"))),
              "## 2. Valores ausentes", md_tabela(abas["Ausentes"]),
              "`data_cancelamento` (= quem cancelou) e `tempo_resposta_chamado_h` (= quem abriu chamado) são ausências esperadas. "
              "`transacoes_30d` é a única sem explicação.\n"]

    # --- Duplicatas: um bloco por cliente_id, mostrando só as colunas que diferem
    dup = abas["Duplicatas_cliente_id"]
    partes += ["## 3. Duplicatas de `cliente_id`",
               "16 ids aparecem 2 vezes. Para cada um: só as colunas que **diferem** entre as duas cópias "
               "(a linha é o número no arquivo CSV, contando o cabeçalho como 1).\n"]
    cols = [c for c in df.columns if c != "cliente_id"]
    for cid, g in dup.groupby("cliente_id", sort=True):
        a, b = g.iloc[0], g.iloc[1]
        difs = [c for c in cols if a[c] != b[c]]
        titulo = f"### `{cid}` — {a['nome'].strip()}"
        if not difs:
            partes += [titulo, f"Cópia **exata** (linhas {a['posicao_original_csv']} e {b['posicao_original_csv']}). Nenhuma coluna difere.\n"]
            continue
        t = pd.DataFrame({"coluna": difs,
                          f"linha {a['posicao_original_csv']}": [cru(a[c]) for c in difs],
                          f"linha {b['posicao_original_csv']}": [cru(b[c]) for c in difs]})
        partes += [titulo, md_tabela(t), ""]

    # --- Variações categóricas
    partes += ["## 4. Variações de grafia (colunas categóricas)", "### `plano` — 14 grafias para 2 valores"]
    vp = abas["Var_plano"].copy(); vp["grafia_entre_aspas"] = vp["grafia_entre_aspas"].map(lambda s: f"`{s}`")
    partes += [md_tabela(vp), "### `estado` — grafias que NÃO são sigla"]
    ve = abas["Var_estado"].copy()
    ve = ve[~ve["grafia_entre_aspas"].str.strip("'").isin(UFS_VALIDAS)]
    ve["grafia_entre_aspas"] = ve["grafia_entre_aspas"].map(lambda s: f"`{s}`")
    partes += [md_tabela(ve), f"As demais {int(abas['Var_estado']['linhas'].sum() - ve['linhas'].sum())} linhas já usam sigla correta.\n",
               "### `abriu_chamado` e `churn_30d`"]
    vb = abas["Var_booleanos"].copy(); vb["grafia_entre_aspas"] = vb["grafia_entre_aspas"].map(lambda s: f"`{s}`")
    partes += [md_tabela(vb), "### `cidade` — mesma cidade escrita de formas diferentes"]
    vc = abas["Var_cidade"]; vc = vc[vc["n_grafias_da_cidade"] > 1].copy()
    vc["grafia_entre_aspas"] = vc["grafia_entre_aspas"].map(lambda s: f"`{s}`")
    partes += [md_tabela(vc), ""]

    # --- Formatos
    partes += ["## 5. Formatos misturados (data, CPF, mensalidade)",
               "Molde: `9` = dígito, `A` = letra.\n", md_tabela(abas["Formatos"]), ""]

    # --- Flags
    cont = flags.drop(columns=list(df.columns) + ["n_problemas"]).sum().astype(int).rename("linhas").rename_axis("problema").reset_index()
    cont["% das linhas"] = (cont["linhas"] / len(df) * 100).round(1)
    partes += ["## 6. Quantas linhas têm cada tipo de sujeira",
               md_tabela(cont.sort_values("linhas", ascending=False)),
               f"\nLinhas com pelo menos 1 problema: **{int((flags['n_problemas'] > 0).sum())}** de {len(df)}.\n"]

    # --- Amostra das linhas mais sujas
    sujas = flags.sort_values("n_problemas", ascending=False).head(10)
    amostra = pd.DataFrame({"linha CSV": sujas.index + 2, "cliente_id": sujas["cliente_id"],
                            "plano": sujas["plano"].map(cru), "estado": sujas["estado"].map(cru),
                            "cidade": sujas["cidade"].map(cru), "data_cadastro": sujas["data_cadastro"],
                            "cpf": sujas["cpf"], "valor_mensalidade": sujas["valor_mensalidade"],
                            "abriu_chamado": sujas["abriu_chamado"].map(cru), "n_problemas": sujas["n_problemas"]})
    partes += ["## 7. As 10 linhas mais sujas (amostra)", md_tabela(amostra), "",
               "A lista completa por linha, com uma coluna por problema, está em `auditoria_pixpay.xlsx` (aba `Linhas_com_flags`).\n"]
    return "\n".join(partes)


if __name__ == "__main__":
    dados = carregar_csv(CAMINHO_CSV)
    abas_xlsx, destaque = montar_auditoria(dados)
    salvar_excel(abas_xlsx, destaque, CAMINHO_XLSX)
    CAMINHO_MD.write_text(gerar_markdown(dados, abas_xlsx), encoding="utf-8")
    print(f"Gerados: {CAMINHO_XLSX} e {CAMINHO_MD}")
