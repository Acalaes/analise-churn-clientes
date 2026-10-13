"""Limpeza do dataset PixPay, orientada pelas hipóteses e achados da auditoria (auditoria_pixpay.md).

Entrada : data/clientes_pixpay.csv         (bruto, NÃO é modificado)
Saída   : data/clientes_pixpay_limpo.csv   (novo arquivo)

Uso (a partir da raiz do projeto):  python scripts/limpar_dados.py

Princípios:
- O bruto nunca é sobrescrito.
- Mapeamentos são ESTRITOS: valor sem mapeamento gera erro, nunca vira NaN em silêncio.
- A única operação que descarta linhas é a remoção de cópias de cliente_id (decisão 11),
  e ela só ocorre se as cópias forem idênticas após a normalização; se houver conflito real, o script para.
- Funções retornam DataFrame/dict; só o bloco __main__ imprime.
"""
import re
import unicodedata
from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parent.parent
CSV_BRUTO = RAIZ / "data" / "clientes_pixpay.csv"
CSV_LIMPO = RAIZ / "data" / "clientes_pixpay_limpo.csv"

PLANOS = {"basico": "Básico", "basic": "Básico", "premium": "Premium", "premim": "Premium", "premiun": "Premium"}
UF_POR_NOME = {
    "acre": "AC", "alagoas": "AL", "amapa": "AP", "amazonas": "AM", "bahia": "BA", "ceara": "CE",
    "distrito federal": "DF", "espirito santo": "ES", "goias": "GO", "maranhao": "MA",
    "mato grosso": "MT", "mato grosso do sul": "MS", "minas gerais": "MG", "para": "PA",
    "paraiba": "PB", "parana": "PR", "pernambuco": "PE", "piaui": "PI", "rio de janeiro": "RJ",
    "rio grande do norte": "RN", "rio grande do sul": "RS", "rondonia": "RO", "roraima": "RR",
    "santa catarina": "SC", "sao paulo": "SP", "sergipe": "SE", "tocantins": "TO",
}
MAPA_ESTADO = {**UF_POR_NOME, **{uf.casefold(): uf for uf in UF_POR_NOME.values()}}
BOOLEANOS = {"true": True, "false": False, "sim": True, "nao": False}
MENSALIDADE_POR_PLANO = {"Básico": 19.90, "Premium": 49.90}

# (regex completa, formato strptime). Ordem de interpretação validada na auditoria:
# em DD-MM-AA o 1º campo chega a 31 e o 2º nunca passa de 12 => dia-mês-ano, sem ambiguidade.
FORMATOS_DATA = [
    (r"\d{2}/\d{2}/\d{4}", "%d/%m/%Y"),
    (r"\d{4}-\d{2}-\d{2}", "%Y-%m-%d"),
    (r"\d{2}-\d{2}-\d{2}", "%d-%m-%y"),  # %y: 00-68 => 2000-2068 (dataset só tem anos 24-26)
]

COLUNAS_SEM_NULO = ["cliente_id", "nome", "cpf", "data_cadastro", "cidade", "estado", "plano",
                    "valor_mensalidade", "notificacoes_7d", "ticket_medio_30d", "abriu_chamado", "churn_30d"]


# ---------------------------------------------------------------- utilitários
def _chave(texto):
    """Chave de comparação: sem acento, sem espaços nas pontas, minúscula."""
    return unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii").strip().casefold()


def _mapear_estrito(serie, mapa, nome_coluna):
    """Aplica mapa pela chave normalizada. Valor sem mapeamento => erro (nunca NaN silencioso)."""
    mapeado = serie.map(lambda v: mapa.get(_chave(v)))
    faltando = sorted(serie[mapeado.isna()].unique())
    if faltando:
        raise ValueError(f"{nome_coluna}: valores sem mapeamento: {faltando}")
    return mapeado


def _parse_data(serie, nome_coluna):
    """Converte para datetime exigindo que TODO valor não vazio case com algum formato conhecido."""
    s = serie.str.strip()
    out = pd.Series(pd.NaT, index=s.index, dtype="datetime64[ns]")
    for regex, formato in FORMATOS_DATA:
        casa = s.str.fullmatch(regex)
        if casa.any():
            out.loc[casa] = pd.to_datetime(s[casa], format=formato)
    sem_parse = s.ne("") & out.isna()
    if sem_parse.any():
        raise ValueError(f"{nome_coluna}: datas não reconhecidas: {sorted(s[sem_parse].unique())[:10]}")
    return out


# ---------------------------------------------------------------- carga
def carregar_bruto(caminho=CSV_BRUTO):
    """Lê tudo como texto (dtype=str, sem conversão de nulos) e valida o esquema esperado."""
    df = pd.read_csv(caminho, dtype=str, keep_default_na=False, encoding="utf-8")
    esperadas = ["cliente_id", "nome", "cpf", "data_cadastro", "data_cancelamento", "cidade", "estado", "plano",
                 "valor_mensalidade", "notificacoes_7d", "transacoes_30d", "ticket_medio_30d", "abriu_chamado",
                 "tempo_resposta_chamado_h", "churn_30d"]
    if list(df.columns) != esperadas:
        raise ValueError(f"colunas inesperadas: {list(df.columns)}")
    return df


# ---------------------------------------------------------------- passos de limpeza
def limpar_dados(bruto):
    """Aplica as decisões de limpeza. Retorna dict com 'dados' (DataFrame limpo) e 'log' (DataFrame)."""
    df = bruto.copy()
    log = []

    def registrar(decisao, coluna, antes, depois_txt):
        log.append({"decisao": decisao, "coluna": coluna, "linhas_alteradas": int((antes != depois_txt).sum())})

    # DECISÃO 1 — nome: remover espaços das pontas e padronizar em Title Case.
    # Por quê: a auditoria achou 'TATIANE ALMEIDA' vs 'Tatiane Almeida' e ' João Rodrigues' em cópias do mesmo
    # cliente. Verificado antes: todos os 10.016 nomes têm exatamente 2 palavras e nenhuma partícula
    # (de/da/dos), então .title() não corrompe nada.
    nome = df["nome"].str.strip().str.title()
    registrar("1. nome: strip + Title Case", "nome", df["nome"], nome)
    df["nome"] = nome

    # DECISÃO 2 — plano: 14 grafias -> {Básico, Premium}. Cobre caixa, acento, espaços e typos
    # ('basic', 'premim', 'Premiun'). Mapeamento estrito: grafia nova no futuro gera erro.
    plano = _mapear_estrito(df["plano"], PLANOS, "plano")
    registrar("2. plano: 14 grafias -> 2", "plano", df["plano"], plano)
    df["plano"] = plano

    # DECISÃO 3 — estado: nome por extenso -> sigla UF (27 linhas). Todas mapeiam para UF válida.
    estado = _mapear_estrito(df["estado"], MAPA_ESTADO, "estado")
    registrar("3. estado: nome por extenso -> UF", "estado", df["estado"], estado)
    df["estado"] = estado

    # DECISÃO 4 — cidade: unir grafias da mesma cidade (caixa/acento/espaço) na grafia MAIS FREQUENTE.
    # Por quê: 72 grafias -> 60 cidades (ex.: 'CURITIBA', 'Curitiba ', 'curitiba'). A forma canônica sai
    # dos próprios dados, não de uma lista externa; empate é resolvido pela ordem alfabética.
    cid = df["cidade"].str.strip()
    contagem = pd.DataFrame({"chave": cid.map(_chave), "grafia": cid}).groupby(["chave", "grafia"]).size().rename("n").reset_index()
    canonica = contagem.sort_values(["chave", "n", "grafia"], ascending=[True, False, True]).drop_duplicates("chave")
    cidade = cid.map(_chave).map(canonica.set_index("chave")["grafia"])
    registrar("4. cidade: unir grafias na mais frequente", "cidade", df["cidade"], cidade)
    df["cidade"] = cidade

    # DECISÃO 5 — abriu_chamado e churn_30d: 'sim'/'não' -> True/False (1.001 linhas em abriu_chamado).
    for col in ("abriu_chamado", "churn_30d"):
        bool_col = _mapear_estrito(df[col], BOOLEANOS, col).astype(bool)
        registrar("5. booleano: sim/não -> True/False", col, df[col], bool_col.astype(str))
        df[col] = bool_col

    # DECISÃO 6 — datas: 3 formatos -> datetime. Gravadas no CSV como AAAA-MM-DD (ISO), que é inequívoco
    # para leitura por máquina; a exibição em DD/MM/AAAA fica para os relatórios (regra do CLAUDE.md).
    # data_cancelamento vazia é ausência ESTRUTURAL (quem não cancelou) e é mantida vazia.
    for col in ("data_cadastro", "data_cancelamento"):
        data = _parse_data(df[col], col)
        registrar("6. data -> AAAA-MM-DD", col, df[col], data.dt.strftime("%Y-%m-%d").fillna(""))
        df[col] = data

    # DECISÃO 7 — cpf: padronizar na máscara 000.000.000-00 (formato dominante, 70% das linhas).
    # NÃO se valida o dígito verificador nem se descarta CPF inválido: 99,14% falham, taxa compatível com
    # CPFs aleatórios (~0,97% passariam por acaso), ou seja, dado sintético/anonimizado. Preservar zeros à esquerda.
    d = df["cpf"].str.replace(r"\D", "", regex=True)
    if not d.str.fullmatch(r"\d{11}").all():
        raise ValueError("cpf: há valores que não têm 11 dígitos")
    cpf = d.str[:3] + "." + d.str[3:6] + "." + d.str[6:9] + "-" + d.str[9:]
    registrar("7. cpf: máscara 000.000.000-00", "cpf", df["cpf"], cpf)
    df["cpf"] = cpf

    # DECISÃO 8 — valor_mensalidade: texto ('R$ 19,90', '19,90', '49.90') -> float (19.9 / 49.9).
    # O símbolo R$ e a vírgula decimal são formatação de exibição, não de armazenamento.
    mensal = pd.to_numeric(df["valor_mensalidade"].str.replace("R$", "", regex=False).str.strip()
                           .str.replace(",", ".", regex=False), errors="raise")
    registrar("8. mensalidade -> float", "valor_mensalidade", df["valor_mensalidade"], mensal.map("{:.2f}".format))
    df["valor_mensalidade"] = mensal

    # DECISÃO 9 — colunas numéricas: texto -> número.
    # transacoes_30d: 1.216 ausentes SEM explicação estrutural e sem relação visível com o churn
    # (12,5% vs 13,65%). NÃO imputar e NÃO descartar: fica ausente (<NA>) até decidirmos o tratamento.
    # tempo_resposta_chamado_h: ausente = não abriu chamado (estrutural), mantido vazio.
    for col in ("notificacoes_7d", "transacoes_30d"):
        df[col] = pd.to_numeric(df[col].replace("", pd.NA), errors="raise").astype("Int64")  # todos inteiros (verificado)
    for col in ("ticket_medio_30d", "tempo_resposta_chamado_h"):
        df[col] = pd.to_numeric(df[col].replace("", pd.NA), errors="raise").astype("float64")

    # DECISÃO 10 — ticket_medio_30d: valores extremos (máx. 999.842,62 vs mediana ~69) NÃO são alterados
    # nem removidos aqui. Fora do escopo da auditoria pedida; serão tratados após decisão do usuário.

    # DECISÃO 11 — cliente_id duplicado: manter 1 linha por cliente_id (mantém a primeira ocorrência).
    # Só é seguro porque, depois dos passos 1-9, as cópias ficaram IDÊNTICAS (a auditoria mostrou que as 16
    # divergiam apenas em formato/caixa/espaço). Se sobrar conflito real, o script PARA em vez de escolher.
    antes = len(df)
    df = df.drop_duplicates(keep="first")
    conflitos = df[df["cliente_id"].duplicated(keep=False)]
    if not conflitos.empty:
        raise ValueError(f"cliente_id com cópias conflitantes após normalizar:\n{conflitos}")
    log.append({"decisao": "11. remover cópias de cliente_id", "coluna": "(linhas)", "linhas_alteradas": antes - len(df)})

    return {"dados": df.reset_index(drop=True), "log": pd.DataFrame(log)}


# ---------------------------------------------------------------- verificações pós-limpeza
def verificar_limpo(limpo, bruto):
    """Contagem de violações de regras de consistência. 0 = ok. Retorna dict."""
    hoje = pd.Timestamp.today().normalize()
    return {
        "linhas_limpas": len(limpo),
        "ids_unicos_bruto": bruto["cliente_id"].nunique(),
        "cliente_id_duplicado": int(limpo["cliente_id"].duplicated().sum()),
        "nulos_em_colunas_obrigatorias": int(limpo[COLUNAS_SEM_NULO].isna().sum().sum()),
        "churn_diferente_de_ter_data_cancelamento": int((limpo["churn_30d"] != limpo["data_cancelamento"].notna()).sum()),
        "chamado_diferente_de_ter_tempo_resposta": int((limpo["abriu_chamado"] != limpo["tempo_resposta_chamado_h"].notna()).sum()),
        "plano_incoerente_com_mensalidade": int((limpo["plano"].map(MENSALIDADE_POR_PLANO) != limpo["valor_mensalidade"]).sum()),
        "cancelamento_antes_do_cadastro": int((limpo["data_cancelamento"] < limpo["data_cadastro"]).sum()),
        "cadastro_no_futuro": int((limpo["data_cadastro"] > hoje).sum()),
        "uf_invalida": int((~limpo["estado"].isin(set(UF_POR_NOME.values()))).sum()),
    }


def salvar_limpo(limpo, caminho=CSV_LIMPO):
    """Grava o CSV limpo (UTF-8, datas AAAA-MM-DD). Nunca escreve sobre o bruto."""
    if Path(caminho).resolve() == CSV_BRUTO.resolve():
        raise ValueError("recusado: o caminho de saída é o do arquivo bruto")
    limpo.to_csv(caminho, index=False, encoding="utf-8", date_format="%Y-%m-%d")
    return Path(caminho)


if __name__ == "__main__":
    bruto = carregar_bruto()
    resultado = limpar_dados(bruto)
    verificacoes = verificar_limpo(resultado["dados"], bruto)
    destino = salvar_limpo(resultado["dados"])
    print(resultado["log"].to_string(index=False))
    print()
    for k, v in verificacoes.items():
        print(f"{k}: {v}")
    print(f"\nSalvo em: {destino}")
